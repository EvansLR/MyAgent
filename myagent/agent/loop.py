"""Minimal agent loop for processing messages from the bus."""

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

from myagent.agent.context import ContextBuilder
from myagent.agent.runtime.cron_bridge import AgentCronBridge
from myagent.agent.runtime.env import format_runtime_environment
from myagent.agent.runtime.skill_state import AgentSkillState
from myagent.agent.context.summary import (
    ConversationSummarizer,
    ConversationSummaryConfig,
)
from myagent.agent.runtime.tool_loop import AgentToolLoop
from myagent.agent.runtime.turn_processor import AgentTurnProcessor
from myagent.agent.runtime.run_events import AgentRunEvents
from myagent.agent.runtime.session_history import AgentSessionHistory
from myagent.agent.delegation.subagent import DelegateTaskTool
from myagent.bus import InboundMessage, MessageBus, OutboundMessage
from myagent.memory import MarkdownMemoryStore, MemoryConsolidator, VisibleMemoryCompressor
from myagent.memory.extractor import MemoryExtractor
from myagent.providers import BaseProvider, create_provider
from myagent.skills import SkillRegistry
from myagent.tools import (
    MemoryArchiveTool,
    MemoryForgetTool,
    MemoryGetTool,
    MemoryProposeTool,
    MemoryRememberTool,
    MemorySearchTool,
    SkillGetTool,
    ToolRegistry,
    create_default_registry,
)
from myagent.tracing import JsonlTraceStore, TraceStore
from myagent.profile import ProfileLoader

if TYPE_CHECKING:
    from myagent.cron.service import CronService

MAX_TOOL_ITERATIONS = 50


class AgentLoop:
    """Consume inbound messages, ask a provider, and publish outbound replies."""

    def __init__(
        self,
        bus: MessageBus,
        provider: BaseProvider | None = None,
        context_builder: ContextBuilder | None = None,
        tool_registry: ToolRegistry | None = None,
        trace_store: TraceStore | None = None,
        markdown_memory_store: MarkdownMemoryStore | None = None,
        memory_extractor: MemoryExtractor | None = None,
        skill_registry: SkillRegistry | None = None,
        workspace_root: Path | str | None = None,
        profile_loader: ProfileLoader | None = None,
        max_tool_iterations: int = MAX_TOOL_ITERATIONS,
        conversation_summary_config: ConversationSummaryConfig | None = None,
        cron_service: "CronService | None" = None,
        start_cron: bool = True,
    ) -> None:
        self.bus = bus
        self.provider = provider or create_provider()
        self.markdown_memory_store = markdown_memory_store or MarkdownMemoryStore()
        self.memory_extractor = memory_extractor or MemoryExtractor(
            self.provider,
            self.markdown_memory_store,
        )
        self.memory_consolidator = MemoryConsolidator(
            self.provider,
            self.markdown_memory_store,
        )
        self.cron_bridge = AgentCronBridge(self.bus, self.memory_consolidator)
        self.skill_registry = skill_registry or SkillRegistry.from_directory()
        self.profile_loader = profile_loader or ProfileLoader()
        self.conversation_summary_config = (
            conversation_summary_config or ConversationSummaryConfig()
        )
        self.conversation_summarizer = ConversationSummarizer(
            self.provider,
            self.conversation_summary_config,
        )
        self.trace_store = trace_store or JsonlTraceStore()
        self.events = AgentRunEvents(self.trace_store)
        self.skill_state = AgentSkillState(self.events)
        self.session_history = AgentSessionHistory(
            self.conversation_summarizer,
            self.conversation_summary_config,
            self.memory_extractor,
            self.events,
        )
        self.context_builder = context_builder or ContextBuilder(
            runtime_environment_provider=lambda: format_runtime_environment(workspace_root),
            always_memory_provider=self.markdown_memory_store.read_always_memory,
            now_memory_provider=self.markdown_memory_store.read_now_memory,
            conversation_summary_provider=self.session_history.current_summary_context,
            active_skills_provider=self.skill_state.current_active_skills_context,
            skill_registry=self.skill_registry,
            profile_provider=self.profile_loader,
        )
        if self.context_builder.always_memory_provider is None:
            self.context_builder.always_memory_provider = (
                self.markdown_memory_store.read_always_memory
            )
        if self.context_builder.now_memory_provider is None:
            self.context_builder.now_memory_provider = (
                self.markdown_memory_store.read_now_memory
            )
        if self.context_builder.conversation_summary_provider is None:
            self.context_builder.conversation_summary_provider = (
                self.session_history.current_summary_context
            )
        if self.context_builder.active_skills_provider is None:
            self.context_builder.active_skills_provider = (
                self.skill_state.current_active_skills_context
            )
        self.conversation_summarizer.chars_per_token = (
            self.context_builder.budget.chars_per_token
        )
        self.memory_compressor = VisibleMemoryCompressor(
            self.provider,
            self.markdown_memory_store,
            chars_per_token=self.context_builder.budget.chars_per_token,
        )
        self.tool_registry = tool_registry or create_default_registry()
        self._register_memory_tools()
        if not self.tool_registry.has("delegate_task"):
            self.tool_registry.register(DelegateTaskTool(self.provider, self.tool_registry))
        self.cron_service = cron_service or self._create_default_cron_service()
        if cron_service is not None:
            self.cron_service.on_job = self.cron_bridge.on_job
        self._start_cron = start_cron
        if not self.tool_registry.has("cron"):
            from myagent.tools.cron import CronTool
            self.tool_registry.register(CronTool(self.cron_service))
        if not self.tool_registry.has("message"):
            from myagent.tools.message import MessageTool
            self.tool_registry.register(MessageTool(send_callback=self.bus.publish_outbound))
        self.max_tool_iterations = max_tool_iterations
        self.tool_loop = AgentToolLoop(
            self.provider,
            self.tool_registry,
            self.bus,
            self.events,
            self.skill_state,
            self.max_tool_iterations,
        )
        self.turn_processor = AgentTurnProcessor(
            bus=self.bus,
            context_builder=self.context_builder,
            session_history=self.session_history,
            memory_compressor=self.memory_compressor,
            events=self.events,
            skill_state=self.skill_state,
            tool_registry=self.tool_registry,
            tool_loop=self.tool_loop,
            profile_loader=self.profile_loader,
            max_tool_iterations=self.max_tool_iterations,
        )
        self._lock = asyncio.Lock()
        self._running = False

    @property
    def running(self) -> bool:
        """Return whether the loop should keep processing messages."""
        return self._running

    @property
    def locked(self) -> bool:
        """Return whether a turn is currently being processed."""
        return self._lock.locked()

    async def process_next(self) -> OutboundMessage:
        """Process one inbound message and publish one outbound message."""
        inbound = await self.bus.consume_inbound()
        async with self._lock:
            return await self.process_message(inbound)

    async def process_message(self, inbound: InboundMessage) -> OutboundMessage:
        """Generate and publish an outbound response for one inbound message."""
        return await self.turn_processor.process_message(inbound)

    async def run_until_stopped(self) -> None:
        """Keep processing messages until stopped or cancelled."""
        self._running = True
        if self._start_cron:
            await self.cron_service.start()
            self.cron_bridge.register_memory_consolidation_job(self.cron_service)
        try:
            while self._running:
                await self.process_next()
        finally:
            if self._start_cron:
                self.cron_service.stop()

    def stop(self) -> None:
        """Request the processing loop to stop."""
        self._running = False

    def _create_default_cron_service(self):
        from myagent.cron.service import CronService
        store_path = Path.home() / ".myagent" / "runtime" / "cron" / "jobs.json"
        return CronService(
            store_path=store_path,
            on_job=self.cron_bridge.on_job,
        )

    def _register_memory_tools(self) -> None:
        """Expose local personal memory tools to the main agent."""
        tools = (
            MemoryRememberTool(self.markdown_memory_store),
            MemoryProposeTool(self.markdown_memory_store),
            MemoryArchiveTool(self.markdown_memory_store),
            MemorySearchTool(self.markdown_memory_store),
            MemoryGetTool(self.markdown_memory_store),
            MemoryForgetTool(self.markdown_memory_store),
        )
        for tool in tools:
            if not self.tool_registry.has(tool.name):
                self.tool_registry.register(tool)
        if self.skill_registry.list_skills() and not self.tool_registry.has("skill_get"):
            self.tool_registry.register(
                SkillGetTool(self.skill_registry, trace_hook=self.skill_state.trace_event)
            )

