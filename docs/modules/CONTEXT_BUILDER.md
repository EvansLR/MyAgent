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
56 passed
```

---

### 已知问题：缺少 Budget-aware Compaction

当前 ContextBuilder 已经具备 tier 和 budget 结构，但**没有实现超预算时的降级逻辑**。

具体问题：

1. **System prompt 无限增长**
   - `MEMORY.md` 会随着 Consolidation 越来越长
   - Available Skills 的 description 变长
   - Workspace 文件内容累积
   - 没有任何长度限制

2. **History 只按消息数裁剪**
   - `select_history()` 只保留最近 20 条消息
   - 但不做 token 级别裁剪，20 条长对话可能远超预算

3. **`max_prompt_tokens` 默认无限制**
   - `ContextBudget.max_prompt_tokens` 默认是 `None`
   - 没有任何 token 级别的预算控制

**后续方向**：

- 设定总 prompt token 上限（如 6000）
- 超预算时按 tier 优先级逐步降级/丢弃：
  - 先丢 LOW（Available Skills 详细描述）
  - 再丢 MEDIUM（Tool Guidelines）
  - 保留 HIGH（Memory）和 PROTECTED（Identity、User Profile）
- history 从按消息数裁剪升级为按 token 数裁剪
- 生成 `context_dropped` trace 事件

这是当前最应优先补齐的短板。

## Phase 2B Research: Budget-aware Context Composer

本轮重新校准了 ContextBuilder 的设计：上下文膨胀不只是 system prompt
太长，也包括 session history、tool results、retrieved memory、skill
content、workspace 文件和工具 schema 等多种来源。

因此，下一步不应只做“按 priority 丢 system section”。那样只能解决一小
部分问题，而且会误导 `priority` 的语义。

### 外部方案调研

参考的成熟方案：

- Claude Code Context Window
  - context 包含项目规则、memory、MCP/tool 信息、skill 描述、文件读取、工具结果和对话历史。
  - `/compact` 或自动 compact 会把长历史替换成结构化摘要。
  - 项目级 memory / rules 会在 compact 后重新注入。
  - 参考：https://code.claude.com/docs/en/context-window

- OpenAI Agents SDK Sessions
  - session 负责跨 run 保存 conversation history。
  - `SessionSettings(limit=N)` 可以限制每次 run 取回的历史条数。
  - `OpenAIResponsesCompactionSession` 可以在 history 达到阈值后自动压缩。
  - 参考：https://openai.github.io/openai-agents-python/sessions/

- OpenAI sandbox agent memory
  - 明确区分 conversational session memory 和 agent memory。
  - 采用 progressive disclosure：先注入小的 memory summary，再按需搜索和打开更详细的 rollout summaries。
  - memory 可以过期或失效，agent 应优先相信当前环境。
  - 参考：https://openai.github.io/openai-agents-python/sandbox/memory/

- LangChain / LangGraph
  - `trim_messages` 支持按 token 或消息数裁剪，并保持消息结构合法。
  - 常见方案是保留最近消息，或把旧消息总结成 summary。
  - 对 ReAct agent，history 管理通常放在 pre-model hook / middleware。
  - 参考：https://reference.langchain.com/v0.3/python/core/messages/langchain_core.messages.utils.trim_messages.html

- LlamaIndex Memory
  - 支持 `token_limit`、`chat_history_token_ratio`、`token_flush_size`。
  - 当 chat history 超过预算时，可以把部分内容 flush 到长期 memory。
  - 参考：https://docs.llamaindex.ai/en/stable/module_guides/deploying/agents/memory/

- AutoGen Model Context
  - `BufferedChatCompletionContext` 保留最近 N 条消息。
  - `TokenLimitedChatCompletionContext` 维护一个 token-limited context view。
  - Memory 通过 `update_context(...)` 在模型调用前向 context 注入相关内容。
  - 参考：https://microsoft.github.io/autogen/stable/reference/python/autogen_core.model_context.html

- OpenClaw Context
  - context 是每次发送给模型的完整内容，不等同于磁盘 memory。
  - pruning 可以从 in-memory prompt 中丢弃旧 tool results，但不重写磁盘 transcript。
  - context engine 可以接管 assembly / compact / subagent context lifecycle。
  - 参考：https://docs.openclaw.ai/context/

### 调研结论

成熟系统通常不是把所有上下文放进一个全局优先级队列，而是按来源和生命周期
分池处理：

```text
instructions / rules
  稳定、高优先级，通常永远保留

current user input
  当前任务本身，永远保留

session history
  最近优先，按 token 或消息数裁剪，旧内容可摘要

tool calls / tool results
  当前 turn 的工作记忆，容易膨胀，旧结果可 prune 或 summarize

memory
  核心 memory 默认注入，详细 memory 通过 search/get progressive disclosure

skills
  skill summary 默认注入，完整 SKILL.md 按需加载，不跨 turn 默认保留

retrieved context
  按 relevance / score / top-k / token cap 注入
```

这意味着 MyAgent 应该把 ContextBuilder 从“system prompt 拼接器”升级为
“context composer”。

### `priority` 的正确语义

`priority` 不应该被理解成全局保命等级。

新的语义建议：

```text
kind
  这是什么上下文：instruction / memory / skill / history / tool_result / retrieved_context

tier
  它的生存级别：protected / high / medium / low / ephemeral

policy
  超预算时怎么处理：never_drop / keep_recent / drop / summarize_later / top_k

priority
  同一 kind 或同一 tier 内部的稳定排序 / tie-breaker
```

也就是说：

- `tier` 决定“能不能丢、什么时候丢”。
- `kind` 决定“用什么方式裁剪”。
- `policy` 决定具体动作。
- `priority` 只在同类内容内部排序，不负责所有类型之间的绝对比较。

示例：

```text
Identity
  kind=instruction
  tier=protected
  policy=never_drop
  priority=1

Runtime Environment
  kind=instruction
  tier=protected
  policy=never_drop
  priority=20

Long-term Memory
  kind=memory_core
  tier=high
  policy=keep_or_truncate_later
  priority=30

Available Skills
  kind=skill_summary
  tier=medium
  policy=drop_if_needed
  priority=30

Session History
  kind=session_history
  tier=medium
  policy=keep_recent_by_token
  priority 不作为全局排序，只用于 history 内部稳定顺序

Tool Result
  kind=tool_result
  tier=ephemeral
  policy=prune_old_or_summarize
```

### MyAgent 的分阶段设计

#### Phase 2B：Deterministic Context Budget

第一阶段不做 LLM summary，只做可解释、可测试的 deterministic budget。

实现目标：

1. 引入内部 `ContextItem` 概念。

```text
ContextItem
  id
  name
  kind
  tier
  priority
  source
  content
  estimated_tokens
  policy
```

现有 `ContextSection` 可以先转成 `ContextItem`，保持外部接口兼容。

2. 让 `ContextBudget.max_prompt_tokens` 变成真实约束。

建议默认值：

```text
max_prompt_tokens = 6000
```

调用方仍可显式传 `None` 表示不限制，便于特殊测试和调试。

3. 分池预算，而不是全局排序。

最小策略：

```text
always keep:
  Identity
  Runtime Environment
  Agent Principles
  User Profile
  Delegation Policy
  current user message

prefer keep:
  Long-term Memory

drop first if needed:
  Available Skills
  Active Skills
  Tool Guidelines

trim by token:
  Session History, newest first
```

4. history 从“消息数裁剪”升级为“token-aware 裁剪”。

当前策略：

```text
max_history_messages = 20
```

建议升级为：

```text
先按 max_history_messages 取最近 N 条
再在剩余 token budget 内从后往前保留
超出的旧消息丢弃
```

当前用户消息永远保留。

5. report 和 trace 可解释。

`ContextAssemblyReport` 应记录：

```text
estimated_tokens_before_budget
estimated_tokens_after_budget
max_prompt_tokens
dropped_sections
dropped_history_messages
warnings
```

section report 中保留：

```text
included=false
reason=budget_exceeded
```

如果出现 drop，AgentLoop 可记录：

```text
context_dropped
  dropped_sections
  dropped_history_messages
  estimated_tokens_before
  estimated_tokens_after
  max_prompt_tokens
```

#### Phase 2C：Tool Output Boundary

Phase 2B 只控制首次 provider call 的上下文还不够。

`AgentLoop._generate_with_tools(...)` 内部会不断追加：

```text
assistant tool_call message
tool result message
refreshed system prompt
```

这会导致当前 turn 内部 context 继续膨胀。成熟系统会对 tool results 做
pruning 或 summarization，OpenClaw 也明确提到可以丢弃 in-memory prompt
中的旧 tool results 而不改磁盘 transcript。

MyAgent 后续应单独设计：

```text
WorkingTurnContextBudget
  max_working_tokens
  tool_output_boundary
  max_tool_results
  prune_old_tool_results
```

Phase 2C 建议只做 deterministic pruning：

- 保留最近工具结果。
- 对旧 tool result 只保留 preview / result_length / tool name。
- 不重写 trace。
- 不修改 session history。

#### Later：LLM Compaction 和 Memory Flush

等 history、tool results、active skills 真正出现高压场景后，再做：

```text
before_compaction:
  optional memory flush
  transcript summary
  tool result summary
  summary injection
  trace compaction report
```

这一步需要 LLM summarizer，因此不放进 Phase 2B。

### 当前建议的最小实现范围

第一轮代码实现只改：

```text
myagent/agent/context.py
tests/test_context_builder.py
tests/test_agent_trace.py
```

如果需要 trace inspect 显示 dropped 信息，再补：

```text
myagent/tracing/inspect.py
tests/test_trace_store.py
```

暂不改：

```text
MemoryExtractor
MemoryConsolidator
SkillRegistry
SubAgentRunner
ToolRegistry
```

### 面试表达

可以这样讲：

> 我没有把 context 管理简化成“按 priority 丢 system prompt”。成熟 Agent
> 系统里，上下文来自 instructions、memory、skills、history、tool results
> 和 retrieved context，它们的生命周期不同。所以 MyAgent 用 kind 表示内容
> 类型，用 tier 表示生存级别，用 policy 表示裁剪方式，priority 只做同类
> 内容内部排序。第一阶段先实现 deterministic budget-aware composer，保证
> prompt 不会无限增长；后续再接入 tool result pruning、LLM compaction 和
> memory flush。

如果被问到为什么不先做摘要式 compact：

> 摘要式 compact 需要额外模型调用，并且会引入信息损失。MyAgent 当前更需要
> 一个可测试、可解释的基础预算层：先知道哪些内容进了 context、哪些被丢弃、
> 为什么被丢弃。等 trace 显示 history 或 tool results 经常触顶，再引入
> summarization hook 更合理。

### 下一步实现建议

推荐实现顺序：

1. 新增内部 `ContextItem` / `ContextItemKind` / `ContextRetentionPolicy`。
2. 把现有 `ContextSection` 转成 items，再 render 成 system prompt。
3. 实现 prompt budget selection：
   - protected 必保
   - high 尽量保
   - medium / low 可丢
   - history 按剩余 token 从后往前保留
4. 扩展 `ContextAssemblyReport`。
5. `AgentLoop` 在发生 drop 时记录 `context_dropped`。
6. 增加 focused tests。

## Phase 2B Implementation Notes

本轮已完成 Budget-aware Context Composer 的第一片实现，重点是先建立一个
可观测、可测试的 deterministic budget 层，而不是直接做 LLM 摘要压缩。

修改文件：

```text
myagent/agent/context.py
myagent/agent/loop.py
myagent/agent/__init__.py
myagent/tracing/inspect.py
myagent/tracing/html_report.py
tests/test_context_builder.py
tests/test_agent_trace.py
tests/test_trace_store.py
```

### 已实现内容

新增内部上下文分类：

```text
ContextItem
ContextItemKind
ContextRetentionPolicy
```

当前语义：

```text
ContextItemKind
  instruction
  memory_core
  skill_summary
  active_skill
  session_history
  current_input
  workspace

ContextRetentionPolicy
  never_drop
  keep_if_fits
  drop_if_needed
  keep_recent_by_token
```

`ContextSection` 保持外部兼容，但新增：

```text
kind
policy
```

这样现有调用方仍然可以继续使用 section，而 ContextBuilder 内部会把 section
转换为 budgetable item。

### 默认预算

`ContextBudget.max_prompt_tokens` 默认从无限制改为：

```text
6000
```

调用方仍然可以显式传：

```text
ContextBudget(max_prompt_tokens=None)
```

表示不启用 token 预算。

当前 token 估算仍然沿用轻量策略：

```text
chars_per_token = 4
```

这不是精确 tokenizer，而是适合当前 hot path 的近似预算层。

参考 LlamaIndex `chat_history_token_ratio` 这类公开设计，当前还新增：

```text
history_token_ratio = 0.35
```

含义是：当存在 session history 时，ContextBuilder 会为 history 预留总 prompt
预算的一部分，避免 system sections、memory 或 skills 把短期对话历史完全挤掉。
如果没有 history，则不预留这部分预算。

### Section 预算行为

当前 system section 会先转换为 `ContextItem`，再按预算选择：

```text
protected / never_drop
  永远保留

high / medium / low / ephemeral
  按 tier 和 priority 尝试保留
  放不下则 included=false, reason=budget_exceeded
```

当前已标记为 protected：

```text
Identity
Runtime Environment
Agent Principles
User Profile
Delegation Policy
```

当前可在预算不足时丢弃：

```text
Available Skills
Active Skills
Tool Guidelines
```

Long-term Memory 标记为：

```text
kind=memory_core
tier=high
policy=keep_if_fits
```

### History 预算行为

history 现在仍先受：

```text
max_history_messages
```

约束，然后再受剩余 token budget 约束。

选择策略：

```text
从最近的 history message 往前保留
超过剩余 token budget 的旧消息丢弃
确保最终 history 不以 assistant/tool message 开头
```

report 中新增：

```text
history.reserved_tokens
history.estimated_tokens
history.dropped_by_message_limit
history.dropped_by_token_budget
```

### History 成熟路线

当前 MyAgent 的 history 管理已经从“最近 N 条消息”升级到：

```text
recent message window
  -> token-aware trimming
  -> history_token_ratio budget reserve
```

这对应成熟框架中的基础短期记忆层，但还不是完整的 conversation memory
lifecycle。

参考公开框架后，History 后续应按下面路线过渡：

#### Level 1：Recent Buffer

只保留最近 N 条消息。

对应成熟框架：

- AutoGen `BufferedChatCompletionContext`

价值：

- 实现简单。
- 防止 prompt 无限增长。

限制：

- 旧但重要的信息会被直接丢出模型窗口。

MyAgent 状态：

```text
已实现：max_history_messages
```

#### Level 2：Token Window

保留最近且能放进 token budget 的消息。

对应成熟框架：

- AutoGen `TokenLimitedChatCompletionContext`
- LlamaIndex short-term memory token limit

价值：

- 比固定消息数更贴近真实模型上下文限制。

MyAgent 状态：

```text
已实现：history token-aware trimming
```

#### Level 3：History Ratio / Token Allocation

给短期 history 预留一部分总 prompt budget，避免 system sections、memory、
skills 把近期对话完全挤掉。

对应成熟框架：

- LlamaIndex `chat_history_token_ratio`

MyAgent 状态：

```text
已实现：history_token_ratio = 0.35
```

当前区别：

```text
LlamaIndex:
  超过比例后可以 flush 到 long-term memory blocks

MyAgent 当前:
  先只预留 history budget
  超出的旧 history 暂时只丢出模型窗口
```

#### Level 4：Running Summary + Recent Messages

当 history 超过阈值时，把旧消息总结成 running summary，再把模型可见历史变成：

```text
Conversation Summary
+ recent raw messages
+ current user message
```

对应成熟框架：

- LangGraph / LangMem `summarize_messages`
- OpenAI Responses compaction session

建议 MyAgent 后续引入：

```text
ConversationSummary
  content
  summarized_message_ids
  last_summarized_message_id
```

边界：

- 原始 history 不应被摘要覆盖。
- summary 是 model-visible view 的一部分，不是唯一事实来源。
- summary 生成应写 trace，说明哪些 message 被 summarized。

#### Level 5：Flush Old History Into Memory Pipeline

旧 history 不应只是被 summary 吸收，也可以进入长期 memory pipeline。

MyAgent 可复用现有结构：

```text
old history over compaction threshold
  -> MemoryExtractor
  -> daily/YYYY-MM-DD.md candidates
  -> DREAMS.md proposals
  -> MemoryConsolidator
  -> MEMORY.md durable memory
```

这对应 LlamaIndex 把超出 short-term memory 的内容 flush 到 long-term memory
blocks 的思路，但保持 MyAgent 的 Markdown-backed local-first 形态。

#### Level 6：Full Session Store 与 Model-visible View 分离

成熟框架通常区分：

```text
stored history
  完整保存，用于审计、恢复、UI 和后续 compaction

model-visible history
  每次模型调用前筛选、裁剪、摘要后的 view
```

对应成熟框架：

- OpenAI Agents SDK Session
- LangGraph state + checkpointer

MyAgent 当前 `_history` 仍是 AgentLoop 内存 list。后续若要完善，应拆出：

```text
SessionStore
  append turn
  list full history
  list model-visible history
  store summaries
```

这一步不应和当前 ContextBuilder v2B 混在一起做。

#### Level 7：Tool Call / Tool Result 成组裁剪

Agent history 中的 tool call / tool result 不能随意按单条消息裁剪，否则可能产生
非法消息序列。

后续 working-turn budget 应按组处理：

```text
assistant tool_call
+ matching tool result
```

一起保留、一起摘要或一起丢弃。

这属于 Phase 2C / working-turn budget，而不是本轮 history window。

### History 下一步建议

为了平滑过渡到成熟形态，推荐顺序：

```text
1. 先保持当前 deterministic token window + ratio reserve 稳定。
2. 设计 WorkingTurnContextBudget，先解决 tool result 膨胀。
3. 再设计 ConversationSummary，把旧 history 压成 summary + recent messages。
4. 最后接 MemoryExtractor / daily / DREAMS，实现旧 history flush。
5. 等上面稳定后，再拆 SessionStore。
```

原因：

- tool result 膨胀会在 ReAct loop 中更快触发真实上下文压力。
- ConversationSummary 需要额外模型调用和 summary state，应该等基础预算层稳定后再做。
- SessionStore 是更大的 runtime 边界，不适合在 ContextBuilder v2B 里顺手重构。

warnings 新增：

```text
context_budget_exceeded
section_dropped
history_token_trimmed
protected_context_over_budget
```

### Trace

`ContextAssemblyReport` 新增：

```text
estimated_tokens_before_budget
max_prompt_tokens
dropped_sections
```

Trace inspect / report 已同步显示新增预算字段：

```text
python -m myagent trace context
  estimated_tokens_before_budget
  max_prompt_tokens
  history reserved/tokens
  section kind
  dropped reason

python -m myagent trace report
python -m myagent trace viewer
  Context overview 显示 before-budget / max prompt / history reserved
  section row 显示 kind 和 dropped reason
  context_dropped 事件显示 dropped section/history/token delta
```

当 ContextBuilder 实际丢弃 section 或按 token 丢弃 history 时，AgentLoop 会记录：

```text
context_dropped
```

事件内容包括：

```text
dropped_sections
dropped_history_messages
dropped_history_by_token_budget
estimated_tokens_before
estimated_tokens_after
max_prompt_tokens
```

### 当前边界

这轮仍然不处理：

- tool result pruning
- working turn budget
- LLM summary compaction
- memory flush before compaction
- 精确 tokenizer
- retrieved context top-k budget

原因是这些能力要么需要额外模型调用，要么涉及 AgentLoop tool loop 和
Memory pipeline 的更大边界。当前先把首次 provider call 的预算层做稳。

## Phase 2C Recalibration: Tool Output Boundaries

ContextBuilder v2B 管住的是首次 provider call：

```text
system prompt + selected history + current user message
```

但 ReAct tool loop 中，`AgentLoop._generate_with_tools(...)` 会持续追加：

```text
assistant tool_call message
tool result message
refreshed system prompt
```

如果工具返回大文件、长网页、长搜索结果，working messages 会在同一轮内快速膨胀。

### 设计目标

第一版不再做 working-turn tool result compaction；参考 NanoBot，优先把大输出控制在工具边界。

目标：

- 保持消息序列合法。
- 不删除 assistant tool_call / tool result 配对。
- 保留最近工具结果的完整内容。
- 对更早或过长的工具结果做确定性压缩。
- trace 记录压缩事实。

暂不做：

- LLM summary。
- 删除 tool call/result pair。
- 跨 turn 持久化 tool result summary。
- 精确 tokenizer。

### 为什么不直接丢 tool messages

OpenAI-compatible chat messages 对 tool call 有结构要求：

```text
assistant message with tool_calls
  -> matching tool role message(s)
```

如果只丢 `tool` message，或只丢 assistant tool_call message，就可能造成非法消息序列。

因此第一版不做 pair 删除，而是保留结构：

```text
assistant tool_call message
tool result message with compacted content
```

这样 provider 仍然能看到“工具已经执行过”，只是旧结果内容被压缩成 preview。

### 建议预算参数

复用 `ContextBudget`，先增加 working-turn 相关 knobs：

```text
read_file offset/limit pagination
read_file max chars per response
list_dir max_entries truncation
history-save-time tool result truncation if tool messages are persisted later
```

语义：

- `read_file` 使用 `offset` / `limit` 分页，返回行号和续读提示。
- `read_file` 对单次返回内容设置字符上限；当行窗口仍然过大时，按完整行截断，
  并保留续读提示。
- 对单行超过响应预算的 minified / long-line 文件，`read_file` 会返回截断 marker，
  避免续读提示卡在同一行。
- `list_dir` 使用 `max_entries` 截断目录输出。
- 当前 loop 内不把刚返回的 tool result 压成 preview。

### 压缩格式

被压缩后的 tool result content 建议格式：

```text
[Tool result boundary]
Original length: <chars> chars
Original estimated tokens: <tokens>
Kept preview:
<preview>
```

这不是摘要，只是 deterministic preview。

### AgentLoop 流程

建议在每次 provider call 前执行：

```text
working_messages = refresh_system_message(...)
provider.generate_response(working_messages, tools=tools)
```

注意：

- compaction 只影响当前 turn 的 model-visible working messages。
- trace 仍然记录真实 tool result preview / length。
- session history 仍然只保存最终 user / assistant，不保存 tool messages。

### Trace

新增事件：

```text
tool_output_boundary_deferred
```

字段：

```text
iteration
tool_result_boundary
estimated_tokens_before
estimated_tokens_after
```

每个 compacted tool result 记录：

```text
tool_call_id
original_chars
original_estimated_tokens
visible_range_or_limit
continuation_hint
truncated_when_saved
```

### 后续扩展

下一步可以继续演进：

```text
tool-level pagination
  -> LLM-generated tool result summary
  -> pair-level pruning
  -> pre-compaction memory flush
```

第一版只做 deterministic preview，保持行为可测、可讲清楚。

## Phase 2C Recalibration Notes

本轮参考 NanoBot 后撤回 Working-turn Budget 的第一片实现：当前 loop 内不再做
deterministic tool result compaction。

修改文件：

```text
myagent/agent/context.py
myagent/agent/loop.py
tests/test_agent_loop.py
tests/test_agent_trace.py
```

### 新增预算参数

`ContextBudget` 新增：

```text
read_file offset/limit pagination
read_file max chars per response
list_dir max_entries truncation
history-save-time tool result truncation if tool messages are persisted later
```

语义：

- 工具结果会完整进入当前 turn 的下一次 provider call。
- 大文件读取依赖 `read_file` 的 `offset` / `limit` 分页、字符上限和续读提示。
- 如果未来保存 tool messages，截断应发生在 history 保存边界。

### Runtime 行为

`AgentLoop._generate_with_tools(...)` 现在每次 provider call 前会执行：

```text
refresh system prompt
-> provider.generate_response(...)
```

压缩只影响当前 turn 内发给模型的 `working_messages`。

不会改变：

- trace 中记录的真实 tool result preview / result length。
- session history。
- 文件或 memory。

### 压缩格式

被压缩的 tool result content 形如：

```text
[Tool result boundary]
Original length: <chars> chars
Original estimated tokens: <tokens>
Kept preview:
<preview>
```

这不是语义摘要，只是可预测的 preview。

### Trace

当发生压缩时记录：

```text
tool_output_boundary_deferred
```

包含：

```text
iteration
estimated_tokens_before
estimated_tokens_after
tool_result_boundary
  tool_call_id
  original_chars
  original_estimated_tokens
  visible_range_or_limit
  continuation_hint
  truncated_when_saved
```

当前 reason：

```text
oversized_tool_result
old_tool_result
```

### 当前边界

这轮仍然不做：

- 删除 tool call/result pair。
- LLM-generated tool result summary。
- 跨 turn 保存 tool result summary。
- tool output 写入 memory。
- 精确 tokenizer。

原因是第一版目标是先控制当前 turn 内的上下文膨胀，同时保持消息结构合法。

### Verification

Focused verification：

```text
python -m pytest tests/test_filesystem_tools.py
28 passed

python -m pytest tests/test_agent_loop.py tests/test_agent_trace.py tests/test_context_builder.py
28 passed
```

### Verification

Focused verification：

```text
Superseded by the focused verification above.
```

Full test run observed：

```text
python -m pytest
211 passed
```
