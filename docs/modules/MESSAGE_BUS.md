# MessageBus 模块设计

## 职责

MessageBus 用两个内存异步队列解耦输入通道和 AgentLoop。

一句话版本：

```text
Channel 只负责收发消息，AgentLoop 只负责处理消息，中间通过 MessageBus 通信。
```

## 为什么需要它

如果没有 MessageBus，CLI Channel 会直接调用 AgentLoop：

```text
CLI -> AgentLoop
```

这样第一阶段也能跑，但会带来两个问题：

1. CLI 和 AgentLoop 绑定太死，后续换成 Telegram、Slack、Web UI 时要改 AgentLoop。
2. AgentLoop 的输入输出没有统一格式，不利于测试和 trace。

引入 MessageBus 后，系统变成：

```text
CLI Channel -> MessageBus -> AgentLoop -> MessageBus -> CLI Channel
```

好处：

- Channel 不关心 AgentLoop 怎么运行。
- AgentLoop 不关心消息来自哪里。
- 后续增加其他通道时，只要遵守同一套消息结构。
- 测试时可以绕过 CLI，直接往 MessageBus 塞消息。

## 参考 NanoBot 的取舍

NanoBot 的 MessageBus 已经很轻：

- `InboundMessage`
- `OutboundMessage`
- `MessageBus`
- `inbound` queue
- `outbound` queue

MyAgent 保留这个核心设计。

但第一阶段会做减法：

- 不实现多 IM 通道适配。
- 不实现消息优先级。
- 不实现广播订阅。
- 不实现跨进程消息队列。
- 不实现持久化队列。

## 所属架构层

MessageBus 属于 `Message Layer`。

它位于：

```text
Interface Layer
  ↓
Message Layer
  ↓
Runtime Layer
```

对应数据流：

```text
CLI Channel
  ↓ publish_inbound
MessageBus
  ↓ consume_inbound
AgentLoop
  ↓ publish_outbound
MessageBus
  ↓ consume_outbound
CLI Channel
```

## 输入输出

### InboundMessage

InboundMessage 表示“从用户或通道进入 Agent 的消息”。

第一阶段字段：

```text
channel: str
sender_id: str
chat_id: str
content: str
timestamp: datetime
metadata: dict[str, Any]
session_key_override: str | None
```

字段说明：

- `channel`：消息来源，比如 `cli`。
- `sender_id`：发送者标识。CLI 阶段可以固定为 `local-user`。
- `chat_id`：会话标识。CLI 阶段可以固定为 `default`，后续支持 `/new` 后再切换。
- `content`：用户输入文本。
- `timestamp`：消息创建时间。
- `metadata`：预留给通道自己的额外信息。
- `session_key_override`：允许特殊情况下覆盖默认 session key。

第一阶段不放 `media` 字段，因为 CLI 暂时只处理文本。后续接入 IM 或文件上传时再加。

### OutboundMessage

OutboundMessage 表示“Agent 要发回通道的消息”。

第一阶段字段：

```text
channel: str
chat_id: str
content: str
reply_to: str | None
metadata: dict[str, Any]
```

字段说明：

- `channel`：目标通道，比如 `cli`。
- `chat_id`：目标会话。
- `content`：Agent 输出文本。
- `reply_to`：可选回复目标。CLI 阶段可以不用。
- `metadata`：预留扩展信息。

第一阶段不放 `media` 字段，理由同上。

## 核心接口

MessageBus 对外提供 6 个核心能力。

```text
publish_inbound(msg: InboundMessage) -> None
consume_inbound() -> InboundMessage
publish_outbound(msg: OutboundMessage) -> None
consume_outbound() -> OutboundMessage
inbound_size -> int
outbound_size -> int
```

### publish_inbound

由 Channel 调用，把用户消息放进 inbound 队列。

### consume_inbound

由 AgentLoop 调用，等待下一条用户消息。

### publish_outbound

由 AgentLoop 调用，把 Agent 回复放进 outbound 队列。

### consume_outbound

由 Channel 调用，等待下一条 Agent 回复。

### inbound_size / outbound_size

用于测试、调试和简单状态观察。

## 数据结构

第一阶段建议代码结构：

```text
myagent/
└── bus/
    ├── __init__.py
    ├── events.py
    └── queue.py
```

`events.py`：

- `InboundMessage`
- `OutboundMessage`

`queue.py`：

- `MessageBus`

## Session Key 设计

InboundMessage 提供一个 `session_key` 属性：

```text
session_key = session_key_override or f"{channel}:{chat_id}"
```

这样 AgentLoop 不需要理解不同通道的会话规则，只要使用 `session_key` 找当前会话即可。

CLI 第一阶段：

```text
channel = "cli"
chat_id = "default"
session_key = "cli:default"
```

后续 `/new` 可以创建新 chat_id，例如：

```text
cli:session-20260505-001
```

## 与其他模块的关系

### CLI Channel

CLI Channel 依赖 MessageBus：

- 用户输入后调用 `publish_inbound`
- 后台等待 `consume_outbound` 并打印

### AgentLoop

AgentLoop 依赖 MessageBus：

- 通过 `consume_inbound` 获取用户消息
- 处理完成后调用 `publish_outbound`

### Session

Session 不直接依赖 MessageBus，但会使用 `InboundMessage.session_key` 区分会话。

### Trace

Trace 不直接控制 MessageBus，但可以在 AgentLoop 消费和发布消息时记录事件。

## 第一阶段范围

第一阶段只实现：

- 内存队列
- 单进程异步消息传递
- inbound/outbound 两条队列
- 基础消息 dataclass
- `session_key` 属性
- 队列 size 属性

## 暂不实现

第一阶段暂不实现：

- 消息持久化
- 消息重试
- 消息优先级
- 多消费者广播
- 跨进程或分布式队列
- 队列关闭和 drain 机制
- backpressure 策略
- 消息 schema 版本迁移
- media/file 消息

这些能力对生产系统有价值，但对第一阶段“跑通 Agent 主链路”不是必要条件。

## 最小测试点

建议测试文件：

```text
tests/test_message_bus.py
```

测试点：

1. `test_inbound_message_default_session_key`
   - 不传 `session_key_override` 时，`session_key` 等于 `channel:chat_id`。

2. `test_inbound_message_override_session_key`
   - 传入 `session_key_override` 时，优先使用 override。

3. `test_message_bus_delivers_inbound_message`
   - `publish_inbound` 后可以通过 `consume_inbound` 取到同一条消息。

4. `test_message_bus_delivers_outbound_message`
   - `publish_outbound` 后可以通过 `consume_outbound` 取到同一条消息。

5. `test_message_bus_reports_queue_sizes`
   - 发布消息后 size 增加，消费后 size 减少。

这些测试足够证明 MessageBus 的第一阶段核心行为。

## 面试表达

可以这样讲：

> 我在 MyAgent 里设计了一个很轻量的 MessageBus，用两个 `asyncio.Queue` 解耦输入通道和 AgentLoop。这样 CLI、未来的 IM 通道或者 Web UI 都只需要把用户消息转换成统一的 `InboundMessage`，AgentLoop 只消费统一格式，不需要关心消息来源。第一阶段我没有做持久化队列、优先级和广播，因为项目目标是面试展示和最小可运行闭环，这些复杂能力可以作为后续扩展。

如果面试官追问“为什么不用复杂消息队列”，可以回答：

> 当前是单进程本地 Agent runtime，`asyncio.Queue` 已经足够。真正需要 Redis、RabbitMQ 或 Kafka 的场景，一般是多进程、多实例、可靠投递或高吞吐系统。MyAgent 第一阶段不解决这些问题，所以先保持简单。

## 后续扩展方向

如果以后要增强 MessageBus，可以考虑：

- 给消息加 `message_id`
- 增加 `correlation_id` 支持 trace 配对
- 增加 `MessageType`
- 支持队列关闭
- 支持多 channel manager
- 支持持久化 session replay
- 支持后台任务完成后 publish inbound
- 演进为外部消息队列，例如 Redis Streams、RabbitMQ、Kafka

这些扩展都可以在不改变核心接口的前提下逐步加入。

### 外部消息队列扩展

当前第一阶段使用 `asyncio.Queue`，因为 MyAgent 是单进程本地 Agent runtime，重点是跑通主链路。

如果后续要支持多进程、多实例、可靠投递或任务堆积，可以把 MessageBus 的底层实现替换为外部消息队列：

- Redis Streams：适合轻量部署、消费组、简单持久化。
- RabbitMQ：适合明确的生产者/消费者模型、ack/retry、路由规则。
- Kafka：适合高吞吐、事件流、长期日志型消息。

为了给这种升级留空间，第一阶段的业务代码只依赖 `publish_inbound`、`consume_inbound`、`publish_outbound`、`consume_outbound` 这几个接口，不直接操作底层队列对象。

## 第一阶段实现说明

本次已经完成 MessageBus 的第一阶段代码实现。

实现目标：

```text
建立项目骨架，并让 MessageBus 可以被单独测试验证。
```

相关文件：

```text
pyproject.toml
myagent/__init__.py
myagent/__main__.py
myagent/bus/__init__.py
myagent/bus/events.py
myagent/bus/queue.py
tests/test_message_bus.py
.gitignore
```

### 项目骨架

`pyproject.toml` 定义了 MyAgent 作为 Python 项目的基础信息：

- 项目名：`myagent`
- Python 版本：`>=3.11`
- 运行依赖：`typer`、`openai`、`pydantic`
- 开发依赖：`pytest`、`pytest-asyncio`
- 命令入口：`myagent = "myagent.__main__:main"`
- 测试目录：`tests`

当前 `myagent/__main__.py` 只是一个占位入口：

```text
python -m myagent
```

运行后输出：

```text
MyAgent project skeleton is ready.
```

这个入口后续会替换为真正的 CLI。

### events.py

`myagent/bus/events.py` 放消息数据结构。

第一阶段有两个 dataclass：

```text
InboundMessage
OutboundMessage
```

#### InboundMessage

表示“用户或通道发给 Agent 的消息”。

核心字段：

```text
channel
sender_id
chat_id
content
timestamp
metadata
session_key_override
```

最重要的是 `session_key` 属性：

```text
session_key = session_key_override or f"{channel}:{chat_id}"
```

它的作用是给 AgentLoop 和 Session 一个统一会话标识。

例如 CLI 阶段：

```text
channel = "cli"
chat_id = "default"
session_key = "cli:default"
```

这样后续就算接入 Telegram、Slack 或 Web UI，也可以统一通过 `session_key` 区分会话。

#### OutboundMessage

表示“Agent 要发回通道的消息”。

核心字段：

```text
channel
chat_id
content
reply_to
metadata
```

第一阶段只处理文本消息，所以没有加入 `media` 字段。

### queue.py

`myagent/bus/queue.py` 放 MessageBus 本体。

它内部有两个队列：

```text
_inbound: asyncio.Queue[InboundMessage]
_outbound: asyncio.Queue[OutboundMessage]
```

两个队列的含义：

- `_inbound`：Channel -> AgentLoop
- `_outbound`：AgentLoop -> Channel

核心方法：

```text
publish_inbound
consume_inbound
publish_outbound
consume_outbound
```

这四个方法就是后续模块依赖的稳定接口。

代码里的关系可以理解成：

```text
CLI Channel
  -> publish_inbound()
  -> AgentLoop consume_inbound()
  -> AgentLoop publish_outbound()
  -> CLI Channel consume_outbound()
```

### 为什么属性名使用 `_inbound` / `_outbound`

实现里队列变量名前面加了 `_`：

```text
self._inbound
self._outbound
```

意思是：外部模块不要直接操作底层队列，而是通过公开方法访问。

这样未来即使底层从 `asyncio.Queue` 换成 Redis Streams、RabbitMQ，也不需要大改 CLI 或 AgentLoop。

### tests/test_message_bus.py

测试文件验证了 5 个核心行为：

1. 默认 `session_key` 是 `channel:chat_id`。
2. `session_key_override` 可以覆盖默认值。
3. inbound 消息发布后可以消费到。
4. outbound 消息发布后可以消费到。
5. 队列 size 会随发布和消费变化。

这些测试对应的是模块设计里的“最小测试点”。

### 本次验证结果

已执行：

```text
python -m pytest tests\test_message_bus.py
```

结果：

```text
5 passed
```

当前 MessageBus 是完整 Agent runtime 的一部分，CLI Channel 和 AgentLoop 已通过它跑通主链路。

### 临时缓存说明

第一次运行 pytest 时，本地环境生成过 `pytest-cache-files-*` 临时目录，并出现权限问题。

处理方式：

- 用户已手动删除该缓存目录。
- `.gitignore` 已忽略 `pytest-cache-files-*`。
- `pyproject.toml` 里通过 `addopts = "-p no:cacheprovider"` 关闭 pytest cache provider。

这样后续测试不会再依赖 pytest 缓存目录。

## 如何阅读这部分代码

建议按这个顺序读：

1. 先读 `tests/test_message_bus.py`，理解我们希望 MessageBus 做什么。
2. 再读 `myagent/bus/events.py`，看消息长什么样。
3. 最后读 `myagent/bus/queue.py`，看消息怎么进入和流出队列。

读代码时抓住一个主线：

```text
消息结构统一 -> 队列传递消息 -> 上下游模块通过接口通信
```

不要先纠结异步细节。`asyncio.Queue` 在这里可以先理解成“可以等待的内存队列”。

## Phase 2 Review

### 当前实现

MessageBus 保持最初设计：两个 `asyncio.Queue` 解耦 Channel 和 AgentLoop。

- `InboundMessage` / `OutboundMessage` 数据结构稳定
- `session_key` 机制支持多会话隔离
- 接口：`publish_inbound`、`consume_inbound`、`publish_outbound`、`consume_outbound`
- 队列 size 属性用于测试和状态观察

### 和原设计的差异

无显著差异。MessageBus 是 Phase 1 最早实现且变化最少的模块之一。

### 当前问题

1. 内存队列在进程退出时丢失消息。
   这是预期行为。MyAgent 是本地单进程 runtime，不需要持久化队列。

2. 没有 backpressure 机制。
   当前 CLI 是交互式的，用户一次只发一条消息，AgentLoop 用全局锁串行处理，不存在消息堆积问题。

3. 没有队列关闭和 drain 机制。
   当前 `stop()` 通过 AgentLoop 的 `_running` 标志控制。MessageBus 本身不需要显式关闭。

### 二期建议

不建议在 Phase 2 改动 MessageBus。当前实现足够稳定。

如果后续要支持多通道并发或后台任务，再考虑：
- 给消息加 `message_id` 和 `correlation_id`
- 增加队列关闭和 drain 机制
- 替换底层为 Redis Streams / RabbitMQ

### 暂不处理

- 消息持久化
- 消息优先级
- 多消费者广播
- 跨进程队列
- 复杂 backpressure

### 面试表达

> MessageBus 是 MyAgent 里最轻量的模块。两个 asyncio.Queue 解耦了输入通道和 AgentLoop，让 CLI、未来 IM 通道或 Web UI 都不需要关心 AgentLoop 的内部实现。第一阶段我不需要 Redis 或 RabbitMQ，因为本地单进程 runtime 的吞吐和可靠性需求完全可以用内存队列满足。

## 当前代码的边界

MessageBus 已完成其核心职责：单进程异步消息传递。

已接入：
- CLI Channel（publish_inbound / consume_outbound）
- AgentLoop（consume_inbound / publish_outbound）
- 所有测试（直接往 bus 塞消息验证行为）

尚未实现：
- 消息持久化
- 队列关闭和 drain
- 外部消息队列适配
- 消息优先级
