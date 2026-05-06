# AgentLoop 模块设计

## 职责

AgentLoop 是 MyAgent 的运行时核心。

一句话版本：

```text
AgentLoop 从 MessageBus 消费 InboundMessage，调用 Provider 生成回复，再把 OutboundMessage 发布回 MessageBus。
```

第一阶段先做最小消息流闭环，不做完整 ReAct。

## 为什么需要它

MessageBus 和 CLI Channel 只解决了消息输入输出问题，还没有真正的“Agent 处理者”。

没有 AgentLoop，链路停在这里：

```text
CLI Channel -> MessageBus
```

加入 AgentLoop 后，链路变成：

```text
CLI Channel -> MessageBus -> AgentLoop -> Provider -> MessageBus -> CLI Channel
```

这样用户终于可以在终端里输入文本，并看到系统返回响应。

## 第一阶段定位

第一阶段的 AgentLoop 不是完整 ReAct loop。

它先解决：

- 消费 inbound 消息
- 调用一个 provider
- 发布 outbound 回复
- 用锁保证一次只处理一条消息

暂时不解决：

- tool calling
- context builder
- memory
- trace
- max iterations
- tool result 回灌

这些会在后续模块逐步加进来。

## EchoProvider

为了先跑通链路，第一阶段引入一个临时 `EchoProvider`。

它不调用真实 LLM，只返回：

```text
Echo: <用户输入>
```

作用：

- 不需要 API key。
- 不依赖网络。
- 可以快速验证 CLI、MessageBus、AgentLoop 是否连接正确。
- 后续替换成 OpenAI-compatible provider 时，AgentLoop 的结构不用大改。

## 所属架构层

AgentLoop 属于 `Runtime Layer`。

EchoProvider 暂时属于 `Intelligence Layer` 的占位实现。

对应数据流：

```text
CLI Channel
  ↓ publish_inbound
MessageBus
  ↓ consume_inbound
AgentLoop
  ↓ generate
EchoProvider
  ↓ text
AgentLoop
  ↓ publish_outbound
MessageBus
  ↓ consume_outbound
CLI Channel
```

## 核心接口

### AgentLoop

第一阶段建议接口：

```text
process_next() -> OutboundMessage
run_until_stopped() -> None
stop() -> None
```

#### process_next

处理一条 inbound 消息。

步骤：

1. 从 bus 消费 `InboundMessage`。
2. 加锁。
3. 调用 provider 生成文本。
4. 封装 `OutboundMessage`。
5. 发布到 outbound 队列。
6. 返回 outbound 消息，方便测试。

#### run_until_stopped

循环调用 `process_next`。

用于 CLI 后台任务。

#### stop

把运行状态设为停止。

第一阶段只用于退出后台 loop，不做复杂任务取消。

### EchoProvider

第一阶段接口：

```text
generate(message: InboundMessage) -> str
```

后续真实 LLM Provider 会替换成更通用的接口，例如：

```text
generate(messages, tools=None) -> ProviderResponse
```

## 数据结构

建议目录：

```text
myagent/
├── agent/
│   ├── __init__.py
│   └── loop.py
└── providers/
    ├── __init__.py
    └── echo.py
```

## 与其他模块的关系

### MessageBus

AgentLoop 直接依赖 MessageBus。

它通过：

```text
consume_inbound
publish_outbound
```

和外部通信。

### CLI Channel

AgentLoop 不直接依赖 CLI。

CLI 和 AgentLoop 都只依赖 MessageBus。

### Provider

AgentLoop 调用 Provider 生成回复。

第一阶段是 EchoProvider；后续替换为 OpenAI-compatible provider。

## 第一阶段范围

第一阶段只实现：

- `AgentLoop`
- `EchoProvider`
- 一条消息处理
- 后台循环
- 简单 stop
- CLI 交互式 loop 接入

## 暂不实现

第一阶段暂不实现：

- ReAct 多轮工具循环
- tool calling
- ContextBuilder
- Memory
- Trace
- Provider retry
- 真实模型配置
- 任务取消恢复
- 多 session history

## 最小测试点

建议测试文件：

```text
tests/test_agent_loop.py
```

测试点：

1. `test_echo_provider_replies_with_input`
   - EchoProvider 返回用户输入的回显。

2. `test_agent_loop_processes_one_message`
   - inbound 放入消息后，`process_next` 会发布 outbound。

3. `test_agent_loop_uses_lock`
   - AgentLoop 有串行锁。

4. `test_agent_loop_stop_marks_not_running`
   - 调用 `stop` 后状态变为停止。

CLI 集成测试可以放在 `tests/test_cli_channel.py`：

- 用 fake input/output 测试 chat loop 可以处理一条 message 和 `/stop`。

## 面试表达

可以这样讲：

> 我先把 AgentLoop 做成一个最小运行时核心，它从 MessageBus 消费统一的 InboundMessage，调用 Provider 生成回复，再发布 OutboundMessage。第一阶段我没有直接接真实 LLM，而是先用 EchoProvider 跑通消息链路，这样可以把框架通信问题和模型接入问题分开验证。

如果面试官问“为什么 EchoProvider 有价值”，可以回答：

> EchoProvider 是一个测试替身。它让系统不依赖 API key 和网络，也能验证 CLI、MessageBus、AgentLoop 的协作。等链路稳定后，再替换成真实 LLM Provider，风险更小。

## 后续扩展方向

后续 AgentLoop 会逐步升级为完整 ReAct：

- 接入 ContextBuilder。
- 接入 OpenAI-compatible Provider。
- 支持 tool calling。
- 引入 ToolRegistry。
- 增加最大迭代次数。
- 工具结果回灌给 LLM。
- 写入 Trace JSONL。
- 接入 Memory 和 Skills。
- 支持 SubAgent 委托。

## 第一阶段实现说明

本次已经完成最小 AgentLoop + EchoProvider，并把 CLI 接成完整消息流。

实现目标：

```text
CLI -> MessageBus -> AgentLoop -> EchoProvider -> MessageBus -> CLI
```

相关文件：

```text
myagent/agent/__init__.py
myagent/agent/loop.py
myagent/providers/__init__.py
myagent/providers/echo.py
myagent/cli/commands.py
tests/test_agent_loop.py
tests/test_cli_channel.py
```

### agent/loop.py

`myagent/agent/loop.py` 里实现了 `AgentLoop`。

构造函数接收：

```text
bus: MessageBus
provider: EchoProvider | None
```

如果没有传 provider，就默认使用 `EchoProvider`。

这让第一阶段可以不配置 API key，也能跑通 Agent 主链路。

### process_next

`process_next()` 处理一条消息。

流程：

```text
consume_inbound
  -> acquire lock
  -> process_message
  -> publish_outbound
```

它会返回生成的 `OutboundMessage`，这样测试可以直接断言结果。

### process_message

`process_message(inbound)` 负责处理已经拿到的一条消息。

流程：

```text
InboundMessage
  -> provider.generate()
  -> OutboundMessage
  -> bus.publish_outbound()
```

当前 provider 是 EchoProvider，所以输出是：

```text
Echo: <用户输入>
```

### run_until_stopped

`run_until_stopped()` 是后台循环。

它会持续调用：

```text
process_next()
```

直到 `stop()` 被调用，或者任务被取消。

CLI 当前会把它放到后台 task 里运行。

### 串行锁

AgentLoop 内部有：

```text
asyncio.Lock()
```

当前每次 `process_next` 会用锁包住消息处理。

作用：

- 第一阶段避免并发 turn 相互交错。
- 后续接入工具调用和上下文历史时更安全。
- 面试时可以解释为“先用全局锁简化并发模型”。

### providers/echo.py

`EchoProvider` 是临时假模型。

接口：

```text
generate(message: InboundMessage) -> str
```

返回：

```text
Echo: <message.content>
```

它不是最终 LLM Provider，只是第一阶段测试替身。

## CLI 集成说明

这次也更新了 `myagent/cli/commands.py`。

新增两个运行时函数：

```text
run_chat(...)
run_local_echo_chat()
```

### run_chat

`run_chat` 是 CLI 输入循环。

流程：

```text
读取用户输入
  -> parse_cli_command
  -> 如果是 /help /new /stop，CLI 自己处理
  -> 如果是普通消息，publish_inbound
  -> 等待 consume_outbound
  -> 打印 MyAgent 回复
```

为了方便测试，它支持注入：

```text
input_func
output_func
```

测试里可以用 fake input/output，不需要真的打开终端。

### run_local_echo_chat

`run_local_echo_chat` 把三个模块接起来：

```text
MessageBus()
AgentLoop(bus)
run_chat(bus)
```

它会把 AgentLoop 放到后台 task 里运行。

当 CLI 退出时：

```text
agent.stop()
agent_task.cancel()
```

第一阶段这样处理足够简单，后续如果有长任务再设计更完整的取消机制。

## tests/test_agent_loop.py

测试覆盖：

1. EchoProvider 会回显输入。
2. AgentLoop 能处理一条 inbound 并发布 outbound。
3. AgentLoop 暴露锁状态。
4. `stop()` 会把 running 设为 False。

CLI 测试也新增了两类集成行为：

1. `/help` 和 `/stop` 可以在 `run_chat` 里运行。
2. 普通消息会通过 MessageBus 等到 outbound 并打印。

## 本次验证结果

已执行：

```text
python -m pytest
```

结果：

```text
21 passed
```

也执行了管道输入 smoke test：

```text
"hello`n/stop`n" | python -m myagent
```

结果：

```text
MyAgent CLI is ready. Type /help for commands.
You: MyAgent: Echo: hello
You: Stopping MyAgent CLI.
```

你也可以手动运行：

```text
python -m myagent
```

然后输入：

```text
hello
/new
hi
/stop
```

当前会看到 EchoProvider 的回显。

## 如何阅读这部分代码

建议按这个顺序读：

1. `tests/test_agent_loop.py`
2. `myagent/providers/echo.py`
3. `myagent/agent/loop.py`
4. `myagent/cli/commands.py` 里的 `run_chat`

读代码时抓住主线：

```text
InboundMessage -> Provider -> OutboundMessage
```

这就是后续 ReAct loop 的最小雏形。

## 当前代码的边界

当前已经能在终端里聊天，但它只是 Echo 聊天。

还没有：

- 真实 LLM
- ContextBuilder
- ToolRegistry
- Memory
- Trace
- ReAct 多轮工具循环

OpenAI-compatible Provider 已经接入。下一步建议做 ContextBuilder，让 AgentLoop 从“单条用户消息”升级为“结构化上下文消息”。
