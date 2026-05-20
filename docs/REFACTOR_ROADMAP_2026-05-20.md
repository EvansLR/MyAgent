# Refactor Roadmap: Complexity and Redundancy Reduction

Date: 2026-05-20

## Goal

Reduce implementation complexity and duplicated code without changing current
runtime behavior.

This roadmap is intentionally staged. Each step should be small enough to review
and verify independently.

## Current Pain Points

1. `AgentLoop` still owns several responsibilities:
   - dependency assembly for tools, memory, cron, skills, trace, and context
   - turn lifecycle and history updates
   - model/tool iteration
   - special `delegate_task` tracing
   - cron system-job routing
   - active skill context formatting

2. Main-agent and subagent tool-call loops duplicate provider message helpers:
   - `_assistant_tool_call_message`
   - `_tool_result_message`

3. Filesystem copy and move tools repeat the same validation, overwrite, path
   access, and destination-directory logic.

4. CLI startup and gateway startup repeat similar runtime assembly:
   - settings
   - bus
   - workspace root
   - default registry
   - trace store
   - MCP connection
   - `AgentLoop` construction

5. Some docs and user-facing Chinese strings appear mojibake when read from the
   current shell. Treat this as a separate cleanup from behavior-preserving
   refactors, because fixing it may change visible text.

## Target Shape

Keep the project learning-friendly:

- small modules with obvious ownership
- no workflow graph runtime
- no large framework-style dependency container
- no behavior changes hidden inside refactors

Preferred module boundaries:

- `agent/messages.py`: shared chat-completions message helpers.
- `agent/tool_loop.py`: bounded provider/tool iteration for main and child
  agents, if the first helper extraction is not enough.
- `agent/skills_state.py`: active skill tracking and formatting.
- `agent/cron_bridge.py`: system cron job handling and user cron message
  routing.
- `tools/file_operations.py`: shared copy/move validation and execution helpers.
- `cli/runtime.py`: shared CLI/gateway runtime assembly.

## Refactor Sequence

### Phase 1: Extract Shared Tool Message Helpers

Move duplicated provider message helpers from `agent/loop.py` and
`agent/subagent.py` into `agent/messages.py`.

Checkpoint:

- `tests/test_agent_loop.py`
- `tests/test_subagent.py`
- `tests/test_agent_trace.py`

Expected risk: low. This is a pure move with import rewiring.

### Phase 2: Extract Active Skill Turn State

Move `_active_skills_by_turn`, `_trace_skill_event`,
`_active_skill_ids_for_turn`, `_current_active_skills_context`, and
`_format_active_skill_context` into a small `AgentSkillState` class.

Checkpoint:

- `tests/test_agent_skills.py`
- `tests/test_subagent.py`
- `tests/test_context_builder.py`

Expected risk: medium-low. Behavior is trace-sensitive, so keep trace event names
and payloads unchanged.

### Phase 3: Extract Cron Bridge from AgentLoop

Move memory-consolidation registration and `_on_cron_job` into a focused bridge
object that receives:

- `cron_service`
- `memory_consolidator`
- `bus`
- a callable for publishing scheduled inbound messages

Checkpoint:

- `tests/test_cron_service.py`
- `tests/test_cron_tool.py`
- `tests/test_agent_memory.py`
- focused gateway smoke test if available

Expected risk: medium. Cron routing is user-visible and includes channel/chat
preservation.

### Phase 4: Deduplicate Filesystem Copy/Move

Introduce a private helper for shared source/destination validation and approval.
Keep `copy_file` and `move_file` public schemas and result strings stable unless
tests are updated to lock a clearer shared format.

Checkpoint:

- `tests/test_filesystem_tools.py`

Expected risk: medium-low. The behavior surface is broad but well covered.

### Phase 5: Share Runtime Assembly Between CLI and Gateway

Extract common setup from `run_local_chat` and `run_gateway`:

- settings loading stays at the command boundary
- registry, trace store, MCP connection, provider, and `AgentLoop` construction
  move into a helper
- CLI and gateway still own their distinct channel lifecycle

Checkpoint:

- `tests/test_cli_channel.py`
- `tests/test_channels_manager.py`
- `tests/test_channels_feishu.py`
- manual `python -m myagent --help` / `python -m myagent trace latest`

Expected risk: medium. Startup code is integration-heavy.

## Guardrails

- Run focused tests after each phase.
- Avoid renaming public tools or trace event names during the first pass.
- Avoid changing user-facing messages unless the phase is explicitly about text
  cleanup.
- Keep each phase independently revertible.
- Update the touched module doc after each implementation phase.

## Deferred Work

- Larger `AgentLoop` turn-state-machine redesign.
- Tool permission policy redesign.
- Any production dependency injection framework.
- Docs-only mojibake cleanup. The affected docs are user-maintained notes and
  are intentionally out of scope for this engineering refactor.

## Implementation Notes

Implemented on 2026-05-20.

Files added:

- `myagent/agent/messages.py`
- `myagent/agent/skill_state.py`
- `myagent/agent/cron_bridge.py`
- `myagent/cli/runtime.py`

Files changed:

- `myagent/agent/loop.py`
- `myagent/agent/subagent.py`
- `myagent/tools/filesystem.py`
- `myagent/cli/commands.py`
- `docs/modules/AGENT_LOOP.md`

Important behavior notes:

- Main-agent and subagent tool-call message construction now share one helper
  module.
- Active skill tracking moved behind `AgentSkillState`, while trace event names
  and context text format are preserved.
- Cron routing moved behind `AgentCronBridge`; scheduled user jobs still publish
  inbound messages with `session_key_override=f"cron:{job.id}"`.
- Filesystem copy/move now share validation and approval checks.
- CLI and gateway startup now share provider, registry, trace, MCP, and
  `AgentLoop` assembly through `create_agent_runtime`.
- The scheduled-task instruction text was restored from mojibake into clear
  English during the cron extraction because the copied mojibake was syntactically
  invalid in the new file.

Verification:

```text
python -m pytest tests/test_agent_loop.py tests/test_subagent.py tests/test_agent_trace.py
python -m pytest tests/test_agent_skills.py tests/test_subagent.py tests/test_context_builder.py
python -m pytest tests/test_cron_service.py tests/test_cron_tool.py tests/test_agent_memory.py
python -m pytest tests/test_filesystem_tools.py
python -m pytest tests/test_cli_channel.py tests/test_channels_manager.py tests/test_channels_feishu.py
python -m pytest

266 passed
```

## Follow-up Refactor: Runtime Boundary Cleanup

Planned after the first cleanup pass.

Scope:

- Keep public commands, tool names, trace event names, and provider interfaces
  stable.
- Do not edit user-maintained docs solely for encoding or mojibake cleanup.
- Prefer small owner modules over a framework-style dependency container.

Phases:

1. Extract one-turn orchestration from `AgentLoop`, leaving `AgentLoop` focused
   on queue consumption, locking, and lifecycle.
2. Extract the bounded provider/tool iteration and delegate-task special case
   into focused runtime helpers.
3. Split Feishu rendering/card construction from the channel lifecycle.
4. Make smaller cleanups in context assembly, filesystem helpers, and trace CLI
   commands only after the higher-risk runtime split is verified.

Checkpoints:

- `python -m pytest tests/test_agent_loop.py tests/test_agent_trace.py tests/test_agent_memory.py tests/test_agent_skills.py tests/test_subagent.py`
- `python -m pytest tests/test_channels_feishu.py tests/test_channels_manager.py`
- `python -m pytest tests/test_context_builder.py tests/test_filesystem_tools.py tests/test_cli_channel.py tests/test_trace_store.py`

Implementation notes:

- Added `myagent/agent/turn_processor.py` to own one-turn context preparation,
  final reply publication, history updates, and visible-memory compression.
- Added `myagent/agent/tool_loop.py` to own bounded provider/tool iteration,
  tool status messages, repeated-tool diagnostics, and `delegate_task` trace
  handling.
- Reduced `AgentLoop` to lifecycle responsibilities: dependency assembly,
  inbound queue consumption, locking, cron startup, and stop control.
- Added `myagent/channels/feishu_rendering.py` for approval card and
  Markdown-ish text rendering, leaving `FeishuChannel` focused on channel
  lifecycle, token handling, transport, upload, and event routing.
- Kept public tool names, trace event names, provider behavior, Feishu card
  content, and test-visible helper imports stable.

Verification:

```text
python -m pytest tests/test_agent_loop.py tests/test_agent_trace.py tests/test_agent_memory.py tests/test_agent_skills.py tests/test_subagent.py
33 passed

python -m pytest tests/test_channels_feishu.py tests/test_channels_manager.py
27 passed

python -m pytest tests/test_agent_loop.py tests/test_agent_trace.py tests/test_agent_memory.py tests/test_agent_skills.py tests/test_subagent.py tests/test_channels_feishu.py tests/test_channels_manager.py
60 passed

python -m pytest
268 passed
```

## Follow-up Refactor: Agent Package Structure Cleanup

Implemented after the context builder boundary cleanup.

Goal:

- Reduce top-level `myagent/agent` clutter without merging responsibilities back
  into large files.
- Keep `myagent.agent` as the public facade for common imports such as
  `AgentLoop`, `ContextBuilder`, `ContextBudget`, and `DelegateTaskTool`.

New package shape:

```text
myagent/agent/
  __init__.py
  loop.py
  context/
    builder.py
    sections.py
    selection.py
    types.py
    summary.py
    compression.py
  runtime/
    turn_processor.py
    tool_loop.py
    session_history.py
    cron_bridge.py
    skill_state.py
    run_events.py
    messages.py
    env.py
  delegation/
    subagent.py
```

Implementation notes:

- Moved context assembly, summary, compression, and context data structures into
  `myagent.agent.context`.
- Moved one-turn processing, tool loop, trace events, session history, active
  skill state, cron bridge, message helpers, and runtime environment formatting
  into `myagent.agent.runtime`.
- Moved subagent delegation into `myagent.agent.delegation`.
- Updated internal imports and test imports to use the new package paths.
- Kept the top-level `myagent.agent` exports intact for the common public API.

Verification:

```text
python -m compileall -q myagent/agent

python -m pytest tests/test_agent_loop.py tests/test_agent_trace.py tests/test_agent_memory.py tests/test_agent_skills.py tests/test_subagent.py tests/test_context_builder.py
50 passed

python -m pytest
268 passed
```

## Follow-up Refactor: Context Builder Boundary Cleanup

Implemented after the runtime boundary cleanup.

Scope:

- Preserve `ContextBuilder` public construction and `build_messages_with_report`
  behavior.
- Keep the current prompt-time budgeting behavior: sections and history are not
  dropped solely because `max_prompt_tokens` is exceeded; the report records the
  warning instead.
- Do not alter Feishu or user-maintained docs in this phase.

Implementation notes:

- Added `myagent/agent/context_sections.py` to own ordered system section
  assembly for identity, profile, runtime environment, delegation policy,
  visible memory, conversation summary, active skills, and available skills.
- Added `myagent/agent/context_selection.py` to own section item conversion,
  system prompt rendering, history selection, token estimation, warning
  aggregation, and report construction.
- Kept compatibility methods on `ContextBuilder` as thin wrappers so existing
  tests and nearby modules do not need to know about the extracted helpers.
- Added a small sync step before section assembly because `AgentLoop` may attach
  memory, summary, and active skill providers to an injected `ContextBuilder`
  after construction.

Verification:

```text
python -m pytest tests/test_context_builder.py tests/test_agent_loop.py tests/test_agent_trace.py tests/test_agent_memory.py tests/test_subagent.py
47 passed

python -m pytest
268 passed
```
