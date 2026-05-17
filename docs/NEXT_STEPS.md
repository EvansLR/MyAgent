# MyAgent 当前状态与下一步

这份文档用于跨对话续接。
新对话开始时，先读这里，再看 `docs/PHASE2_REVIEW_PLAN.md`、相关模块文档和代码。

## 当前项目目标

MyAgent 的当前定位已经校准为：

```text
一个 local-first、轻量、可教学、可面试讲解的个人助理 Agent runtime。
```

它不是生产级 Agent 平台，也不是只服务代码仓库的 Coding Agent。

当前阶段的主要目标是：

- 主链路稳定可运行。
- 核心模块边界清楚、文档和实现一致。
- 关键能力有 focused tests 和可讲清楚的取舍。
- 后续方向有记录，但不过早做重型系统。

## 当前主线

项目已经完成 Phase 1，Phase 2 模块复盘也已完成：

```text
模块复盘 ✅ -> 文档校准 ✅ -> 小步增强 -> 验证 -> 用户确认
```

当前最重要的工作不是继续横向堆功能，而是：

1. 把 MyAgent 往个人助理 runtime 的方向校准（Agent Workspace 第一版）。
2. 让 Memory recall 更值得讲（轻量增强，不加向量库）。
3. 让 Skills 更容易被模型正确使用（激活引导优化）。
4. 保持文档和真实实现一致。
## 当前实现状态

已经具备并在代码中可见的主链路能力：

- CLI Channel
- MessageBus
- AgentLoop
- ContextBuilder
- OpenAI-compatible provider 和 EchoProvider
- ToolRegistry
- Filesystem tools
- Memory tools 和 Markdown-backed memory
- Skills 扫描与按需加载
- MCP stdio / HTTP / SSE 工具接入
- SubAgent 同步委托
- JSONL trace 与本地 inspect/report/viewer
- **Feishu (Lark) Channel** — WebSocket 长连接接收 + 发送消息/文件
- **CronService** — 定时任务调度引擎（`every` / `at`）
- **MessageTool** — Agent 显式发送消息和文件到任意 channel

当前 CLI 入口：

```text
python -m myagent
```

当前 Trace 入口已经不只有限于 `trace latest/show`，还包括：

```text
python -m myagent trace latest
python -m myagent trace show --limit 20
python -m myagent trace skills
python -m myagent trace startup
python -m myagent trace context
python -m myagent trace report
python -m myagent trace viewer
```

## 近期已完成的关键 checkpoint

下面只保留对续接最重要的 checkpoint，不再记录完整流水账。

### 1. 项目定位校准完成

- `MYAGENT_ROADMAP.md`、`docs/ARCHITECTURE.md`、`docs/DECISIONS.md` 已统一为 personal assistant runtime 口径。
- 已明确源码仓库和未来的 agent workspace 应分离。
- 已新增 `docs/PERSONAL_AGENT_DIRECTION.md` 记录这一方向。

### 2. Memory v2 第一轮已落地

- Memory 已从旧的 JSONL recall 主路径转向 Markdown-backed memory。
- 当前使用的关键文件包括：`MEMORY.md`、`DREAMS.md`、`daily/YYYY-MM-DD.md`。
- `ContextBuilder` 默认会把高信号 memory 组装进 prompt。
- 已有 memory tools：
  - `memory_append_daily`
  - `memory_propose_long_term`
  - `memory_search`
  - `memory_get`
  - `memory_forget`
- 自动提取器会生成 proposal，而不是随意直接污染长期记忆。

### 3. ContextBuilder v2A 已落地

- 已引入 `ContextTier`、`ContextBudget`、`ContextAssemblyReport`。
- 已支持 `build_messages_with_report(...)`。
- 已有 deterministic history selection。
- AgentLoop 已把 `context_built` 信息写入 trace。

### 4. SubAgent 已进入可用阶段

- `delegate_task` 已接入主 Agent。
- 已有内置 profile：`researcher`、`reviewer`、`interviewer`。
- 已支持 profile-specific child tool allowlist。
- 已有 Delegation Policy，主 Agent 可以在合适时自动委托，而不必总靠用户显式指定。
- 已支持将 turn-scoped active skills 以紧凑形式传给子 Agent。

当前 SubAgent 边界：

- 允许读本地文件和使用只读型 web 工具。
- 不允许子 Agent 写文件。
- 不允许递归 `delegate_task`。
- 不允许任意 MCP 工具提升权限。

### 5. 文件工具和审批链路已落地

当前文件工具已经不再只是只读：

- `list_dir`
- `read_file`
- `write_file`
- `edit_file`
- `copy_file`
- `move_file`

其中：

- 工作区内操作默认允许。
- 触及工作区外的变更型文件操作会走 CLI 审批流程。
- 审批请求通过 MessageBus metadata 发布，CLI 负责显示和收集 Yes/No。

### 6. Skills v2 的最小可观察闭环已落地

- `skill_get(skill_id)` 会按需加载完整 `SKILL.md`。
- 成功加载 skill 会记录 `skill_loaded`。
- 同一路径还会记录 `active_skill_set`。
- `active_skill_set` 是 turn-scoped runtime observation，不会自动持久化。

### 7. Trace / inspect 能力已经形成一套本地诊断工具

当前 Trace 不只是 JSONL 文件落盘，还已有：

- turn summary
- context summary
- runtime skills trace inspect
- runtime startup trace inspect
- static HTML report
- interactive local HTML viewer

这条主线现在已经能帮助排查：

- Skills 是否被真正加载
- SubAgent 是否继承了 active skill context
- MCP server 启动是否成功
- ContextBuilder 到底把哪些 section 送进了模型

### 8. 飞书 Gateway + CronService + MessageTool 已落地

**Feishu Channel**（`myagent/channels/`）：
- `BaseChannel` 抽象 + `ChannelManager` 并行管理
- `FeishuChannel`：lark-oapi WebSocket 接收消息，httpx + lark client 发送
- 解决了 `lark-oapi WSClient` 与 asyncio 事件循环冲突（独立线程 + 替换模块级 loop）
- 消息回调正确解析 `P2ImMessageReceiveV1` 包装对象（`.event` 下取数据）
- `send()` 支持 `receive_id_type` 自动判断（`oc_` → chat_id，`ou_` → open_id）
- `send()` 支持图片/音频/视频/文件上传发送

**CronService**（`myagent/cron/`）：
- 精确 sleep 调度（`every` 周期 / `at` 定点）
- CLI 可创建管理任务但不启动 timer，Gateway 模式才运行定时器
- 集成 AgentLoop：`start_cron` 参数控制，`_on_cron_job` 发布 `InboundMessage`
- cron job payload 保存创建时的 channel/chat_id，触发时路由回正确对话
- `once` 参数支持一次性延迟提醒

**MessageTool**（`myagent/tools/message.py`）：
- Agent 显式调用 `message(content, media=[paths])` 发送文件
- 若本轮调用了 `message`，AgentLoop 抑制自动最终回复，避免重复
- 参考 NanoBot 设计，比从 content 中扫描文件路径更鲁棒

新增测试：
- `tests/test_channels_base.py`
- `tests/test_channels_feishu.py`
- `tests/test_channels_manager.py`
- `tests/test_cli_channel.py`

当前 Gateway 入口：
```text
python -m myagent gateway
```

## 最近记录的验证状态

最近一次 focused verification：

```text
python -m pytest tests/test_context_builder.py tests/test_filesystem_tools.py tests/test_agent_loop.py tests/test_agent_trace.py
56 passed
```

最近一次全量测试观察：

```text
python -m pytest
211 passed
```

## 当前最推荐的下一步

Phase 2 复盘已完成，当前进入小步增强阶段。已完成：

```text
✅ 1. Agent Workspace 第一版骨架
✅ 2. Memory recall 轻量增强（Consolidation 自动整理）
✅ 3. Skills 自动激活引导优化（description + format 改进）
```

**当前进行中：Budget-aware Context Composer**

ContextBuilder 已完成 Budget-aware Context Composer 的前两片实现。

已落地：

- `ContextItemKind` / `ContextRetentionPolicy` 内部分类。
- `ContextBudget.max_prompt_tokens` 默认 6000。
- `ContextBudget.history_token_ratio` 默认 0.35，用于给 session history 预留预算。
- system section 会按 tier / policy 预算选择。
- history 会先按消息数、再按剩余 token budget 裁剪。
- report 会记录 dropped section、预算前后 token 估算和 history token 裁剪信息。
- AgentLoop 在发生丢弃时记录 `context_dropped` trace。
- `trace context` / `trace report` / `trace viewer` 已显示新增预算字段。
- 参考上一层 NanoBot 后，已撤回 Working-turn tool result compaction 的实现方向。
- 当前 turn 内的 tool result 会完整进入下一次 provider call；大文件主要靠 `read_file`
  的 `offset` / `limit` 分页和续读提示控制。
- `read_file` 已补齐字符上限 guardrail：超长行窗口会按完整行截到字符预算内，
  并继续返回 `Use offset=... to continue`。
- `read_file` 对单行超过响应预算的 minified / long-line 文件会返回截断 marker，
  避免续读提示停留在同一行。
- `list_dir max_entries` 截断行为已有直接测试覆盖。

当前 focused verification：

```text
python -m pytest tests/test_filesystem_tools.py
28 passed

python -m pytest tests/test_agent_loop.py tests/test_agent_trace.py tests/test_context_builder.py
28 passed
```

CronTool 文案测试已同步到当前实现：

```text
python -m pytest tests/test_cron_tool.py
11 passed
```

当前全量测试基线：

```text
python -m pytest
211 passed
```

下一步应先让用户 review 本轮 ContextBuilder v2B 设计和实现，再决定：

- 是否把 `history_token_ratio=0.35` 调整为配置项。
- 是否继续补齐 NanoBot 风格的 history-save-time tool result truncation。
- 是否进入 Phase 2D：ConversationSummary。

History 的成熟路线已记录到 `docs/modules/CONTEXT_BUILDER.md`：

```text
recent buffer
-> token window
-> history_token_ratio
-> running summary + recent messages
-> old history flush into MemoryExtractor / daily / DREAMS
-> full SessionStore 与 model-visible view 分离
-> tool call / tool result 成组裁剪
```

当前 MyAgent 已完成前三层：

```text
max_history_messages
token-aware trimming
history_token_ratio = 0.35
```

后续不建议马上跳到完整 SessionStore。更合理的过渡顺序是：

```text
1. 如果未来保存 tool messages，再做 history-save-time truncation。
2. 再设计 ConversationSummary：summary + recent raw messages。
3. 再把旧 history 接入 MemoryExtractor / daily / DREAMS。
4. 最后拆出持久化 SessionStore。
```

原始问题背景：

要做的是：
- system prompt 无限增长（MEMORY.md + skills + workspace）
- history 只按消息数裁剪
- `max_prompt_tokens` 默认无限制

Trace runtime overview 暂缓。

原因：

- Context 压缩是当前框架最真实的短板（system prompt 无限增长）。
- 改动范围可控，只改 `ContextBuilder`。
- 面试时能讲清楚"为什么先做 tier-based compaction 而不是向量库"。
- 现有基础设施（tier、budget、report）已全部就绪，只差最后一步降级逻辑。
## 建议的手动检查路径

如果下一轮要继续工作，建议先这样验证当前状态：

### 1. 检查 CLI 基本链路

```text
python -m myagent
```

### 2. 检查 Trace 基本命令

```text
python -m myagent trace latest
python -m myagent trace show --limit 10
python -m myagent trace skills
python -m myagent trace startup
python -m myagent trace context
```

### 3. 检查本地报告产物

```text
python -m myagent trace report
python -m myagent trace viewer
```

### 4. 如果要测 SubAgent + Skills 桥接

可以给一个会先读 skill、再适合委托文件探索的真实任务，观察：

- 是否出现 `active_skill_set`
- 是否出现 `subagent_start`
- `subagent_start` 是否带 `inherited_active_skills`

## 明确暂缓的事项

当前明确不应急着做的内容：

- 自动 SkillSelector
- persistent active skills
- skill-defined tool permissions
- 完整 skill/profile 绑定配置
- 子 Agent 写文件
- recursive subagent delegation
- 背景并发/长生命周期 subagent orchestration
- 向量库 / SQLite / knowledge graph memory
- 重型 workflow graph runtime
- QQ Channel 的实际接入实现

这些方向不是取消，而是当前还不值得优先投入。

## 当前开放问题

后续继续工作前，值得反复校准的几个问题：

1. Agent Workspace 的目录结构和文件格式是否需要先写设计文档再实现？
2. Memory recall 增强的边界在哪里（不加向量库的前提下，还能做什么）？
3. Skills 激活引导优化只改描述格式，还是也需要改加载机制？
4. Trace runtime overview 是否值得做，还是当前诊断命令已足够？
5. QQ Channel 什么时候才值得从“方向记录”推进到“模块设计”？
## 用户偏好与工作约束

开发时继续遵守：

- 重要实现前先更新相关文档。
- 每个核心模块保持独立模块文档。
- 改完后回填实现说明和验证方式。
- 先让用户确认，再做 Git 提交。
- 提交按模块边界进行，不为每个小改动单独提交。
- 不提交真实配置、密钥、memory、trace、cache、本地测试目录。
- 项目优先服务学习、演示、面试表达，避免过度工程化。

## 续接顺序

新对话继续这个项目时，建议按下面顺序恢复上下文：

1. 读本文件。
2. 读 `docs/PHASE2_REVIEW_PLAN.md`。
3. 读本轮相关模块文档，优先：
   - `docs/modules/TRACE.md`
   - `docs/modules/SUBAGENT.md`
   - `docs/modules/SKILLS.md`
   - `docs/modules/CONTEXT_BUILDER.md`
   - `docs/modules/MEMORY.md`
4. 再看代码和测试。
