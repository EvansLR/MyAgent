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
