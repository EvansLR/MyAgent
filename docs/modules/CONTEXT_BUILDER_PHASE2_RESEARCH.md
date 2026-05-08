# ContextBuilder Phase 2 外部调研与改造方向

## 目标

这份文档用于给 MyAgent 的 ContextBuilder 第二轮升级定方向。

本轮原则：

- 不凭主观想象直接改 ContextBuilder。
- 先参考成熟 Agent / Coding Agent / Memory 框架的 context 管理经验。
- 只采纳适合 MyAgent 当前阶段的部分。
- 第二轮要做到有价值、可测试、可解释，但不提前堆复杂生产系统。

## 当前 MyAgent 现状

当前 `ContextBuilder` 已经能组装：

```text
Identity
Core Memory
Available Skills
Conversation History
Current User Message
```

注：旧 JSONL `MemoryRecall` 主路径已经决定删除，不再作为 ContextBuilder v2 的设计对象。

核心代码：

```text
myagent/agent/context.py
```

当前问题：

- `ContextSection` 只有 `name/content/priority`，没有 token/size 统计。
- ContextBuilder 只负责拼接，不产出可观测的 assembly report。
- AgentLoop 只记录 `message_count` 和 roles，不记录每个 section 占用。
- 没有明确区分 protected context、default context、retrievable context、ephemeral context。
- Skills 当前是摘要全量注入，未来数量变多会膨胀。
- Tool schema 成本没有进入 context report。
- History 没有预算控制、裁剪、摘要或 compaction hook。
- 没有 `/context` 或类似 inspect 接口。

## 外部系统经验

### OpenClaw Context

来源：

- https://docs.openclaw.ai/concepts/context

关键设计：

- 明确区分 context 和 memory：memory 在磁盘上，context 是当前真正发给模型的内容。
- `/status` 查看窗口使用情况。
- `/context list` 查看注入内容和粗略大小。
- `/context detail` 查看文件、tool schema、skill entry、system prompt 等贡献。
- system prompt 每轮重建，包含工具、skills、workspace、时间、runtime metadata、bootstrap files。
- workspace bootstrap files 有单文件和总量上限，超限会截断并提示。
- skills 只默认注入 metadata，完整 skill 内容按需读取。
- tools 有两类成本：system prompt 里的工具文字说明，以及发送给模型的 JSON schema。
- compaction summary 会写入 transcript，并保留最近消息。
- pruning 会从当前 prompt 删除旧 tool results，但不改写完整 session transcript。

可采纳：

- MyAgent 应该产出 context assembly report。
- ContextBuilder 应该知道每个 section 的 size / estimated tokens。
- Skills 继续保持摘要注入，全文按需加载。
- Tool schema 成本虽然不在 system prompt 文本里，也应该在 context report 中显示。
- 第二轮可以先做 report 和 tier，不急着做完整 compaction。

### OpenAI Agents SDK / Sessions

来源：

- https://openai.github.io/openai-agents-python/sessions/
- https://developers.openai.com/cookbook/examples/agents_sdk/session_memory

关键设计：

- Session 负责自动维护多轮 conversation history。
- 每轮 run 前读取 session history，和新输入合并。
- 每轮 run 后保存 user input、assistant output、tool calls 等新 items。
- 可以用 `session_input_callback` 自定义“history + new input”的合并策略，例如只保留最近 N 条。
- `OpenAIResponsesCompactionSession` 可以包装 session，根据策略自动 compact。
- cookbook 强调 context 管理不是省 token 小优化，而是避免 stale details、tool noise 和 context poisoning。
- 两类基础技术是 trimming 和 compression。

可采纳：

- MyAgent 应该把 “session history 存储” 和 “本轮 context 输入选择” 分开。
- 第二轮可以先实现 deterministic trimming 或预算报告，为后续 compression 留 hook。
- `ContextBuilder` 不应该直接持久化 history，但可以接收 history 并产出 selection/report。

### Claude Code

来源：

- https://code.claude.com/docs/en/how-claude-code-works
- https://docs.claude.com/en/docs/claude-code/memory

关键设计：

- context window 包含 conversation history、文件内容、命令输出、CLAUDE.md、auto memory、skills、system instructions。
- 接近上限时会自动管理：先清旧 tool outputs，再需要时摘要 conversation。
- 早期对话里的详细指令可能在 compaction 中丢失，所以持久规则应放入 CLAUDE.md。
- `/context` 用于查看空间占用。
- skills 按需加载；subagents 使用独立 fresh context，完成后只返回 summary，避免污染主上下文。
- Claude Code memory 采用多层 `CLAUDE.md`，并支持 `/memory` 管理。

可采纳：

- MyAgent 的 Core Memory / docs / project rules 应放在稳定 section，而不是依赖聊天历史。
- tool results 应该是优先裁剪对象。
- SubAgent 独立上下文是控制主上下文膨胀的重要策略。
- 后续 `/context` inspect 命令有必要。

### LangGraph / LangChain

来源：

- https://docs.langchain.com/oss/javascript/concepts/memory

关键设计：

- 区分 short-term memory 和 long-term memory。
- short-term memory 是 thread-scoped conversation state，可用 checkpointer 持久化。
- long-term memory 是跨 thread 的 user/app data。
- 长 conversation 会导致错误、分心、延迟和成本上升。
- 管理 short-term messages 时需要删除或遗忘 stale information。
- long-term memory 可以分 semantic / episodic / procedural。
- memory 写入可以在 hot path 或 background，各有延迟和质量权衡。

可采纳：

- MyAgent 应继续保持短期 session history 和长期 memory 分离。
- ContextBuilder 只组装当前窗口；MemoryStore 管长期事实；未来 SessionManager 管短期历史。
- 第二轮 ContextBuilder 应先定义 short-term history 的选择策略。

## MyAgent ContextBuilder Phase 2 设计方向

第二轮目标不是直接实现完整自动压缩系统，而是把 ContextBuilder 从“简单拼 prompt”升级为“可观测、可分层、可预算、可扩展的 context composer”。

建议目标：

```text
ContextBuilder v2
  -> Section tier
  -> Size / token estimate
  -> Assembly report
  -> History selection policy
  -> Trace integration
  -> Future compaction hooks
```

### Context 分层

建议给 section 增加 tier：

```text
PROTECTED
  必须保留。Identity、Core Memory、安全/行为边界。

HIGH
  高优先级。当前任务、最近用户目标、active project context。

MEDIUM
  默认可见。Skills summary、selected history、retrieved snippets。

LOW
  可裁剪。旧 history、旧 tool results、大块日志、冗余输出。

EPHEMERAL
  本轮临时信息。tool result、SubAgent result、attachments 摘要等。
```

第一版可以先用字符串或 Enum，不必立刻做复杂裁剪。

### ContextSection 建议字段

建议从：

```python
ContextSection(name, content, priority)
```

升级为：

```python
ContextSection(
    name: str,
    content: str,
    priority: int,
    tier: str,
    source: str,
    char_count: int,
    estimated_tokens: int,
    included: bool,
    reason: str,
)
```

为了保持实现小，`char_count` 和 `estimated_tokens` 可以由 report 动态计算，不一定放进 dataclass。

### Assembly Report

ContextBuilder 每次构建 messages 时，应额外产生 report：

```text
ContextAssemblyReport
  total_chars
  estimated_tokens
  message_count
  sections:
    - name
    - tier
    - priority
    - source
    - chars
    - estimated_tokens
    - included
    - reason
  history:
    total_messages
    included_messages
    dropped_messages
  warnings:
    - section truncated
    - history trimmed
```

AgentLoop 可以把 report 写进 trace：

```text
context_built
  section_count
  estimated_tokens
  sections
  history_included
  warnings
```

这对应 OpenClaw `/context list/detail` 的第一步。

### History 策略

第二轮建议先做 deterministic history selection：

```text
默认保留最近 N 轮
保留 system prompt
保留当前 user message
不做摘要
不做模型压缩
```

建议参数：

```text
max_history_messages = 20
```

或者按字符预算：

```text
max_history_chars = 20000
```

第一版可以先按消息数，report 里显示字符和估算 token。之后再按 budget 裁剪。

### 预算策略

第二轮可以先引入预算对象，但不一定完整裁剪：

```python
ContextBudget(
    max_prompt_tokens: int | None = None,
    max_history_messages: int = 20,
    chars_per_token: int = 4,
)
```

如果超过预算，先采取保守策略：

```text
1. 保留 PROTECTED。
2. 保留当前 user message。
3. History 从新到旧加入，直到接近预算。
4. LOW / EPHEMERAL 优先裁剪。
5. 记录 warning。
```

### 与 Memory 的关系

当前 Memory v2 已经确定：

```text
MEMORY.md 的 Core Memory / User Profile / Active Goals
  -> 默认进入 context

daily / DREAMS / searchable memory
  -> 不默认进入 context
  -> 通过 memory_search / memory_get 按需进入
```

ContextBuilder v2 应保持这个边界：

- Core Memory 是 `PROTECTED` 或 `HIGH`。
- Searchable Memory 不自动进入。
- post-turn MemoryExtractor 不属于 ContextBuilder。
- pre-compaction memory flush 是未来 compaction hook，不在本次强做。

### 与 Skills 的关系

当前 Skills summary 会全量注入。

第二轮建议：

- Skills summary 作为 `MEDIUM` section。
- report 中记录 skill count 和 chars。
- 暂不加载 skill 全文。
- 后续做 active skill 时，再把被激活 skill 的全文放入 `HIGH` 或 `MEDIUM`。

### 与 Tools 的关系

Provider 发送 tool schemas 时，schema 也占上下文预算，但现在 ContextBuilder 看不到 tool schema。

第二轮可以先不重构 provider，但在设计上记录：

```text
ContextBuilder report = prompt text report
AgentLoop/provider report = tool schema report
```

后续可以在 AgentLoop 合并：

```text
context_built:
  prompt_estimated_tokens
  tool_schema_count
  tool_schema_estimated_tokens
```

### 与 SubAgent 的关系

SubAgent 已经有独立 context，这与 Claude Code 的经验一致。

第二轮可以记录：

- 主 Agent 的 context 不塞入子 Agent 的完整执行历史。
- 子 Agent 只返回 summary / result。
- 后续 trace tree 可以观察子 Agent 内部上下文。

## Phase 2 最小实现建议

建议第一步不直接做复杂 compaction，而是实现：

1. 新增 `ContextBudget`。
2. 新增 `ContextAssemblyReport`。
3. `ContextSection` 增加 `tier` 和 `source`。
4. `ContextBuilder.build_messages(...)` 内部使用 history selection。
5. 暴露最近一次 report：

```python
builder.last_report
```

或改成：

```python
messages, report = builder.build_messages_with_report(...)
```

为了少破坏现有调用，建议保留 `build_messages(...)`，新增：

```python
build_messages_with_report(...)
```

6. AgentLoop 使用 `build_messages_with_report(...)` 并把 report 写入 trace。
7. 测试覆盖：

- section 按 priority 排序。
- Core Memory 是 high/protected section。
- history 超过 `max_history_messages` 时只保留最近消息。
- report 包含 section sizes。
- trace 的 `context_built` 包含 context report。

## 暂不实现

本轮暂不实现：

- 模型摘要式 compaction。
- pre-compaction memory flush。
- `/context` slash command。
- tool schema 精确 token 计算。
- tiktoken / tokenizer 依赖。
- persistent SessionManager。
- active skill 全文加载。

这些不代表推到第三轮，而是等 ContextBuilder v2 的 report 和 budget 边界稳定后，再按正常节奏推进。

## 面试表达

可以这样讲：

> 第一版 ContextBuilder 只是把 Identity、Memory、Skills 和 history 拼成 messages。第二版我参考 OpenClaw、OpenAI Agents SDK、Claude Code 和 LangGraph，把它升级成一个可观测的 context composer：每个 section 有 tier、priority、source 和 size 统计；构建时产出 assembly report；history 有确定性的选择策略；trace 能看到上下文由什么组成。这样后续做 trimming、compression、memory flush 或 `/context` inspect 时，不需要重写核心结构。

如果被问为什么不直接做自动压缩：

> 自动压缩需要触发条件、摘要质量控制、压缩结果存储和 memory flush 配合。第二轮先把 context 的边界、预算和观测做好，才能知道什么时候需要压缩、压缩什么、压缩后怎么验证。否则容易做成一个不可解释的黑盒。

## 参考链接

- OpenClaw Context: https://docs.openclaw.ai/concepts/context
- OpenAI Agents SDK Sessions: https://openai.github.io/openai-agents-python/sessions/
- OpenAI Context Engineering cookbook: https://developers.openai.com/cookbook/examples/agents_sdk/session_memory
- Claude Code context behavior: https://code.claude.com/docs/en/how-claude-code-works
- Claude Code memory: https://docs.claude.com/en/docs/claude-code/memory
- LangGraph memory overview: https://docs.langchain.com/oss/javascript/concepts/memory
