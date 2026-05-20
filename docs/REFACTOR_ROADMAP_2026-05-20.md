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

- Mojibake cleanup for docs and Chinese user-facing strings.
- Larger `AgentLoop` turn-state-machine redesign.
- Tool permission policy redesign.
- Any production dependency injection framework.

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
