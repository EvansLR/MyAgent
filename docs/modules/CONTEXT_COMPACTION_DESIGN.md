# Context Compaction Design

Date: 2026-05-20

## Goal

Keep long conversations runnable without turning context management into a
large policy system.

The design has one rule: compress the part that grows. Do not make unrelated
prompt sections compete in one budget pool.

## Current Problem

The current implementation treats system sections, memory, summary, skills, and
raw history as budgetable context sections. This makes the code harder to
explain because each source has a different lifecycle:

- System prompt is fixed by the developer.
- Skill summaries are small and mostly static.
- Memory grows slowly and is already maintained by memory tooling.
- Conversation summary grows with the session.
- Raw conversation history grows every turn and is the main context risk.

The old `history_token_ratio` / `compact_target_ratio` style also hides the
real policy behind percentages. The project does not need that complexity.

## Desired Model

Separate context sources by ownership and compaction behavior:

```text
Fixed system prompt
  developer-authored instructions and policies
  never compressed automatically

Visible memory
  MEMORY.md Always / Now
  compacted with an LLM when it exceeds memory_token_limit

Conversation summary
  session-local summary of older turns
  compacted with an LLM when it exceeds summary_token_limit

Raw history
  recent unsummarized user/assistant messages
  compacted into summary when it exceeds raw_history_token_limit
```

`ContextBuilder` should assemble these prepared inputs. It should not own the
policy for deciding when memory, summary, or history should be compressed.

## Non-Goals

- No system prompt compression.
- No section priority ladder.
- No soft/hard severity levels.
- No ranking tables or memory weight system in this phase.
- No vector store or retrieval redesign.
- No automatic deletion of memory merely because it is old.

## Configuration

Use explicit token limits instead of ratios:

```text
memory_token_limit
summary_token_limit
raw_history_token_limit
raw_history_target_tokens
keep_recent_messages
max_compression_rounds
```

Suggested first defaults:

```text
memory_token_limit = 6000
summary_token_limit = 2000
raw_history_token_limit = 12000
raw_history_target_tokens = 6000
keep_recent_messages = 8
max_compression_rounds = 2
```

These are local runtime limits, not model context-window claims. The purpose is
to keep the learning project fast, explainable, and predictable.

## Compression Loop

Memory and summary use the same simple control flow:

```text
if estimated_tokens(text) <= token_limit:
    keep text

repeat up to max_compression_rounds:
    text = await compress_with_llm(text, token_limit)
    if estimated_tokens(text) <= token_limit:
        keep text

truncate to token_limit
record warning / trace event
```

This avoids extra states such as "soft over", "hard over", "priority demotion",
or multiple fallback policies.

## Memory Handling

Visible memory is the only memory content injected into the model by default.
In the current code, that means:

```text
MEMORY.md
  ## Always
  ## Now
```

Archives and proposals are searchable or consolidatable state, not default
prompt context.

When visible memory exceeds `memory_token_limit`:

1. Ask the LLM to rewrite visible memory into the same `# Memory` markdown
   structure.
2. Preserve stable user preferences, standing collaboration rules, current
   project state, and open loops.
3. Merge duplicates and remove stale or low-value details.
4. Re-estimate tokens.
5. Repeat at most `max_compression_rounds`.
6. If still over limit, truncate and record a trace warning.

This prompt-time memory compression is separate from the existing 24-hour
`memory_consolidation` cron job. The cron job still merges
`MEMORY_PROPOSALS.md` into `MEMORY.md` and keeps memory healthy over time.

## Summary Handling

Conversation summary is session-local. It is not long-term memory.

When summary exceeds `summary_token_limit`:

1. Ask the LLM to rewrite the summary shorter.
2. Preserve decisions, user preferences relevant to this session, open tasks,
   project/module names, and important file paths.
3. Do not turn old user requests into current instructions.
4. Re-estimate tokens.
5. Repeat at most `max_compression_rounds`.
6. If still over limit, truncate and record a trace warning.

## Raw History Handling

Raw history is the main source of prompt growth.

When visible raw history exceeds `raw_history_token_limit`:

1. Choose an older chunk while preserving `keep_recent_messages`.
2. Run `MemoryExtractor` on that chunk so future-useful information can be
   written to archive or proposals.
3. Fold that chunk into the conversation summary.
4. If the updated summary exceeds `summary_token_limit`, run the summary
   compression loop.
5. Keep recent raw messages unchanged.

This keeps the current behavior's useful idea: before old raw history disappears
from prompt context, protect important information through memory proposals and
session summary.

## ContextBuilder Responsibility

After this redesign, `ContextBuilder` should be boring:

```text
fixed system prompt
+ visible memory
+ conversation summary
+ recent raw history
+ current user input
```

It may still produce trace reports with token estimates. It may also keep a
final provider-call safety check, but that check should be a last-resort
diagnostic, not the normal policy for dropping memory or summary.

## Module Boundaries

Proposed ownership:

- `ContextBuilder`: assemble already-prepared context into provider messages.
- `AgentSessionHistory`: own raw history and session summary state.
- `ConversationSummarizer`: summarize raw history and compress existing summary.
- `MarkdownMemoryStore`: read/write visible memory, proposals, and archive.
- `MemoryConsolidator`: merge proposals into visible memory on cron.
- `MemoryCompressor` or `VisibleMemoryCompactor`: compress visible memory when
  it exceeds `memory_token_limit`.
- `MemoryExtractor`: extract future-useful information from raw history chunks
  before they are folded into summary.

## Implementation Sequence

1. Add tests that describe the desired behavior before changing logic.
2. Introduce explicit config fields and keep old fields temporarily for
   compatibility.
3. Add shared compression-loop helper.
4. Add summary compression when summary exceeds `summary_token_limit`.
5. Add visible-memory compression when memory exceeds `memory_token_limit`.
6. Replace ratio-based history compaction with `raw_history_token_limit` and
   `raw_history_target_tokens`.
7. Simplify `ContextBuilder` so it assembles context and reports estimates
   instead of deciding section priority.
8. Remove old ratio fields and tests once behavior is covered.

## Test Strategy

Focused tests should cover:

- Memory under limit is unchanged.
- Memory over limit calls the LLM compressor and writes back compact memory.
- Memory still over limit after N rounds is truncated and traced.
- Summary under limit is unchanged.
- Summary over limit is compressed and state metadata is updated.
- Raw history over limit runs extractor before summary update.
- ContextBuilder no longer drops memory/summary as normal budget policy.
- Final assembled messages preserve fixed system prompt.

## Simple Explanation

System prompt is fixed. Memory and summary each have their own size limit. Raw
conversation history has its own size limit. When a part grows too large, that
part is compressed with the LLM; after a small number of attempts, it is
truncated with a trace warning. Nothing else is needed for the current project
stage.

## 2026-05-20 Implementation Notes

Implemented the first version of this design.

Files added:

- `myagent/agent/compression.py`
- `myagent/memory/compressor.py`

Files changed:

- `myagent/agent/context_types.py`
- `myagent/agent/context.py`
- `myagent/agent/loop.py`
- `myagent/agent/session_history.py`
- `myagent/agent/summary.py`
- `myagent/memory/__init__.py`

Important runtime behavior:

- `ContextBuilder` no longer drops memory, summary, skills, or other system
  sections as normal budget policy. It assembles context and reports estimates.
- Visible memory is compressed before context build when `MEMORY.md` exceeds
  `memory_token_limit`.
- Conversation summary is compressed when it exceeds `summary_token_limit`.
- Raw history is compacted when it exceeds `raw_history_token_limit`.
- Before raw history is folded into summary, `MemoryExtractor` still preserves
  future-useful information into archive/proposals.
- After raw history is successfully folded into summary, the folded messages are
  removed from the in-process raw history list. This prevents long-running
  processes from keeping invisible old history forever.
- If a custom `ContextBuilder` is injected, `AgentLoop` fills missing memory,
  summary, and active-skill providers so runtime context remains connected.

Verification:

```text
python -m pytest
268 passed
```
