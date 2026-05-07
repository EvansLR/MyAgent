# MyAgent 总体架构设计

## 设计目标

MyAgent 是一个面向用户个人助理场景的 local-first、轻量、可教学、可面试的异步 Agent runtime。

它不是只服务代码仓库的一次性 Coding Agent，也不是生产级 Agent 平台。

它的核心目标是：

```text
让一个本地运行的个人助理 Agent 能长期理解用户、维护个人工作状态、通过工具完成任务，并且整个设计能被讲清楚。
```

当前实现仍然保留 ReAct 主循环作为最小决策框架，但后续设计重点不应只围绕“读代码、改代码、跑测试”，而应围绕个人助理能力：

- 用户消息如何进入系统
- Agent 如何维护 identity、persona、user profile 和 memory
- Agent 如何构建当前上下文
- LLM 如何决定是否调用工具
- 工具结果如何回到 LLM
- 运行过程如何被记录和解释
- Memory、Skills、MCP、SubAgent、Channel 如何作为个人助理能力接入

当前阶段的核心标准是：**能跑、能讲、能扩展，并逐步接近个人助理而不是 Coding Agent**。

## 个人助理定位

MyAgent 后续应引入 “Agent Workspace” 概念。

源码仓库和运行时个人助理状态需要分开：

```text
E:\ClaudeCode\openSource\MyAgent
  MyAgent 的源码项目。

~/.myagent/workspace/
  某个用户个人助理的长期状态。
```

运行时 workspace 可以参考 OpenClaw 这类 local-first personal agent 的分层：

```text
~/.myagent/workspace/
  AGENT.md        # 操作原则和运行约束
  PERSONA.md      # 助理的风格、边界和自我设定
  USER.md         # 用户画像、偏好、称呼和协作方式
  TOOLS.md        # 工具使用约定和风险提示
  MEMORY.md       # 精炼后的长期记忆
  memory/
    YYYY-MM-DD.md # working memory / daily notes
  skills/
    ...
```

第一版不必立即实现完整 workspace，但架构口径要明确：MyAgent 的目标是个人助理 runtime，代码项目能力只是其中一种任务类型。

## 总体分层

MyAgent 按职责分为 6 层：

```text
┌─────────────────────────────────────────────┐
│ Interface Layer                             │
│ CLI Channel / Future QQ Channel             │
├─────────────────────────────────────────────┤
│ Message Layer                               │
│ MessageBus / InboundMessage / OutboundMessage│
├─────────────────────────────────────────────┤
│ Runtime Layer                               │
│ AgentLoop / Session / Task Control          │
├─────────────────────────────────────────────┤
│ Intelligence Layer                          │
│ ContextBuilder / LLM Provider / Memory / Persona│
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
Channel
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
Channel
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

第一阶段只做本地单用户 CLI。后续如果扩展 IM，优先考虑 QQ Channel，并建议通过 OneBot 兼容协议接入。

Channel 层的边界：

- 把外部消息转换成 `InboundMessage`。
- 把 `OutboundMessage` 发送回对应通道。
- 处理通道级安全策略，例如 allowlist、群聊 require mention。
- 不把 QQ/IM 协议细节泄漏给 AgentLoop。

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
- 汇总 Identity、Persona、User Profile、Memory、Skills、Tools、Conversation

第一阶段采用分区式模板：

```text
Identity
Persona / User Profile
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

- 保存用户个人助理的长期工作状态
- 在构建上下文时提供可召回内容

第一阶段参考 NanoBot 思路做轻量版本：

- 文件型 memory
- 简单召回
- 可选总结

不急着做完整 active memory、SQLite、向量检索。

Phase 2 的新方向：

- Memory 不只是当前代码项目进度。
- Memory 应服务个人助理长期状态。
- 建议分为：

```text
profile  # 用户偏好、目标、协作方式
project  # 长期项目/任务状态和决策
working  # 最近观察、候选信息、临时计划
```

详见：

```text
docs/PERSONAL_AGENT_DIRECTION.md
docs/modules/MEMORY_PHASE2_RESEARCH.md
docs/modules/MEMORY.md
```

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

个人助理方向下，Skills 更接近可复用工作流手册：

- Memory 记事实、偏好和状态。
- Skills 记“怎么做事”。
- Tools 负责真实执行。

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
MYAGENT_CONFIG
MYAGENT_PROVIDER
MYAGENT_API_KEY
OPENAI_API_KEY
MYAGENT_BASE_URL
MYAGENT_MODEL
MYAGENT_SYSTEM_PROMPT
MYAGENT_PROVIDER_RETRIES
```

当前也支持本地 JSON 配置：

```text
myagent.json
```

可提交模板是：

```text
myagent.example.json
```

`myagent.json` 用于保存本地真实配置，已被 `.gitignore` 忽略，不能提交 API key、MCP key 或私有 URL。

当前 JSON 配置主要包含：

```text
provider
mcpServers
```

其中 `provider` 用于选择 EchoProvider 或 OpenAI-compatible provider；`mcpServers` 用于配置 stdio 或 HTTP/SSE 风格 MCP server。

后续如果要把 `max_iterations`、`workspace`、SubAgent profile、工具权限等纳入配置，应先在 `docs/modules/CONFIG.md` 校准设计，再实现。

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
- `myagent workspace`
- `myagent qq`

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
- Agent Workspace
- persona / user profile 文件体系
- Heartbeat 主动助理循环
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

Phase 2 之后，MyAgent 的解释口径应从：

```text
一个能跑 ReAct + tools 的本地 coding-ish agent
```

校准为：

```text
一个 local-first 个人助理 Agent runtime。
CLI 只是第一种通道，文件工具只是第一批能力，Memory/Skills/Workspace 才是长期个人助理体验的基础。
```
