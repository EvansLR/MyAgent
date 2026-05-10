# ContextBuilder 模块设计

## 职责

ContextBuilder 负责把 Agent 运行时信息组装成 LLM 能理解的 `messages`。

一句话版本：

```text
ContextBuilder 把 Identity、Memory、Skills、Tools、Conversation 等上下文分区组装成模型请求。
```

## 为什么需要它

当前 OpenAICompatibleProvider 直接拼：

```text
system prompt + 当前用户消息
```

这能完成单轮问答，但有几个问题：

1. 没有 conversation history，模型不知道上一轮说过什么。
2. system prompt、memory、skills、tools 混在一起后不好扩展。
3. 后续做 token budget 时没有 section 边界。
4. AgentLoop 和 Provider 都不应该负责上下文拼装。

引入 ContextBuilder 后：

```text
AgentLoop -> ContextBuilder -> Provider
```

Provider 只负责发送模型请求，ContextBuilder 负责组织上下文。

## 参考 NanoBot 的取舍

NanoBot 的 ContextBuilder 已经包含很多能力：

- Identity
- Bootstrap files
- Memory
- Retrieved memory
- Skills summary
- Active skills
- Task plan
- Budget tier
- Runtime context
- Media message
- Tool result message

MyAgent 第一阶段只保留骨架：

- Identity section
- Memory section 占位
- Skills section 占位
- Tools section 占位
- Conversation history
- 当前用户消息

暂不实现：

- bootstrap 文件
- active memory
- skills 扫描
- tools schema 注入
- media
- token budget
- tool result 回灌

这样既模仿 NanoBot 的分区思想，又不会一开始做太复杂。

## 所属架构层

ContextBuilder 属于 `Intelligence Layer`。

它位于：

```text
AgentLoop
  ↓
ContextBuilder
  ↓
LLM Provider
```

对应数据流：

```text
InboundMessage
  ↓
AgentLoop
  ↓ session history
ContextBuilder
  ↓ messages
Provider
  ↓ assistant text
AgentLoop
```

## 核心概念

### ContextSection

ContextSection 表示 system prompt 的一个分区。

建议字段：

```text
name: str
content: str
priority: int
```

第一阶段 priority 暂时只记录，不做预算裁剪。

后续可以升级为类似 NanoBot 的 tier：

```text
PROTECTED
HIGH
MEDIUM
LOW
```

### Conversation

Conversation 是模型可见的历史消息。

第一阶段格式：

```text
[
  {"role": "user", "content": "..."},
  {"role": "assistant", "content": "..."}
]
```

AgentLoop 在每轮完成后追加：

```text
user -> assistant
```

### Session History

第一阶段先放在 AgentLoop 内存里：

```text
dict[session_key, list[dict[str, str]]]
```

它不是最终 SessionManager，只是为了让多轮对话能工作。

后续可以独立成 Session 模块。

## 核心接口

### ContextBuilder

第一阶段接口：

```text
build_messages(
    current_message: InboundMessage,
    history: list[dict[str, str]],
) -> list[dict[str, str]]
```

返回值示例：

```text
[
  {"role": "system", "content": "...section prompt..."},
  *history,
  {"role": "user", "content": current_message.content}
]
```

### build_system_prompt

```text
build_system_prompt() -> str
```

第一阶段将 sections 用分隔符拼起来：

```text
# Identity
...

---

# Memory
...
```

如果某个 section 为空，可以跳过或输出占位说明。第一阶段建议只输出有意义内容，并保留 section 标题。

## 第一阶段 section

### Identity

当前默认：

```text
You are MyAgent, a lightweight ReAct agent runtime for learning and interview practice.
Be concise, helpful, and honest about current limitations.
```

### Memory

第一阶段占位：

```text
No memory module is connected yet.
```

但可以先不注入，避免给模型噪音。

### Skills

第一阶段占位，暂不注入。

### Tools

第一阶段占位，暂不注入。

### Conversation

注入真实历史。

这一步是当前最有价值的能力，因为它让 MyAgent 从单轮回复变成多轮对话。

## Provider 接口调整

当前 Provider 接口是：

```text
generate(message: InboundMessage) -> str
```

接入 ContextBuilder 后建议改成：

```text
generate(messages: list[dict[str, str]]) -> str
```

这样 Provider 不再负责拼 system/user。

EchoProvider 可以简单取最后一条 user message：

```text
Echo: <last user content>
```

OpenAICompatibleProvider 直接把 messages 传给 Chat Completions。

## 与其他模块的关系

### AgentLoop

AgentLoop 持有 ContextBuilder。

每次处理 inbound：

1. 取 session history。
2. 调用 ContextBuilder 生成 messages。
3. 调用 provider。
4. 把 user/assistant 追加到 history。

### Provider

Provider 接收 messages，不再关心 MessageBus 或 InboundMessage。

### Memory / Skills / Tools

第一阶段只是预留 section。

后续对应模块完成后，ContextBuilder 负责把它们接入 system prompt。

## 第一阶段范围

第一阶段只实现：

- `ContextSection`
- `ContextBuilder`
- `build_system_prompt`
- `build_messages`
- AgentLoop 内存 session history
- Provider 接口改为 messages
- EchoProvider 兼容 messages
- OpenAICompatibleProvider 发送 messages

## 暂不实现

第一阶段暂不实现：

- token budget
- section 压缩
- bootstrap 文件
- memory 召回
- skills 扫描
- tools schema
- media
- tool result message
- 持久化 session

## 最小测试点

建议测试文件：

```text
tests/test_context_builder.py
```

测试点：

1. `test_context_builder_builds_system_prompt`
   - system prompt 包含 MyAgent identity。

2. `test_context_builder_builds_messages_with_history`
   - messages 顺序是 system -> history -> current user。

3. `test_agent_loop_adds_turn_to_history`
   - 处理一轮后 session history 包含 user 和 assistant。

4. `test_echo_provider_uses_last_user_message`
   - EchoProvider 从 messages 里取最后一条 user。

5. `test_openai_provider_sends_built_messages`
   - fake client 收到 ContextBuilder 生成的 messages。

## 面试表达

可以这样讲：

> 我把上下文构建从 Provider 和 AgentLoop 中拆出来，形成 ContextBuilder。它用分区方式组织 Identity、Memory、Skills、Tools 和 Conversation。第一阶段只接 Identity 和 Conversation，但保留 section 边界，后续做 memory、skills、tool schema 或 token budget 时不需要推翻结构。

如果面试官问“为什么现在不做 budget”，可以回答：

> 当前项目目标是先跑通核心链路。Budget-aware composer 需要 token 估算、section 降级、压缩策略，复杂度较高。我先保留 ContextSection 和 priority 字段，等 Memory/Skills/Tools 接入后再做预算更有意义。

## 后续扩展方向

后续可以增强：

- Budget tier：PROTECTED / HIGH / MEDIUM / LOW
- Memory section
- Retrieved memory section
- Skills summary section
- Active skills section
- Tools schema section
- Runtime metadata
- Trace 记录 context stats
- 持久化 session history
- Token-aware truncation

## Phase 2 Review

ContextBuilder 第二轮不应只是继续追加 section，而应升级为更明确的 context composer。

详细外部调研见：

```text
docs/modules/CONTEXT_BUILDER_PHASE2_RESEARCH.md
```

本轮参考对象包括：

- OpenClaw Context
- OpenAI Agents SDK Sessions / context engineering cookbook
- Claude Code context window / compaction
- LangGraph short-term / long-term memory

### 当前实现状态

当前 `ContextBuilder` 已经接入：

- `Identity`
- `Core Memory`
- `Available Skills`
- conversation history
- current user message

当前 `AgentLoop` 会记录：

```text
context_built
  message_count
  roles
```

### 当前问题

- 没有 context size / token estimate。
- 没有 section-level report。
- 没有 history selection policy。
- 没有 budget 对象。
- 没有区分 protected / high / medium / low / ephemeral context。
- 没有记录 tool schema context cost。
- 没有为后续 compaction / memory flush 留明确 hook。

### Phase 2 目标

第二轮建议目标：

```text
从“简单拼接 system prompt”
升级为
“可观测、可分层、可预算、可扩展的 context composer”
```

最小实现建议：

1. 新增 `ContextBudget`。
2. 新增 `ContextAssemblyReport`。
3. `ContextSection` 增加 `tier` 和 `source`。
4. 新增 `build_messages_with_report(...)`，保留旧 `build_messages(...)` 兼容调用。
5. 实现 deterministic history selection，例如默认只保留最近 20 条 history message。
6. AgentLoop 把 report 写入 `context_built` trace。
7. tests 覆盖 section report、history trimming、Core Memory tier、trace 统计。

### 暂不实现

本轮暂不直接实现：

- 模型摘要式 compaction。
- pre-compaction memory flush。
- `/context` CLI 命令。
- 精确 tokenizer。
- persistent SessionManager。

这些不是放弃，而是等 ContextBuilder v2 的 report / budget / history selection 稳定后，再按正常节奏接入。

### Deferred Until Real Trigger Points

以下能力必须保留在路线图里，但不在当前 ContextBuilder v2A 直接实现：

```text
context compaction
pre-compaction memory flush
tool output pruning
/context inspect
summary persistence
```

暂缓原因不是优先级低，而是它们需要几个 pipeline 先出现真实触发点：

- Skills v2：skill 摘要、active skill、完整 skill 内容加载会带来新的 context 成本。
- Tools pipeline：tool result 和 tool schema 需要进入 context report，才能判断裁剪顺序。
- SubAgent pipeline：子 Agent 内部上下文、返回 summary、trace tree 会影响主上下文设计。
- Session history：history 规模变大后，才需要摘要式 compaction 和持久化 summary。
- Memory pipeline：pre-compaction flush 需要和 daily / DREAMS / MemoryExtractor 的写入策略对齐。

触发条件建议：

```text
当出现以下任一情况，再进入 compaction 设计：
- history trimming 开始丢失用户仍然关心的信息
- tool result 明显污染或撑爆 context
- active skill 内容开始占用大量 prompt
- SubAgent result 需要长期保留但不适合塞进主 history
- ContextAssemblyReport 显示 prompt 预算经常接近上限
```

到那时再设计：

```text
before_compaction:
  optional memory flush
  tool output pruning
  transcript summary
  summary injection
  trace compaction report
```

### 和 Memory 的边界

Memory v2 已经规定：

```text
MEMORY.md 的 Core Memory / User Profile / Active Goals
  -> 默认注入 context

daily / DREAMS / searchable memory
  -> 不默认注入
  -> 通过 memory tools 按需查询
```

ContextBuilder v2 应保持这个边界，并把 Core Memory 标为高优先级 section。

### 推荐下一步

下一步先实现 ContextBuilder v2 的 report 和 history selection，不急着做压缩：

```text
ContextBudget
ContextSection tier/source
ContextAssemblyReport
build_messages_with_report
AgentLoop trace 增强
focused tests
```

### Phase 2A Implementation Notes

本阶段已经落地 ContextBuilder v2 的最小可观测 composer。

新增能力：

```text
ContextTier
  protected / high / medium / low / ephemeral

ContextBudget
  max_prompt_tokens
  max_history_messages
  chars_per_token

ContextAssemblyReport
  total_chars
  estimated_tokens
  message_count
  sections
  history
  warnings

build_messages_with_report(...)
  返回 messages 和 report
```

当前默认 history 策略：

```text
max_history_messages = 20
```

如果 history 超过上限，只保留最近消息，并在 report 中记录：

```text
history.total_messages
history.included_messages
history.dropped_messages
warnings: ["history_trimmed"]
```

`AgentLoop` 已改为调用 `build_messages_with_report(...)`，并把 report 写入 `context_built` trace：

```text
context_built:
  message_count
  roles
  context:
    total_chars
    estimated_tokens
    sections
    history
    warnings
```

旧 `MemoryRecall` 主路径已彻底移除：

- `ContextBuilder` 不再接受 `memory_recall`。
- `AgentLoop` 不再记录旧 `memory_recalled`。
- `myagent/memory/recall.py` 和 `tests/test_memory_recall.py` 已删除。

当前 focused verification：

```text
python -m pytest tests/test_context_builder.py tests/test_agent_trace.py
9 passed
```

全量验证：

```text
python -m pytest
88 passed, 1 skipped
```

后续不要忘记：

```text
ContextBuilder v2A 做的是 report / tier / budget / history selection。
Compaction 不是取消，而是等 Skills / Tools / SubAgent / Session pipeline 形成真实压力后再做。
```

### Required Follow-Up: Runtime Environment Section

本地测试发现：当用户让 Agent 做前端 HTML 页面时，模型在触发 `frontend-design` skill 后调用了：

```text
list_dir path=/Users/liuguanglin/workspace/claude-didi-9527
```

但当前实际运行环境是 Windows / PowerShell / `E:\ClaudeCode\openSource\MyAgent`。

这说明 ContextBuilder 还缺少基础运行环境信息，导致模型可能凭空猜测 macOS/Linux 风格路径。

后续必须新增：

```text
# Runtime Environment

- OS: Windows
- Shell: PowerShell
- Workspace root: E:\ClaudeCode\openSource\MyAgent
- Path style: Windows paths
- Prefer relative paths such as "." unless the user gives an explicit path.
- Filesystem tools resolve relative paths inside the workspace root.
- Common personal folder aliases such as Desktop, Downloads, Documents, and 桌面 are recognized.
- Read-only filesystem operations do not require approval.
- Mutating filesystem operations outside the workspace require explicit user approval from the current channel.
- Do not invent absolute paths.
```

建议实现：

```text
ContextBuilder(runtime_environment=...)
ContextSection(name="Runtime Environment", tier=protected/high, source="runtime:environment")
```

来源：

- `platform.system()`
- `Path.cwd()`
- shell 信息可由 CLI / AgentLoop 传入，或先用配置值。

这是后续优先修复项，因为它直接影响工具调用路径、安全边界和跨平台行为。

### Runtime Environment Implementation Note

已落地：

- `ContextBuilder(runtime_environment=...)` 支持注入运行环境 section。
- `AgentLoop` 默认通过 `format_runtime_environment(workspace_root)` 注入：
  - current date
  - current time
  - OS
  - shell
  - workspace root
  - path style
  - filesystem path policy
  - relative path preference
- CLI 启动时会把 `Path.cwd()` 同时传给 `create_default_registry(...)` 和 `AgentLoop(workspace_root=...)`，确保工具 workspace 与 prompt 里的 workspace 一致。
- `list_dir` / `read_file` 的工具描述和错误信息已补充 workspace 约束，明确建议优先使用 `.` 和相对路径。

这次修复的重点不是放开文件访问，而是让模型知道正确边界：当前本地 CLI 运行在 Windows workspace 内，不能凭空生成 `/Users/...` 这类 macOS/Linux 绝对路径。

后续本地测试 web search 时又发现一个相关问题：用户说“明天的天气”时，如果上下文没有当前日期，模型可能把“明天”交给搜索引擎乱匹配，甚至命中旧年份页面。

因此 Runtime Environment 继续补充：

```text
- Current date: YYYY-MM-DD
- Current time: HH:MM:SS <timezone>
- Resolve relative dates such as today, tomorrow, and yesterday to absolute dates before searching.
```

这不是新增 time/weather 工具，而是让模型在调用 `web_search` 前先把相对日期解析成绝对日期。

验证：

```text
python -m pytest tests/test_context_builder.py tests/test_filesystem_tools.py tests/test_agent_loop.py tests/test_agent_trace.py
25 passed
```
