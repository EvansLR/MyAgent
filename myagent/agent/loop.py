"""Minimal agent loop for processing messages from the bus."""

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

from myagent.agent.context import ContextBuilder
from myagent.agent.context.runtime import AgentContextRuntime
from myagent.agent.delegation.subagent import DelegateTaskTool
from myagent.agent.context.summary import ConversationSummaryConfig
from myagent.agent.runtime.cron_bridge import AgentCronBridge
from myagent.agent.runtime.tool_loop import AgentToolLoop
from myagent.agent.runtime.turn_processor import AgentTurnProcessor
from myagent.bus import InboundMessage, MessageBus, OutboundMessage
from myagent.memory import AgentMemoryServices, MarkdownMemoryStore
from myagent.memory.extractor import MemoryExtractor
from myagent.providers import BaseProvider, create_provider
from myagent.profile import ProfileLoader
from myagent.skills import SkillRegistry
from myagent.tools.context import ApprovalCallback
from myagent.tools import (
    ToolRegistry,
    create_default_registry,
)

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
        markdown_memory_store: MarkdownMemoryStore | None = None,
        memory_extractor: MemoryExtractor | None = None,
        skill_registry: SkillRegistry | None = None,
        workspace_root: Path | str | None = None,
        profile_loader: ProfileLoader | None = None,
        max_tool_iterations: int = MAX_TOOL_ITERATIONS,
        conversation_summary_config: ConversationSummaryConfig | None = None,
        cron_service: "CronService | None" = None,
        start_cron: bool = True,
        approval_callback: ApprovalCallback | None = None,
    ) -> None:
        self.bus = bus
        self.provider = provider or create_provider()
        self.memory_services = AgentMemoryServices.create(
            self.provider,
            store=markdown_memory_store,
            extractor=memory_extractor,
        )
        self.markdown_memory_store = self.memory_services.store
        self.memory_extractor = self.memory_services.extractor
        self.memory_consolidator = self.memory_services.consolidator
        self.memory_compressor = self.memory_services.compressor
        self.cron_bridge = AgentCronBridge(self.bus, self.memory_consolidator)
        self.context_runtime = AgentContextRuntime.create(
            self.provider,
            memory=self.memory_services,
            builder=context_builder,
            skill_registry=skill_registry,
            workspace_root=workspace_root,
            profile_loader=profile_loader,
            summary_config=conversation_summary_config,
        )
        self.skill_registry = self.context_runtime.skill_registry
        self.profile_loader = self.context_runtime.profile_loader
        self.conversation_summary_config = self.context_runtime.summary_config
        self.conversation_summarizer = self.context_runtime.summarizer
        self.skill_state = self.context_runtime.skill_state
        self.session_history = self.context_runtime.session_history
        self.context_builder = self.context_runtime.builder
        self.tool_registry = tool_registry or create_default_registry()
        self.approval_callback = approval_callback
        self._register_runtime_tools()
        if not self.tool_registry.has("delegate_task"):
            self.tool_registry.register(DelegateTaskTool(self.provider, self.tool_registry))
        self.cron_service = cron_service or self._create_default_cron_service()
        if cron_service is not None:
            self.cron_service.on_job = self.cron_bridge.on_job
        self._start_cron = start_cron
        if not self.tool_registry.has("cron"):
            from myagent.tools.cron import CronTool
            self.tool_registry.register(CronTool(self.cron_service))
        self.max_tool_iterations = max_tool_iterations
        self.tool_loop = AgentToolLoop(
            self.provider,
            self.tool_registry,
            self.bus,
            self.max_tool_iterations,
            approval_callback=self.approval_callback,
        )
        self.turn_processor = AgentTurnProcessor(
            bus=self.bus,
            context_builder=self.context_builder,
            session_history=self.session_history,
            memory_compressor=self.memory_compressor,
            skill_state=self.skill_state,
            tool_loop=self.tool_loop,
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
    # the only place that model processing happens is in process_message, 
    # which is protected by the lock, 
    # so this indicates whether we're waiting for a provider response
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

    def _register_runtime_tools(self) -> None:
        """Expose module-owned tools to the main agent."""
        self.memory_services.register_tools(self.tool_registry)
        self.context_runtime.register_skill_tools(self.tool_registry)

