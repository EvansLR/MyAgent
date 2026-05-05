# MyAgent 总体架构设计

## 设计目标

MyAgent 是一个面向学习和面试展示的轻量异步 ReAct Agent runtime。

它的目标不是复刻 NanoBot 的全部工程能力，而是提炼 Agent 系统里最关键的运行机制：

- 用户消息如何进入系统
- Agent 如何构建上下文
- LLM 如何决定是否调用工具
- 工具结果如何回到 LLM
- 运行过程如何被记录和解释
- Memory、Skills、MCP、SubAgent 如何作为扩展能力接入

第一阶段的核心标准是：**能跑、能讲、能扩展**。

## 总体分层

MyAgent 按职责分为 6 层：

```text
┌─────────────────────────────────────────────┐
│ Interface Layer                             │
│ CLI Channel                                 │
├─────────────────────────────────────────────┤
│ Message Layer                               │
│ MessageBus / InboundMessage / OutboundMessage│
├─────────────────────────────────────────────┤
│ Runtime Layer                               │
│ AgentLoop / Session / Task Control          │
├─────────────────────────────────────────────┤
│ Intelligence Layer                          │
│ ContextBuilder / LLM Provider / Memory      │
├─────────────────────────────────────────────┤
│ Capability Layer                            │
│ ToolRegistry / Built-in Tools / Skills / MCP│
├─────────────────────────────────────────────┤
│ Observability Layer                         │
│ Trace JSONL / Summary / Debug Reports       │
└─────────────────────────────────────────────┘
```

依赖方向尽量保持单向：上层调用下层能力，下层不反向依赖具体入口。

## 核心数据流

最小运行闭环如下：

```text
User
  ↓
CLI Channel
  ↓ publish_inbound
MessageBus
  ↓ consume_inbound
AgentLoop
  ↓ build context
ContextBuilder
  ↓ request
LLM Provider
  ↓ tool calls?
ToolRegistry
  ↓ tool result
AgentLoop
  ↓ publish_outbound
MessageBus
  ↓ consume_outbound
CLI Channel
  ↓
User
```

如果 LLM 不调用工具，则 `AgentLoop` 直接输出最终回答。

如果 LLM 调用工具，则 `AgentLoop` 执行：

```text
LLM -> Tool -> Result -> LLM
```

循环直到得到最终回答，或达到最大迭代次数。

## 推荐目录结构

第一阶段建议目录如下：

```text
MyAgent/
├── MYAGENT_ROADMAP.md
├── pyproject.toml
├── docs/
│   ├── ARCHITECTURE.md
│   ├── DECISIONS.md
│   ├── DEVELOPMENT_WORKFLOW.md
│   ├── PHASE1_PLAN.md
│   └── modules/
│       ├── MESSAGE_BUS.md
│       ├── CLI_CHANNEL.md
│       ├── AGENT_LOOP.md
│       ├── CONTEXT_BUILDER.md
│       ├── LLM_PROVIDER.md
│       ├── TOOL_REGISTRY.md
│       ├── MEMORY.md
│       ├── TRACE.md
│       ├── SKILLS.md
│       ├── MCP.md
│       └── SUBAGENT.md
├── myagent/
│   ├── __init__.py
│   ├── __main__.py
│   ├── bus/
│   │   ├── __init__.py
│   │   ├── events.py
│   │   └── queue.py
│   ├── cli/
│   │   ├── __init__.py
│   │   └── commands.py
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── loop.py
│   │   ├── context.py
│   │   ├── memory.py
│   │   ├── skills.py
│   │   └── subagent.py
│   ├── providers/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   └── openai_compatible.py
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── registry.py
│   │   ├── filesystem.py
│   │   ├── shell.py
│   │   ├── web.py
│   │   └── mcp.py
│   ├── tracing/
│   │   ├── __init__.py
│   │   ├── events.py
│   │   └── store.py
│   └── config/
│       ├── __init__.py
│       └── settings.py
├── skills/
│   └── example/
│       └── SKILL.md
├── data/
│   ├── memory/
│   ├── sessions/
│   └── traces/
└── tests/
    ├── test_message_bus.py
    ├── test_cli_channel.py
    ├── test_agent_loop.py
    └── test_tool_registry.py
```

这个结构和 NanoBot 相似，但明显更薄：保留核心模块边界，暂时不引入多 IM 通道、复杂服务端、定时任务和完整生产配置。

## 模块职责

### Interface Layer

#### CLI Channel

职责：

- 接收用户命令行输入
- 解析 `/new`、`/stop`、`/help`
- 将普通消息封装成 `InboundMessage`
- 消费 `OutboundMessage` 并打印给用户

第一阶段只做本地单用户 CLI，不做 Telegram、Slack、Discord 等 IM 通道。

### Message Layer

#### MessageBus

职责：

- 用内存异步队列解耦 Channel 和 AgentLoop
- 提供 inbound/outbound 两条消息通道
- 统一消息数据结构

核心价值：

- Channel 不需要知道 AgentLoop 怎么运行
- AgentLoop 不需要知道消息来自 CLI 还是未来的 IM 通道

### Runtime Layer

#### AgentLoop

职责：

- 消费 inbound 消息
- 构建上下文
- 调用 LLM
- 执行工具调用
- 将工具结果回灌给 LLM
- 发布 outbound 消息

第一阶段设计：

- 全局锁串行处理，避免并发复杂度
- 最大迭代次数限制，避免无限 tool loop
- 每次 turn 记录 trace

#### Session

职责：

- 保存当前会话的消息历史
- 为 ContextBuilder 提供 conversation history

第一阶段可以先用内存结构，后续再扩展文件或 SQLite 持久化。

### Intelligence Layer

#### ContextBuilder

职责：

- 统一组织发给 LLM 的上下文
- 汇总 Identity、Memory、Skills、Tools、Conversation

第一阶段采用分区式模板：

```text
Identity
Memory
Available Skills
Available Tools
Conversation
```

暂不做完整 token budget，但内部保留 section 概念，为后续 budget-aware composer 做铺垫。

#### LLM Provider

职责：

- 封装 OpenAI 兼容接口
- 屏蔽 SDK 调用细节
- 输出统一的 assistant message / tool call 结构

第一阶段只实现一个 OpenAI-compatible provider。多 provider registry 暂不做。

#### Memory

职责：

- 保存跨轮次重要信息
- 在构建上下文时提供可召回内容

第一阶段参考 NanoBot 思路做轻量版本：

- 文件型 memory
- 简单召回
- 可选总结

不急着做完整 active memory、SQLite、向量检索。

### Capability Layer

#### ToolRegistry

职责：

- 注册工具
- 暴露工具描述和 JSON Schema
- 校验参数
- 执行工具

内置工具：

- `list_dir`
- `read_file`
- `write_file`
- `edit_file`
- `exec`
- `web_search`

第一阶段可以优先实现文件和 shell 工具，`web_search` 可后置。

#### Skills

职责：

- 扫描 `skills/*/SKILL.md`
- 提取 skill 名称、描述和触发说明
- 将摘要注入 context
- 按需读取全文

Skills 是“提示词能力扩展”，不是 Python 插件系统。第一阶段保持简单。

#### MCP

职责：

- 连接外部 MCP server
- 将 MCP tools 动态注册到 ToolRegistry

目标支持：

- stdio
- SSE

实现顺序建议先 stdio，再 SSE。

#### SubAgent

职责：

- 提供同步委托工具 `delegate_task`
- 用独立模型配置执行一个子任务
- 返回子任务结果给主 Agent

第一阶段只做同步委托，不做后台 spawn。

### Observability Layer

#### Trace

职责：

- 用 JSONL 记录 Agent 运行过程
- 支持调试和面试讲解

基础事件：

- `user_message`
- `context_built`
- `llm_request`
- `llm_response`
- `tool_call`
- `tool_result`
- `final_answer`
- `error`

第一阶段不做复杂可视化，只保证 trace 文件可读、可回放、可解释。

## 配置设计

第一阶段配置保持轻量：

```text
MYAGENT_MODEL
MYAGENT_API_KEY
MYAGENT_BASE_URL
MYAGENT_MAX_ITERATIONS
MYAGENT_WORKSPACE
```

可以先使用环境变量和简单 `Settings` 类，不急着做复杂配置文件和迁移逻辑。

## 运行模式

第一阶段只支持一种运行模式：

```text
python -m myagent
```

或通过脚本入口：

```text
myagent
```

后续可扩展：

- `myagent chat`
- `myagent trace`
- `myagent memory`
- `myagent skills`

## 实现路线

### Milestone 0：文档与项目骨架

目标：

- 完成总体架构文档
- 为第一批模块补设计文档
- 初始化 Python 项目结构

产出：

- `docs/ARCHITECTURE.md`
- `docs/modules/MESSAGE_BUS.md`
- `pyproject.toml`
- `myagent/`
- `tests/`

### Milestone 1：消息流闭环

目标：

- CLI 能输入
- MessageBus 能传递消息
- AgentLoop 能消费消息
- EchoProvider 能返回响应
- CLI 能打印响应

这是第一个可运行版本。

### Milestone 2：真实 LLM 闭环

目标：

- 接入 OpenAI-compatible provider
- ContextBuilder 生成基础上下文
- LLM 可以正常回复

### Milestone 3：工具调用闭环

目标：

- ToolRegistry 可注册工具
- LLM 可以调用工具
- 工具结果能回灌给 LLM

### Milestone 4：可观察性与记忆

目标：

- Trace JSONL 记录完整 turn
- Memory 提供简单保存和召回

### Milestone 5：扩展能力

目标：

- Skills 扫描和按需加载
- MCP 动态工具注册
- SubAgent 同步委托

## 模块文档规则

每个模块实现前必须有独立设计文档。

模块文档放在：

```text
docs/modules/
```

推荐结构：

```text
# 模块名

## 职责
## 为什么需要它
## 输入输出
## 核心接口
## 数据结构
## 与其他模块的关系
## 第一阶段范围
## 暂不实现
## 测试点
## 面试表达
```

实现前先写文档；实现中如果发现设计变化，先更新文档再改代码。

## 第一阶段暂不追求的能力

以下能力有价值，但不作为第一阶段重点：

- 多 IM 通道
- 完整 Web UI
- 完整 checkpoint/resume
- SQLite session migration
- 大规模插件市场
- 完整权限系统
- 复杂并发任务编排
- 向量数据库 RAG

这些能力可以作为面试中的“后续扩展方向”来讲。

## 总结

MyAgent 的整体架构是一个轻量 Agent runtime：

```text
Channel -> MessageBus -> AgentLoop -> Context/LLM/Tools -> MessageBus -> Channel
```

Memory、Skills、MCP、SubAgent 都围绕这个主链路扩展。

第一阶段不要追求大而全，先把主链路跑通，再让每个扩展模块逐步接入。
