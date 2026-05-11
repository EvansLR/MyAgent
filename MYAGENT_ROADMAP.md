# MyAgent Roadmap

## 项目定位

参考 NanoBot 和 OpenClaw 等 Agent 架构理念，重新设计一个**local-first、轻量、可教学、可面试**的个人助理 Agent runtime。

核心原则：**做减法**。只保留最必要的模块，每个模块都要能讲清楚设计决策。

本项目不是生产级 Agent 平台，也不是只服务代码仓库的一次性 Coding Agent。

当前目标是服务学习、演示和面试场景：系统要能跑起来，架构要能讲清楚，工程化保持必要但不过度。同时，长期方向要明确指向用户个人助理：

```text
长期理解用户 -> 维护个人工作状态 -> 使用工具完成任务 -> 支持多通道协作
```

因此，代码项目能力只是 MyAgent 的一个任务场景，不是最终边界。

---

## 当前状态

Phase 1 已经完成：MyAgent 现在有一个可运行、可测试、可讲解的轻量 ReAct Agent runtime。

但 Phase 2 的定位已经校准：后续升级不能只沿着 Coding Agent 方向堆工具，而要把 MyAgent 往 local-first personal assistant runtime 推进。

已完成的主链路是：

```text
CLI Channel
  -> MessageBus
  -> AgentLoop
  -> ContextBuilder
  -> LLM Provider
  -> ToolRegistry
  -> tool result
  -> AgentLoop
  -> CLI Channel
```

已完成的扩展能力包括：

- JSON 配置文件和环境变量覆盖。
- Rich CLI 状态展示和 Markdown 渲染。
- OpenAI-compatible provider 和 EchoProvider。
- ToolRegistry 注册、schema、参数校验和执行。
- 默认内置工具：
  - 文件工具：`list_dir`、`read_file`、`write_file`、`edit_file`、`copy_file`、`move_file`
  - Web 工具：`web_search`、`web_fetch`
- JSONL Trace。
- 文件型 Memory 保存和简单召回。
- Skills 扫描和上下文注入。
- MCP stdio 和 HTTP/SSE 风格工具接入。
- SubAgent 同步委托工具 `delegate_task`。

最近一次记录的全量测试结果是：

```text
python -m pytest
80 passed, 1 skipped
```

跳过项是 `tests/test_mcp_stdio.py`，原因是当前 Windows 沙箱可能限制 asyncio subprocess pipe；这是已知环境限制。

---

## Phase 1：核心骨架（已完成）

### 1. 消息总线（MessageBus）
- 已实现内存队列，包含 inbound/outbound。
- 已解耦 Channel 和 AgentLoop。

### 2. CLI 通道
- 已实现本地命令行入口。
- 支持普通消息、`/new`、`/stop`、`/help`。
- 已加入 Rich 状态展示和 Markdown 渲染。

### 3. ReAct 主循环（AgentLoop）
- 已实现 LLM -> Tool -> Result -> LLM 循环。
- 已用全局锁串行处理，降低第一版并发复杂度。
- 已加入最大迭代次数限制。
- 已接入 memory、skills、trace、MCP、SubAgent 等扩展点。

### 4. 上下文构建（ContextBuilder）
- 已实现分区式上下文组装。
- 当前包含 Identity、Memory、Skills、Tools、Conversation 等 section。
- 暂未实现完整 token budget，后续可升级为 budget-aware composer。

### 5. LLM Provider
- 已实现 OpenAI-compatible provider。
- 已保留 EchoProvider，方便本地测试和最小闭环验证。
- 当前 SubAgent 与主 Agent 共用 provider；独立模型配置作为 Phase 2 复盘项。

### 6. 工具层
- 已实现 ToolRegistry 注册表。
- 已实现工具描述、JSON Schema、参数校验和执行。
- 当前主 Agent 默认工具集包括：
  - 文件工具：`list_dir`、`read_file`、`write_file`、`edit_file`、`copy_file`、`move_file`
  - Web 工具：`web_search`、`web_fetch`
- 工作区内变更型文件操作允许直接执行；工作区外变更型文件操作通过当前 Channel 走审批流程。
- `exec` 仍未实现，原因是当前阶段优先保持安全边界清楚、可解释、可面试。

### 7. MCP 扩展
- 已实现 stdio MCP 接入。
- 已实现 HTTP/SSE 风格 MCP 接入。
- 已支持动态工具注册到 ToolRegistry。
- 超时、重试、禁用配置和真实 MCP server 体验仍属于 Phase 2 复盘项。

### 8. 记忆层（Memory）
- 已实现文件型 memory 存储。
- 已实现显式保存和简单召回。
- 当前召回仍偏简单，Phase 2 应重点升级为更值得讲的记忆机制。

### 9. Trace
- 已实现 JSONL append-only 运行轨迹。
- 已记录基础 turn、LLM、tool、memory、subagent 事件。
- correlation id、树形 trace、trace summary/inspect、损坏容忍和清理仍属于后续增强。

### 10. Skills（技能）
- 已实现 `skills/*/SKILL.md` 扫描。
- 已实现摘要提取和上下文注入。
- 自动读取 skill 全文、模型主动选择 skill、skill 与 SubAgent profile 绑定仍属于 Phase 2 复盘项。

### 11. SubAgent（同步委托）
- 已实现 `delegate_task` 工具。
- 子 Agent 按 profile 暴露受限只读工具集：
  - 本地只读：`list_dir`、`read_file`
  - 部分 profile 可用只读 web 工具：`web_search`、`web_fetch`
- 已内置 `researcher`、`reviewer`、`interviewer` profile。
- 子 Agent 不继承 `write_file`、`edit_file`、`copy_file`、`move_file`、MCP tools 或递归 `delegate_task`。
- 当前使用独立 prompt，但与主 Agent 共用 provider；独立模型配置、profile 配置化和更完整 trace tree 属于 Phase 2 复盘项。

---

## Phase 2：模块复盘与重点升级（当前阶段）

Phase 2 不急着堆新功能，而是按模块复盘：

- 当前实现是否和文档一致。
- 当前能力是否足够稳定。
- 哪些地方影响演示和面试表达。
- 哪些增强应该实现，哪些继续后置。
- 当前设计是否偏向 coding agent，是否需要拉回个人助理方向。

第一轮建议先做：

1. Project Docs / Roadmap 校准。
2. Config 复盘。
3. CLI Channel 体验复盘。
4. Memory 复盘。
5. Skills 复盘。
6. SubAgent 复盘。
7. Personal Agent Direction 校准。

其中 Memory 和 Skills 是最值得重点提升的两个模块。

### Memory 升级方向

- 以 OpenClaw 这类 local-first personal agent 为主参考。
- 不把 memory 限定为当前代码项目状态。
- 采用 `profile / project / working` 三层。
- 继续保持文件型存储，避免过早引入 SQLite 或向量库。
- 从简单关键词召回升级为可解释的复合召回。
- 增加用户可查看、可删除、可整理的路径。

### Skills 升级方向

- 从“摘要注入”升级为更明确的“可激活能力”。
- 明确模型如何知道有哪些 skill、什么时候需要读取全文。
- 评估是否把 skill 全文读取暴露成受控工具。
- 评估 skill 是否要和 SubAgent profile 绑定。
- 将 Skills 解释为个人助理的可复用工作流手册，而不是单纯 coding prompt。

### Personal Agent Workspace 方向

- 区分 MyAgent 源码仓库和运行时个人助理 workspace。
- 后续设计类似：

```text
~/.myagent/workspace/
  PERSONA.md
  USER.md
  MEMORY.md
  TOOLS.md
  memory/
  skills/
```

- ContextBuilder 后续应能读取 persona、user profile、memory 和 skills。
- 暂不急着完整实现，但 Roadmap 必须避免把项目锁死在 Coding Agent。

### SubAgent 升级方向

- 评估 profile 是否配置化。
- 评估是否需要独立模型配置。
- 评估子 Agent 内部工具调用是否展示到 CLI。
- 评估是否需要树形 trace。

---

## Phase 2 之后的扩展能力（建议做）

### 11. MCP 工具扩展
- 更稳定的真实 MCP server 接入体验。
- 更清楚的错误提示、超时、重试、禁用配置。
- 工具命名和 schema 兼容性整理。

### 12. Budget-aware Context Composer
- 4 级 Tier 优先级（PROTECTED / HIGH / MEDIUM / LOW）
- 超预算时逐步降级
- 基于当前 ContextBuilder section 结构继续演进。

---

## Phase 3：有时间再考虑（优先级很低）

> 以下功能有价值，但不影响核心框架的完整性和面试表达。记录下来作为后续方向，当前阶段不投入开发。

### 13. `ask_user` 安全确认闸

**问题**：Agent 在执行高风险操作（删除文件、sudo 执行、覆盖生产配置）时，应该向用户确认。

**为什么不现在做**：
- 需要设计风险检测规则（哪些操作算"高风险"）
- 需要暂停/恢复 ReAct 循环的状态机
- 大多数场景用普通文本回复即可覆盖

**后续方向**：
- 不是给模型的自由工具，而是框架层安全闸
- 当 `exec`/`write_file`/`edit_file` 检测到高风险模式时自动触发
- 风险等级（low/medium/high）决定确认方式

---

### 14. 多通道支持（IM 集成）

**问题**：支持 Telegram、Discord、Slack、飞书、钉钉等通道。

当前用户偏好：

- 先不急着做 IM Channel。
- 先把 Agent 本体跑通、跑稳、跑得更有效率。
- 如果以后做 IM，优先考虑 QQ；微信暂不优先。
- QQ 建议优先考虑 OneBot 兼容协议，让 MyAgent 对接标准 Channel 层，而不是直接处理 QQ 登录和底层协议。

**为什么不现在做**：
- 每个通道需要独立的认证、消息格式、错误处理
- 核心框架的验证不依赖 IM 通道
- CLI 已足够展示框架能力

**后续方向**：
- QQ Channel 作为独立模块文档设计，例如 `docs/modules/QQ_CHANNEL.md`
- 第一版可以只支持私聊，群聊响应和命令前缀后置决策
- 通过 OneBot HTTP/WebSocket 兼容服务接入，降低协议和登录复杂度
- 继承 BaseChannel 抽象基类
- ChannelManager 自动发现（pkgutil + entry_points）
- 先加 Discord 或 Telegram（社区文档最完善）

---

### 15. `spawn` 后台异步子代理

**问题**：启动一个后台任务，做完后通过消息总线汇报结果。

**为什么不现在做**：
- 和 `delegate_task` 有重叠，但异步语义更复杂
- 需要后台任务生命周期管理（取消、超时、状态查询）
- 面试时 `delegate_task` 的成本分层故事已经足够

**后续方向**：
- SubagentManager 增加 `spawn()` 方法
- asyncio.Task 后台执行
- 完成后通过 `publish_inbound` 注入结果

---

### 16. 文档 RAG（向量检索）

**问题**：用 embedding + 向量库（ChromaDB）对用户上传的文档做语义检索，将相关段落注入上下文。

**为什么不现在做**：
- 增加外部依赖（sentence-transformers + ChromaDB），破坏轻量定位
- 和 Memory 召回功能边界容易混淆
- 关键词匹配 + 复合打分在大多数场景够用
- 面试时"为什么先不做向量检索"本身就是可讲的设计取舍

**后续方向**：
- 作为独立知识源（区别于 episodic memory）
- 可选模块，默认关闭
- 用 sentence-transformers（本地模型）+ ChromaDB（本地文件型）
- 提供 `add_document` / `query` 简单接口

---

### 17. 持久化 Session（SQLite）

**问题**：当前 Session 是内存 + JSONL 文件，重启后丢失。

**为什么不现在做**：
- 文件型 Session 已足够演示
- SQLite 迁移涉及 schema 设计、迁移脚本、回滚策略
- 不是核心面试亮点

**后续方向**：
- SQLite 存储消息历史
- 支持 Session 查询、导出、回放

---

### 18. Web UI

**问题**：浏览器界面展示对话、trace、memory。

**为什么不现在做**：
- 前端开发量大，偏离"后端运行时"的核心定位
- CLI + trace summary 已足够诊断

**后续方向**：
- FastAPI + SSE 推送
- 前端展示 trace 时间线

---

### 19. 多 Agent 协作

**问题**：多个 Agent 实例之间通信、分工、共识。

**为什么不现在做**：
- 复杂度高，容易做成空泛的概念堆砌
- 当前项目体量不匹配

**后续方向**：
- 消息总线支持多 Agent 订阅
- Agent 间通过特定 topic 通信

---

### 20. Checkpoint / Resume

**问题**：运行中断后恢复，支持回放。

**为什么不现在做**：
- 需要完整的状态序列化（消息、工具状态、plan、memory）
- 和 LangGraph / OpenAI Agents 的思路一致，但实现成本高

**后续方向**：
- 每个 turn 结束后快照状态到 SQLite
- 支持从任意 checkpoint 恢复

---

## 已确认决策

1. **命名** — 项目名为 MyAgent，Python 包名建议为 `myagent`。
2. **项目定位** — MyAgent 是 local-first 个人助理 Agent runtime，不是只服务代码仓库的 Coding Agent。
3. **Context 设计** — 模仿 NanoBot / OpenClaw 的分区式上下文设计，但在 MyAgent 中做轻量化实现，并预留后续 persona、user profile、memory、skills、budget/tier 扩展点。
4. **Memory 方案** — 优先参考 OpenClaw 的 personal memory 思路，采用 `profile / project / working` 三层方向，先做本地文件型和可解释召回。
5. **Skills 加载** — 采用“扫描摘要 + 按需加载全文”的方向，后续升级为个人助理可复用工作流。
6. **MCP 范围** — 目标上支持 stdio + SSE；实现时可以先 stdio，再补 SSE。
7. **Channel 方向** — CLI 是第一入口，后续 IM 优先考虑 QQ + OneBot 兼容协议，群聊默认保守。

## 开发节奏

1. 任何代码实现之前，先补齐对应文档。
2. 每次实现前查阅并校准文档，避免偏离“轻量、可教学、可面试”的目标。
3. 每个模块完成并经用户确认、测试后，再进行 Git 提交。
4. Git 提交以模块为单位，不追求每个小步骤都提交。
