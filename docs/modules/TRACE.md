# Trace 模块设计

## 职责

Trace 负责记录 MyAgent 每一轮运行过程中发生了什么。

一句话版本：

```text
Trace 用 JSONL 文件记录 user message、LLM 请求/响应、工具调用、工具结果、最终回答和错误。
```

它属于 `Observability Layer`。

## 为什么需要它

现在 MyAgent 已经能做到：

- CLI 对话
- 保留会话历史
- 调用真实 LLM
- 调用本地只读工具
- 展示工具调用状态

但如果出现问题，比如：

```text
为什么模型没有调用工具？
为什么调用了太多次工具？
为什么最终回答不符合预期？
上下文里到底发给模型了什么？
```

只看终端输出是不够的。

Trace 的作用是把 Agent 的内部过程落盘，方便：

- 调试
- 面试讲解
- 回放某一轮 turn
- 后续 Memory / Skills / MCP 接入时定位问题

## 第一阶段定位

第一阶段只做轻量 JSONL trace。

目标不是做完整观测平台，而是做到：

```text
能看
能解释
能排查问题
```

暂时不做：

- Web UI
- 可视化图表
- trace 搜索
- trace 压缩
- 跨进程集中采集
- OpenTelemetry
- SQLite trace store
- 自动脱敏
- token 统计

## 数据存储

默认目录：

```text
data/traces/
```

文件格式：

```text
data/traces/<session_key>.jsonl
```

因为 `session_key` 里可能包含冒号等不适合文件名的字符，所以真实文件名会做简单安全化，例如：

```text
cli_default.jsonl
cli_session-1.jsonl
```

每一行是一条 JSON 事件。

示例：

```json
{"ts":"2026-05-06T10:00:00.000000","session_key":"cli:default","turn_id":"...","event":"user_message","data":{"content":"帮我看看 docs 目录"}}
```

## 核心事件

第一版建议记录这些事件：

```text
user_message
context_built
llm_request
llm_response
tool_call
tool_result
final_answer
error
```

### user_message

用户输入进入 AgentLoop 时记录。

字段：

```text
channel
chat_id
content
```

### context_built

ContextBuilder 构造完 messages 后记录。

字段：

```text
message_count
roles
```

第一版不完整记录 system prompt 全文，避免 trace 文件太吵。

后续如果需要，可以加配置开关记录完整 messages。

### llm_request

调用 provider 前记录。

字段：

```text
message_count
tool_count
iteration
```

第一版不记录完整 API key、base_url 等敏感配置。

### llm_response

provider 返回后记录。

字段：

```text
content_preview
tool_call_count
tool_names
```

`content_preview` 只保留前一小段文本，避免 trace 太大。

### tool_call

执行工具前记录。

字段：

```text
tool_call_id
tool_name
arguments
```

### tool_result

工具执行完成后记录。

字段：

```text
tool_call_id
tool_name
result_preview
result_length
```

### final_answer

本轮最终回答发布前记录。

字段：

```text
content_preview
content_length
```

### error

AgentLoop 捕获异常时记录。

字段：

```text
message
type
```

第一版不记录完整 traceback，后续需要时再增加。

## 核心接口

建议新增：

```text
myagent/tracing/
  __init__.py
  events.py
  store.py
```

### TraceEvent

轻量数据结构：

```text
ts: str
session_key: str
turn_id: str
event: str
data: dict
```

### JsonlTraceStore

负责 append JSONL：

```text
record(session_key, turn_id, event, data) -> None
```

第一版使用同步文件写入即可，因为 trace 内容很小，代码更容易理解。

后续如果有性能问题，再改成异步队列。

## 与 AgentLoop 的关系

TraceStore 由 AgentLoop 持有。

流程：

```text
process_message
  -> trace user_message
  -> build context
  -> trace context_built
  -> llm request
  -> trace llm_request
  -> llm response
  -> trace llm_response
  -> tool_call / tool_result
  -> final_answer
```

Trace 不参与业务决策。

也就是说：

- Trace 不改变 LLM 输入
- Trace 不改变工具调用
- Trace 失败不应该影响主流程

如果 trace 写入失败，第一版可以吞掉异常，避免因为观测系统导致 Agent 不可用。

## 配置

第一版默认启用 trace。

后续可以加配置：

```json
{
  "trace": {
    "enabled": true,
    "dir": "data/traces",
    "includeMessages": false
  }
}
```

但第一版可以先不扩展 config 文件，直接使用默认目录。

原因：

- 当前项目目标是能跑、能讲。
- 默认 trace 对学习和调试有价值。
- `data/` 已经在 `.gitignore` 中，不会误提交本地 trace。

## 测试点

建议新增：

```text
tests/test_trace_store.py
tests/test_agent_trace.py
```

测试内容：

1. `JsonlTraceStore` 能创建 JSONL 文件。
2. record 多次会 append 多行。
3. session_key 会被转换成安全文件名。
4. AgentLoop 处理普通消息时会记录 user_message 和 final_answer。
5. AgentLoop 执行工具时会记录 tool_call 和 tool_result。
6. Provider 报错时会记录 error。

## 面试表达

可以这样讲：

> 我给 AgentLoop 增加了一个轻量 Trace 层，用 append-only JSONL 记录每一轮的关键事件，比如用户输入、上下文构建、模型请求、工具调用和最终回答。它不参与业务决策，只负责观测，所以即使 trace 写入失败也不应该影响主流程。这样在面试和调试时，可以直接打开 trace 文件解释 Agent 的 ReAct 过程。

如果面试官问“为什么不用 OpenTelemetry”，可以回答：

> OpenTelemetry 更适合生产系统的分布式观测。MyAgent 是学习和面试项目，第一阶段更需要一个可读、可解释、实现成本低的 trace 文件，所以先用 JSONL。后续如果要做服务化、多实例运行，再接 OpenTelemetry 也不晚。

## 后续扩展方向

后续可以增强：

- CLI 子命令 `myagent trace`
- `/trace` 查看最近一轮
- trace summary
- 记录完整 messages
- token 统计
- trace replay
- 错误 traceback
- trace 脱敏
- SQLite trace store
- Web UI 可视化

## 第一阶段实现记录

本阶段已经完成轻量 JSONL Trace。

新增/修改文件：

```text
myagent/tracing/__init__.py
myagent/tracing/events.py
myagent/tracing/store.py
myagent/agent/loop.py
tests/test_trace_store.py
tests/test_agent_trace.py
```

### 代码阅读顺序

建议按这个顺序看：

1. `myagent/tracing/events.py`
2. `myagent/tracing/store.py`
3. `myagent/agent/loop.py`
4. `tests/test_trace_store.py`
5. `tests/test_agent_trace.py`

`events.py` 定义 trace event 长什么样，`store.py` 负责写 JSONL，`AgentLoop` 负责在关键流程点调用 trace。

### TraceEvent

`TraceEvent` 是一条 trace 记录。

字段：

```text
ts
session_key
turn_id
event
data
```

`to_dict()` 会返回可 JSON 序列化的字典。

### JsonlTraceStore

`JsonlTraceStore` 负责把事件 append 到文件。

默认目录：

```text
data/traces
```

文件名来自 `session_key`，会做安全化。

例如：

```text
cli:default -> cli_default.jsonl
cli:session/with spaces -> cli_session_with_spaces.jsonl
```

写入方式是 append-only，每次 `record(...)` 追加一行 JSON。

### AgentLoop 接入点

`AgentLoop` 现在默认持有：

```python
JsonlTraceStore()
```

也可以在测试或后续配置里注入自定义 store：

```python
AgentLoop(bus, trace_store=JsonlTraceStore(".test-workspaces/traces"))
```

每次 `process_message` 会生成一个新的：

```text
turn_id
```

同一轮里的所有事件共享这个 `turn_id`。

当前记录事件：

```text
user_message
context_built
llm_request
llm_response
tool_call
tool_result
final_answer
error
```

### Trace 不影响主流程

AgentLoop 通过内部 `_trace(...)` 方法记录事件。

如果 trace 写入失败，会吞掉异常。

这样做是为了保证：

```text
观测系统不能把主聊天流程搞挂。
```

### 如何手动查看

运行：

```text
python -m myagent
```

然后进行一次对话。

默认可以查看：

```text
data/traces/cli_default.jsonl
```

每一行是一条 JSON 事件。你可以直接打开，也可以用命令按行查看。

### 测试说明

新增测试：

```text
tests/test_trace_store.py
tests/test_agent_trace.py
```

覆盖内容：

- JSONL 文件创建
- 多次 record 会 append 多行
- session_key 会转换成安全文件名
- 普通 turn 会记录 `user_message`、`context_built`、`llm_request`、`llm_response`、`final_answer`
- 工具 turn 会记录 `tool_call`、`tool_result`
- provider 报错会记录 `error`

验证结果：

```text
python -m pytest
55 passed
```

### 当前边界

当前 Trace 已经能记录主链路事实，但还没有：

- trace CLI 子命令
- `/trace`
- trace summary
- 完整 messages 记录
- traceback
- token 统计
- 配置开关
- 自动清理旧 trace

这些可以在后续按需补。
## Phase 2 Review

Trace has become more important after the AgentLoop, MCP, web, memory, skills,
and SubAgent upgrades. It now records enough events to diagnose most local runs,
but users still had to open JSONL files manually.

Current trace sources include:

- normal turn events:
  - `user_message`
  - `context_built`
  - `llm_request`
  - `llm_response`
  - `tool_call`
  - `tool_result`
  - `final_answer`
  - `turn_completed`
- memory events:
  - `memory_candidates_saved`
  - `memory_extraction_error`
- SubAgent events:
  - `subagent_start`
  - `subagent_tool_call`
  - `subagent_tool_result`
  - `subagent_result`
- runtime startup events:
  - `mcp_server_registered`
  - `mcp_server_connect_failed`

### Current Problem

The trace data is useful but not ergonomic:

- JSONL must be opened manually.
- It is hard to quickly find the latest turn.
- `turn_completed.stop_reason` is not surfaced in CLI.
- Tool loops and repeated-call warnings require hand-reading JSON.

### Phase 2 Direction

Do not build a web UI or full replay system yet. The smallest useful step is a
CLI trace inspect command:

```text
python -m myagent trace latest
python -m myagent trace show
```

Design goals:

- Read local JSONL trace files only.
- Do not modify trace files.
- Default to `data/traces` and `cli:default`.
- Show compact summaries rather than raw JSON dumps.
- Keep the implementation independent from AgentLoop behavior.

Deferred:

- Web UI
- SQLite trace store
- trace replay
- token accounting
- automatic cleanup
- full-message capture
- redaction policy
- OpenTelemetry integration

## Phase 2A Implementation Notes

Changed files:

- `myagent/tracing/inspect.py`
- `myagent/tracing/__init__.py`
- `myagent/cli/commands.py`
- `tests/test_trace_store.py`
- `tests/test_cli_channel.py`
- `docs/modules/TRACE.md`
- `docs/NEXT_STEPS.md`

Implemented:

- `read_trace_events(session_key, trace_root)`
- `summarize_turns(events)`
- `latest_turn_summary(events)`
- `format_turn_summary(summary)`
- `format_trace_events(events, limit)`
- CLI command:
  - `python -m myagent trace latest`
  - `python -m myagent trace show`
  - `python -m myagent trace context`
  - `python -m myagent trace report`
  - `python -m myagent trace viewer`
  - `python -m myagent trace skills`
  - `python -m myagent trace startup`

Default behavior:

```text
python -m myagent trace latest
```

reads:

```text
data/traces/cli_default.jsonl
```

and prints a compact latest-turn summary:

```text
turn_id: ...
events: ...
event_names: ...
stop_reason: final_output
iterations: 2
tool_calls: 1
tool_errors: 0
warnings: 0
```

Recent event view:

```text
python -m myagent trace show --limit 20
```

prints compact event rows:

```text
turn-id user_message - ...
turn-id tool_call - read_file
turn-id turn_completed - final_output
```

Runtime skill event view:

```text
python -m myagent trace skills --limit 20
```

reads:

```text
data/traces/runtime_skills.jsonl
```

and prints compact rows such as:

```text
skills skill_loaded - frontend-design len=123
skills active_skill_set - frontend-design scope=turn reason=loaded_by_skill_get
```

Startup event view:

```text
python -m myagent trace startup --limit 20
```

reads:

```text
data/traces/runtime_startup.jsonl
```

and prints compact rows such as:

```text
startup mcp_server_registered - didi-mcp http tools=13/13
```

Context assembly view:

```text
python -m myagent trace context
```

reads the latest `context_built` event from:

```text
data/traces/cli_default.jsonl
```

and prints the ContextBuilder report in a readable shape:

```text
turn_id: ...
message_count: 3
estimated_tokens: 1200
total_chars: 4800
history: 2/4 included, 2 dropped
warnings: history_trimmed
sections:
- Identity: tier=protected, source=identity, tokens=25, chars=100, included=yes
- Runtime Environment: tier=protected, source=runtime:environment, ...
- Available Skills: tier=medium, source=skills:summary, ...
```

This is different from `trace latest`: `trace latest` summarizes the turn result,
while `trace context` explains what went into the model context before the
provider call.

Static HTML report:

```text
python -m myagent trace report
```

writes:

```text
data/traces/report.html
```

The report is a self-contained local page. It reads the same JSONL trace files
and presents:

- latest turn summary
- ContextBuilder sections and token estimates
- recent skill events
- MCP startup events
- recent session event stream

This is intentionally not a web server or dashboard app. For the current phase,
a static report is enough to make trace analysis easier without introducing a
frontend build pipeline, database, or long-running local service.

Interactive local viewer:

```text
python -m myagent trace viewer
```

writes:

```text
data/traces/viewer.html
```

The viewer is different from `trace report`:

- `trace report` renders the current known trace files into one fixed report.
- `trace viewer` is an interactive local page.
- The user opens the page and selects one or more saved JSONL files.
- The browser parses the selected files locally and displays Context, Skills,
  Startup, Events, and Raw JSON views.

Recommended files to load together:

```text
data/traces/cli_default.jsonl
data/traces/runtime_skills.jsonl
data/traces/runtime_startup.jsonl
```

This better matches real analysis because the user can compare different saved
trace files without regenerating a report for each combination.

Options:

```text
--session cli:default
--trace-dir data/traces
--limit 20
```

Runtime convenience commands intentionally do not change trace storage. They only
avoid requiring users to remember internal session keys such as
`runtime:skills` and `runtime:startup`.

Important Typer detail:

- The root callback now checks `ctx.invoked_subcommand`.
- This prevents `python -m myagent trace latest` from also starting the chat
  loop.

Verification:

```text
python -m pytest tests/test_trace_store.py tests/test_cli_channel.py
21 passed
```
