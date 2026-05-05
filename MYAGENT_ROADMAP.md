# MyAgent 设计草案

## 项目定位

参考 NanoBot 架构理念，重新设计一个**轻量、可教学、可面试**的异步 ReAct Agent 运行时框架。

核心原则：**做减法**。只保留最必要的模块，每个模块都要能讲清楚设计决策。

本项目不是生产级 Agent 平台，当前目标是服务研究生面试场景：系统要能跑起来，架构要能讲清楚，工程化保持必要但不过度。

---

## 第一阶段：核心骨架（必做）

### 1. 消息总线（MessageBus）
- 内存队列，inbound/outbound
- 解耦 Channel 和 AgentLoop

### 2. CLI 通道
- `typer` 做命令行交互
- 支持 `/new`、`/stop`、`/help`

### 3. ReAct 主循环（AgentLoop）
- LLM → Tool → Result → LLM 循环
- 全局锁串行处理（简化并发）
- 最大迭代次数限制

### 4. 上下文构建（ContextBuilder）
- System prompt 组装（Identity + Memory + Skills + Tools）
- **你的设计**：Context 怎么组织？固定模板还是动态预算？

### 5. LLM Provider
- OpenAI 兼容接口（`openai` SDK）
- 支持配置不同模型（主模型 / summary 模型 / subagent 模型）
- 简单重试逻辑

### 6. 工具层
- ToolRegistry（注册表）
- 内置工具：read_file、write_file、edit_file、list_dir、exec、web_search
- 参数 JSON Schema 校验

### 7. MCP 扩展
- stdio 连接外部 MCP 服务器
- 动态工具注册到 ToolRegistry（`mcp_{server}_{tool}`）
- 工具超时控制
- **sse 连接后续扩展**

### 7. 记忆层（Memory）
- **你的设计**：HISTORY.md + MEMORY.md 文件型？还是 SQLite？
- 召回机制：关键词？时间衰减？复合打分？
- 压缩策略：LLM 总结 or 规则归档？

### 8. Trace
- JSONL append-only
- 事件枚举（StrEnum）
- correlation_id 配对
- 损坏容忍 + 自动清理

### 9. Skills（技能插件）
- `skills/` 目录自动扫描
- SKILL.md 解析
- **你的设计**：全量加载？按需加载？摘要 + 按需全文？

### 10. SubAgent（同步委托）
- `delegate_task` 工具
- 只读工具集
- 独立模型配置

---

## 第二阶段：扩展能力（建议做）

### 11. MCP 工具扩展
- stdio / sse 连接外部 MCP 服务器
- 动态工具注册到 ToolRegistry
- **简化策略**：先只做 stdio，sse 后续扩展

### 12. Budget-aware Context Composer
- 4 级 Tier 优先级（PROTECTED / HIGH / MEDIUM / LOW）
- 超预算时逐步降级
- **前提**：Phase 1 的 ContextBuilder 设计要预留扩展点

---

## 第三阶段：有时间再考虑（优先级很低）

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

**为什么不现在做**：
- 每个通道需要独立的认证、消息格式、错误处理
- 核心框架的验证不依赖 IM 通道
- CLI 已足够展示框架能力

**后续方向**：
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
2. **Context 设计** — 模仿 NanoBot 的分区式上下文设计，但在 MyAgent 中做轻量化实现，并预留后续 budget/tier 扩展点。
3. **Memory 方案** — 参考 NanoBot 的 memory 思路，先做够演示和面试讲解的轻量版本。
4. **Skills 加载** — 采用“扫描摘要 + 按需加载全文”的方向。
5. **MCP 范围** — 目标上支持 stdio + SSE；实现时可以先 stdio，再补 SSE。

## 开发节奏

1. 任何代码实现之前，先补齐对应文档。
2. 每次实现前查阅并校准文档，避免偏离“轻量、可教学、可面试”的目标。
3. 每个模块完成并经用户确认、测试后，再进行 Git 提交。
4. Git 提交以模块为单位，不追求每个小步骤都提交。
