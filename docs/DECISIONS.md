# MyAgent 决策记录

## 项目身份

MyAgent 是一个参考 NanoBot、OpenClaw 等架构理念重新实现的 local-first 轻量异步个人助理 Agent runtime。

目标不是复刻 NanoBot 或 OpenClaw 的全部功能，也不是只做 Coding Agent，而是提炼一个适合学习、展示和面试讲解的个人助理 runtime。

长期方向：

```text
长期理解用户 -> 维护个人工作状态 -> 使用工具完成任务 -> 支持多通道协作
```

## 已确认决策

### 1. 命名

项目名：MyAgent

建议 Python 包名：`myagent`

理由：项目命名直接表达这是用户自己的 Agent 实现，避免和 NanoBot 混淆。

### 2. Context 设计

方向：模仿 NanoBot / OpenClaw 的分区式 context 设计。

第一阶段采用轻量实现：

- Identity
- Persona / User Profile（后续）
- Memory
- Skills
- Tools
- Conversation history

暂不做完整 token budget 管理，但保留 section/tier 的抽象空间，方便后续升级为 budget-aware composer。

### 3. Memory

方向：参考 OpenClaw 的 local-first personal memory 思路，同时吸收 ChatGPT Memory、Claude Code、Letta、LangGraph 等系统的分层经验。

第一阶段优先做能演示的版本，不追求完整长期记忆系统。Memory 可以先围绕文件型存储和简单召回实现。

Phase 2 新方向：

```text
profile  # 用户偏好、目标、协作方式
project  # 当前长期任务、项目状态、阶段决策
working  # 最近观察、候选信息、临时计划
```

不再把 Memory 只理解为当前代码项目状态，也不直接上向量库或 SQLite。

### 4. Skills

方向：扫描摘要 + 按需加载全文。

启动时扫描 `skills/` 目录下的 `SKILL.md`，提取名称和摘要注入 context。真正需要某个 skill 时，再读取完整 `SKILL.md`。

Phase 2 之后，Skills 应升级为个人助理的可复用工作流手册，而不是只作为 coding prompt 摘要。

### 5. MCP

目标：stdio + SSE 都可支持。

实现顺序建议：

1. 先实现 stdio MCP，跑通动态工具注册。
2. 再实现 SSE MCP，作为扩展能力。

### 6. 个人助理定位

已确认：MyAgent 不是只服务代码仓库的 Coding Agent。

源码仓库和运行时个人助理状态应分开：

```text
MyAgent repo
  用来开发 MyAgent 本身。

Agent workspace
  用来保存某个用户个人助理的 persona、user profile、memory、skills、tools notes。
```

后续可设计：

```text
~/.myagent/workspace/
  PERSONA.md
  USER.md
  MEMORY.md
  TOOLS.md
  memory/
  skills/
```

### 7. Channel 方向

CLI 是当前第一个入口。

后续 IM Channel 暂不急着实现；如果做，优先 QQ，并建议走 OneBot 兼容协议。

群聊能力默认保守：

- allowlist
- require mention
- 不让模型自由决定向任意 channel 发消息

## 面试表达口径

MyAgent 的核心取舍是：用最少模块展示个人助理 Agent runtime 的关键机制。

关键机制包括：

- MessageBus 解耦输入通道和 AgentLoop
- AgentLoop 串行执行 ReAct 循环
- ContextBuilder 统一组装模型上下文
- ToolRegistry 管理工具描述、校验和调用
- Memory 提供跨轮次信息保留
- Trace 记录运行过程，方便调试、审计和讲解
- Skills 提供可复用工作流
- MCP / ToolRegistry 提供连接外部世界的行动接口

新的表达口径：

> MyAgent 不是只会读代码和跑工具的 Coding Agent，而是一个 local-first 个人助理 runtime。CLI 是第一种入口，文件工具是第一批能力，真正长期价值来自 Memory、Skills、Workspace 和 Channel 的组合。

## 待确认问题

1. Agent Workspace 第一版是否需要落地到 `~/.myagent/workspace`？
2. Memory v2 是否先实现 profile/project/working 三层 JSONL？
3. QQ Channel 何时进入设计，是否只做私聊第一版？
