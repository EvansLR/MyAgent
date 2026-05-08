# MyAgent 当前状态与下一步

这份文档用于跨对话续接。新对话开始时，先读这里，再看代码和模块文档。

## 当前项目目标

MyAgent 是一个面向学习、面试讲解和本地演示的轻量 ReAct Agent runtime。

当前阶段目标不是生产级 Agent 平台，而是保证：

- 系统能跑起来。
- 核心架构能讲清楚。
- 每个模块有文档、有测试、有明确边界。
- 后续扩展方向有记录，但不提前过度实现。

## 当前已完成模块

已经实现并提交过的主要能力：

- MessageBus：输入/输出消息队列。
- CLI Channel：本地命令行对话入口。
- AgentLoop：ReAct 主循环和工具调用。
- LLM Provider：OpenAI-compatible provider 和 EchoProvider。
- ContextBuilder：Identity、Memory、Skills 等上下文组装。
- ToolRegistry：工具注册、schema、参数校验和执行。
- Read-only filesystem tools：`list_dir`、`read_file`。
- Trace：JSONL 运行轨迹。
- Memory：文件型 memory 和显式记忆保存/召回。
- Skills：本地 `skills/*/SKILL.md` 扫描和上下文注入。
- MCP：stdio 和 HTTP/SSE 风格 MCP 工具接入。

## 最近完成的工作

最近一组完成的文档校准主题是 Project Docs / Roadmap。

校准内容：

- `MYAGENT_ROADMAP.md`：从“设计草案”调整为当前 roadmap，明确 Phase 1 已完成、Phase 2 是当前阶段，并把未实现的写文件、编辑、exec、web_search、高级 trace、独立 SubAgent 模型配置等放入 Phase 2 或后续扩展。
- `docs/PHASE1_PLAN.md`：标记为 Phase 1 历史计划和验收记录，不再作为当前待办清单。
- `docs/PROJECT_PLAYBOOK.md`：补充当前使用方式，说明新对话应先读 `NEXT_STEPS` 和 `PHASE2_REVIEW_PLAN`。

本轮只校准文档，没有修改运行代码。

随后进入 Config 复盘，并完成第一轮文档化：

- 新增 `docs/modules/CONFIG.md`：集中说明 `Settings`、`myagent.json`、环境变量覆盖、`mcpServers`、SubAgent 配置暂缓项和 Phase 2 Review。
- 更新 `myagent.example.json`：增加空的 `mcpServers` 字段，提示 MCP 配置入口。
- 更新 `docs/ARCHITECTURE.md`：把配置设计从早期环境变量口径校准为当前 JSON + 环境变量模式。
- 修复 provider 类型导入环：`providers.base`、`providers.echo`、`providers.openai_compatible` 不再为了类型标注导入 `myagent.agent.context.Message`。

本轮发现：本地 `myagent.json` 包含真实 provider/MCP key，但该文件未被 Git 跟踪，并且已在 `.gitignore` 中忽略。后续不能提交该文件。

本轮验证：

```text
python -m json.tool myagent.example.json
python -m pytest tests/test_llm_provider.py tests/test_mcp_config.py
python -m pytest
```

结果：

```text
15 passed
80 passed, 1 skipped
```

随后进入 CLI Channel 体验复盘，并完成第一轮小升级：

- 更新 `docs/modules/CLI_CHANNEL.md`：补充 Phase 2 Review，校准 Rich spinner、Markdown、MCP 启动提示和未知命令行为。
- 更新 `myagent/cli/commands.py`：未知 slash command 不再进入模型，改为提示 `/help`；MCP server 连接成功时显示注册工具数量。
- 更新 `tests/test_cli_channel.py`：覆盖未知 slash command 的新行为。

本轮验证：

```text
python -m pytest tests/test_cli_channel.py
python -m pytest
```

结果：

```text
14 passed
81 passed, 1 skipped
```

随后根据用户要求，先不直接设计 Memory，而是调研 Codex、Claude、OpenClaw 等系统的 memory 做法：

- 新增 `docs/modules/MEMORY_PHASE2_RESEARCH.md`。
- 调研对象包括 OpenAI ChatGPT Memory、OpenAI Agents SDK cookbook、Codex AGENTS.md、Claude Code memory、OpenClaw、Letta/MemGPT、LangGraph/Deep Agents、Zep。
- 初步结论：MyAgent 第二版不应直接上向量库，而应先做轻量分层 memory：scope、kind、importance、tags、可解释 recall、用户可管理、后续 consolidation 扩展点。

用户进一步明确：MyAgent 是用户个人助理型 Agent，类似 OpenClaw，不只是通用 coding agent。因此 Memory 设计应优先服务个人长期状态：

- `profile`：用户偏好、目标、协作方式。
- `project`：当前项目状态、阶段决策、路线。
- `working`：最近阶段的候选信息、观察和临时计划。

Codex / Claude Code 等 coding agent 经验可以参考，但不能主导设计。

随后继续查阅 OpenClaw 相关机制，发现 MyAgent 需要从“当前源码项目里的 coding agent”转向“local-first 个人助理 runtime”：

- 新增 `docs/PERSONAL_AGENT_DIRECTION.md`。
- 重点参考 OpenClaw 的 agent workspace、SOUL/USER/IDENTITY/TOOLS/MEMORY 文件分层、daily notes、skills、tools/plugins、channels/routing、heartbeat 和安全默认值。
- 新方向：MyAgent 源码仓库和运行时个人助理 workspace 应分开；后续应设计 `~/.myagent/workspace` 这一类 agent home。
- 近期优先级应偏 Memory v2、ContextBuilder v2、Skills v2、状态可见性和 QQ Channel 设计，而不是继续堆 coding 工具。

随后完成个人助理定位校准：

- 更新 `docs/ARCHITECTURE.md`：明确 MyAgent 是 local-first 个人助理 Agent runtime，不是只服务代码仓库的 Coding Agent；新增 Agent Workspace 方向。
- 更新 `MYAGENT_ROADMAP.md`：把长期方向改为“长期理解用户 -> 维护个人工作状态 -> 使用工具完成任务 -> 支持多通道协作”。
- 更新 `docs/DECISIONS.md`：记录项目定位、Memory 三层方向、Skills 工作流方向和 QQ Channel 后续方向。

随后根据用户追问，进一步校准 Memory 触发机制：

- Memory v2 不应只有一个后处理 `MemoryObserver`。
- 应采用三条路径：live memory tools、post-turn MemoryExtractor、dreaming/review consolidation。
- 参考 OpenClaw / Claude：主 Agent 应能通过 memory tools 在当前 turn 主动写 memory 或 proposal。
- 参考 OpenAI Agents SDK：post-turn/session-close extractor 用于补漏和生成候选。
- 长期 `MEMORY.md` 不允许模型随意直接改，先生成 proposal；显式记忆可自动 apply，自动候选先进 daily notes。

随后校准 Core Memory / Searchable Memory：

- `Core Memory` 是 `MEMORY.md` 中默认组装进 system prompt 的高信号 section。
- `Searchable Memory` 是不默认进入 prompt、通过 `memory_search` / `memory_get` 按需检索的内容。
- 这个分层参考 Letta / MemGPT 的 Core Memory / Archival Memory，也对应 OpenClaw / Claude Code 默认加载高信号 memory 文件、按需搜索更多记忆的做法。

随后已把调研结论收敛进 `docs/modules/MEMORY.md`：

- 增加 Memory Phase 2 Review。
- 明确第二版目标：从“显式关键词记忆”升级为“轻量、分层、可管理、可解释的本地记忆系统”。
- 确定最小实现范围：扩展 `MemoryEntry`，新增 `MemoryRecallResult` / `recall_with_scores`，增加 `forget(id)`，增强 trace 中的 recall 解释。
- 明确暂不做向量库、SQLite、knowledge graph、后台 dreaming 和自动全量 chat history 建模。

最近一组完成的变更主题是 SubAgent 和开发规范沉淀。

新增/修改内容：

- `AGENTS.md`：当前项目的 AI 协作规范。
- `docs/CODE_STANDARDS.md`：MyAgent 代码与协作规范。
- `docs/modules/SUBAGENT.md`：SubAgent 调研、设计和实现说明。
- `docs/NEXT_STEPS.md`：当前跨对话续接文档。
- `myagent/agent/subagent.py`：SubAgent 核心实现。
- `myagent/agent/loop.py`：注册 `delegate_task`，并记录 SubAgent trace。
- `myagent/agent/__init__.py`：导出 SubAgent 相关类型。
- `tests/test_subagent.py`：SubAgent 自动化测试。

## SubAgent 当前能力

第一版 SubAgent 采用 manager / agents-as-tools 思路。

主 Agent 默认可以看到：

```text
delegate_task
```

当模型调用 `delegate_task` 时，系统会创建一个临时子 Agent 执行任务。

子 Agent 目前只能使用：

```text
list_dir
read_file
```

它不会看到 `delegate_task`，因此不会递归委托。

当前内置 profile：

- `researcher`
- `reviewer`
- `interviewer`

## 当前验证状态

最近一次全量测试结果：

```text
python -m pytest
81 passed, 1 skipped
```

跳过的测试是 `tests/test_mcp_stdio.py`，原因是当前 Windows 开发沙箱可能禁止 asyncio subprocess pipe。这个是已知旧情况，不是 SubAgent 引入的新问题。

## 手动测试建议

启动 CLI：

```text
python -m myagent
```

推荐测试：

```text
请委托一个 researcher 子 Agent 浏览 docs/modules 目录，并总结当前项目有哪些模块。
```

如果模型触发成功，终端应显示类似：

```text
正在调用工具：delegate_task ...
```

注意：是否调用工具由模型自己决定。为了提高触发概率，测试时明确说“请委托一个 researcher 子 Agent”。

## 用户偏好和约束

开发时必须遵守：

- 任何重要代码实现前，先整理文档。
- 每个核心模块要有独立模块文档。
- 每次实现后，要回到模块文档补充实现说明。
- 做完一部分后，先让用户测试确认，再提交 Git。
- 提交以模块为单位，不为每个小改动提交。
- 提交后同步推送到远程 GitHub。
- 不提交真实配置、密钥、memory、trace、cache、本地测试目录。
- 项目服务学习和面试场景，优先保证能跑、能讲清楚，不做过度工程化。

## 下一步建议

当前最直接的下一步是：

1. 按 `docs/PHASE2_REVIEW_PLAN.md` 继续第二版模块复盘。
2. Project Docs / Roadmap 已完成第一轮校准。
3. Config 已完成第一轮文档复盘。
4. CLI Channel 已完成第一轮体验复盘和小升级。
5. Memory 外部调研已完成第一版文档。
6. Memory Phase 2 Review 已收敛进 `docs/modules/MEMORY.md`。
7. 个人助理方向已新增 `docs/PERSONAL_AGENT_DIRECTION.md`，用于纠正“只像 Coding Agent”的偏移。
8. Architecture / Roadmap / Decisions 已完成个人助理定位校准。
9. 下一步建议先和用户讨论 Memory v2 设计，确认 profile/project/working 三层的边界，再写代码。
10. 如果用户继续测试 SubAgent 并发现问题，先回到 `docs/modules/SUBAGENT.md` 校准设计，再修代码。

可选后续方向：

- 改进 Skills：让 skill 从“提示词摘要”升级为更明确的可激活能力。
- 改进 Memory：从简单关键词召回升级为更可展示的记忆机制。
- 改进 SubAgent：profile 配置化、子 Agent trace tree、CLI 展示子 Agent 内部工具调用。
- 改进 ContextBuilder：增加 budget-aware context composer。
- 后续 IM Channel：暂时不做微信；如果以后扩展，优先考虑 QQ，并建议通过 OneBot 兼容协议接入，让 MyAgent 只负责 Channel 适配，不直接处理 QQ 登录和协议细节。

## 开放问题

- SubAgent profile 是否需要放进 `myagent.json` 配置？
- 子 Agent 内部工具调用是否要在 CLI spinner 中显示？
- Skills 是否要和 SubAgent profile 绑定？
- Memory 下一版是否需要从关键词召回升级为更可靠的检索策略？
- QQ Channel 是否在 Agent 主体跑顺之后作为独立模块设计？第一版是否只支持私聊，群聊是否需要命令前缀？

## Latest Session Update

Memory v2 Phase 2A 已经开始实现，并完成最小闭环：

- 新增 Markdown-backed memory store：`MEMORY.md`、`DREAMS.md`、`daily/YYYY-MM-DD.md`。
- `Core Memory` / `User Profile` / `Active Goals` 会由 `ContextBuilder` 默认组装进 system prompt。
- 主 Agent 现在注册四个 memory tools：`memory_append_daily`、`memory_propose_long_term`、`memory_search`、`memory_get`。
- `AgentLoop` 在 final answer 发布后运行 `MemoryExtractor`，默认每轮尝试从 user message + assistant answer 中抽取候选记忆。
- 自动抽取不会直接写长期 `MEMORY.md`，而是写 daily note 或 DREAMS proposal。
- 旧 JSONL memory 代码暂时保留，作为旧模块兼容和对照。

随后本地 CLI 测试暴露了记忆一致性问题：模型声称“已忘掉 Java 面试 / 已记住名字”，但实际底层只写了 `DREAMS.md` proposal，旧 `facts.jsonl` 仍被默认召回。

已修复：

- `AgentLoop` 和 `ContextBuilder` 已移除旧 JSONL recall 主路径，避免旧测试记忆污染上下文。
- `memory_propose_long_term` 默认会把用户明确要求记住的长期资料写入 `MEMORY.md`。
- 自动 `MemoryExtractor` 仍然只写 proposal，不直接污染长期记忆。
- 新增 `memory_forget(query)`，支持按 id 或主题从 Markdown memory 文件删除记忆。
- 本地 ignored memory 数据已清理：Java 面试测试记忆已移除，`用户的名字是 lin` 已进入 `MEMORY.md` 的 `User Profile`。

当前 focused tests 已通过：

```text
python -m pytest tests/test_memory_store.py tests/test_memory_tools.py tests/test_context_builder.py tests/test_agent_memory.py tests/test_agent_trace.py tests/test_agent_loop.py
24 passed
```

最新全量测试：

```text
python -m pytest
90 passed, 1 skipped
```

下一步建议：

1. 先跑全量 `python -m pytest`。
2. 如果全量通过，人工检查 `data/memory/` 是否仍未被 Git 跟踪。
3. 让用户确认这版 Memory v2 行为。
4. 用户确认后提交。
5. 后续再考虑 `/memory` CLI、review/consolidation 命令，以及长期 `MEMORY.md` 的人工晋升流程。

## ContextBuilder Phase 2 Research

Memory v2 已完成提交后，下一步进入 ContextBuilder 第二轮。

用户明确要求：在做 ContextBuilder 拔高前，先查阅成熟开源框架的做法，取长补短，再设计自己的文档。

已新增：

```text
docs/modules/CONTEXT_BUILDER_PHASE2_RESEARCH.md
```

已更新：

```text
docs/modules/CONTEXT_BUILDER.md
```

调研结论：

- OpenClaw 的 `/context list/detail` 说明 context 必须可观测，应该能看到 section、file、skill、tool schema 的大小贡献。
- OpenAI Agents SDK 的 sessions 说明 history 存储和本轮输入选择要分开，并支持 trimming / compression。
- Claude Code 的 context window 说明旧 tool outputs 应优先清理，稳定规则应放在 memory/project files，而不是依赖早期聊天记录。
- LangGraph 说明 short-term memory 和 long-term memory 应分离，长 history 会引入 stale info、成本和性能问题。

ContextBuilder Phase 2 推荐实现顺序：

1. 新增 `ContextBudget`。
2. 扩展 `ContextSection`，加入 `tier` 和 `source`。
3. 新增 `ContextAssemblyReport`。
4. 新增 `build_messages_with_report(...)`。
5. 实现 deterministic history selection，先保留最近 N 条。
6. AgentLoop 把 context report 写入 trace。
7. 跑 focused context tests 和全量 tests。

当前实现进展：

- 已新增 `ContextTier`、`ContextBudget`、`ContextAssemblyReport`。
- 已新增 `build_messages_with_report(...)`。
- 已实现默认最近 20 条 history 的 deterministic selection。
- `AgentLoop` 已把 context report 写入 `context_built` trace。
- 旧 `MemoryRecall` 主路径和文件已删除：`myagent/memory/recall.py`、`tests/test_memory_recall.py`。
- Focused tests 已通过：

```text
python -m pytest tests/test_context_builder.py tests/test_agent_trace.py
9 passed
```

全量验证：

```text
python -m pytest
88 passed, 1 skipped
```

明确记录一个重要暂缓项：

```text
Context compaction 暂不在 ContextBuilder v2A 直接实现。
```

这不是取消。它需要等后面的 pipeline 出现真实触发点后再做：

- Skills v2：区分 skill summary / active skill / full skill content 后，会知道 skills 对 context 的真实压力。
- Tools pipeline：tool result、tool schema、tool output pruning 需要一起设计。
- SubAgent pipeline：子 Agent summary、trace tree、主上下文回灌方式需要先明确。
- Session history：当 history selection 开始丢失重要信息，再做 summary compaction 才有实际问题可解。
- Memory pipeline：pre-compaction memory flush 要和 daily / DREAMS / MemoryExtractor 对齐。

后续必须回来的 ContextBuilder 高级项：

```text
context compaction
pre-compaction memory flush
tool output pruning
/context inspect
summary persistence
```

建议触发条件：

```text
ContextAssemblyReport 显示上下文经常接近预算上限，
或 Skills / Tools / SubAgent 产生明显 prompt 膨胀时，
再进入 ContextBuilder compaction 设计。
```
