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

## Skills Phase 2A

ContextBuilder v2A 提交后，进入 Skills 第二轮。

当前目标：

```text
让 Skills 从“摘要注入”
升级为
“摘要注入 + 按需加载完整 skill”
```

已实现：

- `SkillEntry.allowed_tools`
- `SkillRegistry.get(skill_id)`
- `SkillRegistry.read_skill(skill_id)`
- `skill_get(skill_id)` tool
- `AgentLoop` 在存在 skills 时自动注册 `skill_get`
- `# Available Skills` 中提示模型需要完整说明时调用 `skill_get`
- 已从 Anthropic public skills repo 导入 5 个本地测试 skill：
  - `doc-coauthoring`
  - `frontend-design`
  - `mcp-builder`
  - `skill-creator`
  - `webapp-testing`

当前边界：

- 不自动把所有 `SKILL.md` 全文塞进 context。
- 不做自动 SkillSelector。
- 不强制 allowed-tools 权限。
- 不做 skill marketplace / 热加载。

下一步验证：

```text
python -m pytest tests/test_skills.py tests/test_skill_tools.py tests/test_agent_skills.py tests/test_context_builder.py tests/test_agent_loop.py
```

验证结果：

```text
python -m pytest
90 passed, 1 skipped
```

本地手动触发建议：

```text
请先加载 webapp-testing skill，然后告诉我怎么测试本地前端页面。
```

```text
请使用 mcp-builder skill，帮我设计一个 GitHub issue 管理 MCP server。
```

预期 CLI 出现：

```text
正在调用工具：skill_get skill_id=...
```

## Required Follow-Up: Runtime Environment Context

本地测试 Skills v2A 时发现一个重要问题：

```text
用户请求：帮我设计一个可以用于社团宣传的前端html网页
模型触发 frontend-design skill 后，调用了：
list_dir path=/Users/liuguanglin/workspace/claude-didi-9527
```

但当前项目实际运行在：

```text
Windows
PowerShell
E:\ClaudeCode\openSource\MyAgent
```

结论：ContextBuilder 需要注入基础运行环境信息，否则模型容易脑补 Linux/macOS 路径，影响工具调用。

后续必须改：

```text
新增 Runtime Environment section
  OS
  shell
  workspace root
  path style
  filesystem scope
  prefer relative paths
  do not invent absolute paths
```

建议优先级：高。

原因：这不是体验优化，而是工具调用正确性和安全边界问题。

## Runtime Environment Context Update

已实现 Runtime Environment Context，用来修复本地 Skills 测试时模型调用：

```text
list_dir path=/Users/liuguanglin/workspace/claude-didi-9527
```

这类不存在路径的问题。

实际结论：

- 代码没有把 workspace 写死成 `/Users/...`。
- CLI 文件工具的 workspace 仍来自当前运行目录。
- 问题来源更像是模型缺少 OS / shell / workspace root 约束后，自己生成了 macOS/Linux 风格绝对路径。

已改动：

- `ContextBuilder` 支持 `runtime_environment` section。
- `AgentLoop` 默认注入当前运行环境。
- CLI 会把当前目录作为 workspace root 同步传给工具 registry 和 AgentLoop。
- `list_dir` / `read_file` 的描述和错误信息强调 workspace 边界、优先使用 `.` 和相对路径。

验证：

```text
python -m pytest tests/test_context_builder.py tests/test_filesystem_tools.py tests/test_agent_loop.py tests/test_agent_trace.py
25 passed
```

## Write File Tool Update

本地测试发现：用户要求“设计前端 HTML 网页，保存下来”时，Agent 回复“无法直接写文件到磁盘”。

排查结论：

- workspace 没有被写死成错误路径。
- 但默认工具集合确实只有 `list_dir` / `read_file`，没有 `write_file`。
- 所以模型没有实际保存文件的工具，只能把代码输出给用户。

已修复：

- 新增 `write_file` 工具。
- 默认 registry 注册 `list_dir`、`read_file`、`write_file`。
- `write_file` 只允许写 workspace 内文件。
- 默认不覆盖已有文件，除非传 `overwrite=true`。
- 子 Agent 仍保持只读工具集合。

下一次 CLI 测试前需要重启：

```text
python -m myagent
```

建议测试 prompt：

```text
帮我设计一个可以用于社团宣传的前端html网页，保存为 club-promotion.html
```

预期工具调用：

```text
write_file path=club-promotion.html
```

## Session Handoff: Skills And File Tools

本轮已完成并通过本地验证：

- Skills v2A：从“摘要注入”升级为“摘要注入 + `skill_get` 按需加载完整 skill”。
- 本地 skills：已导入 `doc-coauthoring`、`frontend-design`、`mcp-builder`、`skill-creator`、`webapp-testing` 用于测试。
- Runtime Environment：ContextBuilder 已注入 OS / shell / workspace root / path style，避免模型继续编造 `/Users/...` 这类错误绝对路径。
- File tools：默认工具从只读的 `list_dir` / `read_file` 扩展为 `list_dir` / `read_file` / `write_file`。
- 本地 CLI 已验证：让 Agent 设计前端 HTML 并保存，能够成功写入文件。

当前验证结果：

```text
python -m pytest
95 passed, 1 skipped
```

本地测试产物：

```text
public/mymusic-club.html
```

这是用户本地手动测试生成的页面，不作为项目代码提交。

明天建议继续：

1. 先从 `git status` 和本文件恢复上下文。
2. 继续本地 CLI 体验测试：重点看 `skill_get`、`write_file`、Windows workspace 提示是否稳定。
3. 如果稳定，进入下一块：让 Agent 更高效地完成“创建/修改文件型任务”，包括任务规划、写前检查、写后简短确认。
4. 后续再考虑更强的 Skills pipeline：active skill 记录、skill 使用 trace、allowed-tools 权限提示是否要变成真正限制。

## MCP Phase 2 Review

已按 Phase 2 文档节奏回到 MCP 模块，并参考外部资料更新：

```text
docs/modules/MCP.md
```

参考方向：

- MCP 官方规范：tools/list、tools/call、stdio、Streamable HTTP、capabilities。
- OpenAI Agents SDK MCP：多 server、server prefix、tool filtering、tool list cache、tracing、server lifecycle。

当前判断：

- MyAgent MCP 已经跑通 stdio 和 URL 型 HTTP。
- 当前 HTTP 仍是最小实现，不等于完整生产级 Streamable HTTP host/client。
- 后续最优先不应是 OAuth / resources / prompts / sampling，而是 MCP 可观测性和工具过滤。

建议下一步 MCP Phase 2A：

1. 增加 MCP register summary，记录每个 server 的 transport、tool count、registered tool names。
2. 把 MCP server/tool 注册摘要写入 trace 或可检查的数据结构。
3. 在 MCP tool description 里补充 server 来源。
4. 设计配置层 `enabled`、`include_tools`、`exclude_tools`，先文档后实现。

暂缓：

- OAuth
- 完整长连接 SSE
- resources / prompts / sampling
- MCP server 自动安装

MCP Phase 2A 已开始实现：

- 新增 `McpRegistrationSummary`。
- 新增 `register_mcp_tools_with_summary(...)`。
- CLI 成功连接 MCP server 时展示 transport 和 registered tool names。
- `McpToolAdapter.description` 补充 MCP server 来源。

当前保留边界：

- 先不写入 turn trace，因为 MCP 连接发生在 session/turn 前。
- 如果要记录启动期 MCP 状态，后续应设计 runtime-level startup diagnostics。

MCP Phase 2B 已继续实现：

- `McpServerConfig` 支持 `enabled`。
- `McpServerConfig` 支持 `includeTools` / `include_tools`。
- `McpServerConfig` 支持 `excludeTools` / `exclude_tools`。
- MCP 注册会按原始 tool name 或注册后的 `mcp_{server}_{tool}` 名过滤。
- `McpRegistrationSummary` 增加 `discovered_tool_count` 和 `skipped_tool_names`。
- CLI 只显示 `registered/discovered` 工具数量，不展开完整工具列表。
- MCP 启动注册/连接失败会写入 `data/traces/runtime_startup.jsonl`。

后续 MCP 可继续考虑：

1. `/mcp` 或 `/tools` CLI inspect 命令。
2. HTTP MCP headers 配置。
3. 更清楚的远程 MCP 认证错误提示。

## Web Search Tool Insert

用户在使用过程中发现缺少 web search 能力。该能力对个人助理型 Agent 很重要，因此临时插入 ToolRegistry 路线。

已新增：

- 内置 `web_search` 工具。
- 内置 `web_fetch` 工具。
- 默认 registry 会注册 `web_search`。
- 参数为 `query` 和 `max_results`。
- 实现使用 `httpx` 查询公开搜索页面并解析标题、URL、摘要。
- `web_fetch` 用于打开搜索结果 URL 并提取可读正文。
- 测试使用 fake HTTP response，不依赖真实网络。

当前边界：

- 不抓取搜索结果正文。
- 不做浏览器渲染。
- 不引入 search API key。
- 如果公开搜索页面结构变化，后续可切换到正式 search API 或 MCP search server。

建议测试 prompt：

```text
帮我搜索一下最近有哪些主流 Agent 框架支持 MCP，给我总结一下。
```

预期 CLI 状态：

```text
正在调用工具：web_search query=...
```

天气测试暴露的问题：

- `web_search` 本身调用成功，trace 里能看到多次返回搜索结果。
- 但它只有搜索摘要，没有网页正文。
- 模型为了拿到更具体的天气细节反复搜索，最终触发工具调用上限。

已补充：

```text
web_fetch
```

预期天气类查询现在更合理的工具链是：

```text
web_search query=...
web_fetch url=...
```

### Web Search Relative Date Fix

本地测试发现：用户说“看明天的天气”时，模型可能没有把“明天”解析成具体日期，导致搜索命中旧年份页面。

原因不是缺少单独 time/weather 工具，而是 Runtime Environment 里没有当前日期。

已修正：

- `format_runtime_environment(...)` 注入当前日期。
- `format_runtime_environment(...)` 注入当前时间和本地时区名称。
- 明确提示模型：调用搜索前，应先把 today / tomorrow / yesterday 这类相对日期解析成绝对日期。

后续测试建议：

```text
帮我看一下明天北京天气怎么样
```

预期模型搜索 query 应包含具体日期，例如：

```text
北京 2026-05-10 天气
```

## SubAgent Phase 2 Review

已按 Phase 2 正轨进入 SubAgent 模块复盘，并更新：

```text
docs/modules/SUBAGENT.md
```

当前结论：

- SubAgent 已完成轻量 `agents-as-tools` 模式。
- 主 Agent 通过 `delegate_task` 委托小任务。
- 子 Agent 使用独立 profile 和独立上下文。
- 子 Agent 默认只继承 `list_dir` / `read_file`。
- 当前不开放 `write_file`、`web_search`、MCP tools 或递归 `delegate_task`。

下一步建议 SubAgent Phase 2A：

1. 先补可观测性，不扩大权限。
2. 给 SubAgentRunner 增加可选 trace hook。
3. 记录 `subagent_tool_call` / `subagent_tool_result`。
4. 在 trace 中加入 `subagent_task_id` 和 `parent_turn_id`。
5. CLI 仍保持简洁，不默认展示所有子 Agent 内部工具调用。

暂缓：

- handoff
- swarm
- 并发子任务
- 子 Agent 写文件
- 子 Agent 任意调用 MCP tools
- profile 配置化和 skill 绑定
## SubAgent Phase 2A Implementation

SubAgent Phase 2A has now moved from review to implementation.

Completed:

- `SubAgentRunner` supports an optional trace hook.
- `DelegateTaskTool` has `execute_with_trace(...)` for AgentLoop integration.
- `AgentLoop` creates a stable `subagent_task_id` for each `delegate_task` call.
- Trace now records `subagent_tool_call` and `subagent_tool_result` for child
  Agent internal tool use.
- Child trace events include `parent_turn_id`, `parent_tool_call_id`, and
  `subagent_task_id`.
- CLI remains quiet: users still only see the top-level `delegate_task` status.

Current SubAgent boundary remains unchanged:

- Child Agent can use read-only tools: `list_dir`, `read_file`, `web_search`,
  and `web_fetch`.
- Child Agent cannot use `write_file`, MCP tools, or recursive `delegate_task`.

Focused verification:

```text
python -m pytest tests/test_subagent.py tests/test_agent_loop.py tests/test_agent_trace.py
15 passed
```

Next recommended step after this is full verification:

```text
python -m pytest
```

If full verification passes and the user accepts the behavior, commit the current
MCP + web + runtime context + SubAgent observability batch as a focused Phase 2
checkpoint, or split it into smaller commits if the diff feels too broad.
## SubAgent Delegation Strategy Refresh

User feedback corrected an important design point: everyday prompts should not
require the user to say "delegate to researcher." That wording is useful for
manual testing, but a personal Agent framework should decide delegation itself.

External references checked:

- Claude Code subagents: automatic delegation by subagent description and
  context, with explicit invocation only when the user wants to force a subagent.
- OpenAI Agents SDK: LLM-driven orchestration and agents-as-tools, where a
  manager agent can autonomously call specialist agents.
- LangGraph supervisor: a central supervisor routes work to specialist agents.
- CrewAI: agents have roles, tools, and explicit collaboration/delegation
  controls.

Current conclusion:

- Keep MyAgent's `delegate_task` primitive. It matches the agents-as-tools
  pattern.
- Change the expected UX: the main Agent should call `delegate_task`
  automatically when a task needs isolated research, review, or file exploration.
- Keep explicit "use researcher" prompts only as a test/debug path.
- Stay synchronous for now; async/background subagents are deferred until
  cancellation/status/trace inspection are stronger.
- Allow read-only local + web tools for researcher-style SubAgents.
- Keep child write tools, recursive delegation, arbitrary MCP tools, and handoff
  deferred.

Recommended next implementation:

1. Add a protected `Delegation Policy` section to the main Agent context.
2. Tell the model when to proactively use `delegate_task`.
3. Add trace metadata for the delegation reason and whether the user explicitly
   requested the subagent.
4. Add tests that verify the policy text appears in context and that existing
   explicit delegation still works.
## SubAgent Capability Level Plan

SubAgent design has been widened so it does not get trapped as only a single
`researcher` tool.

The current design model is:

```text
Level 1: agents-as-tools
Level 2: profile-based subagents
Level 3: automatic delegation policy
Level 4: background or parallel subagents
Level 5: supervisor workflow
Level 6: handoff
```

Current Phase 2 target:

- Complete Level 1: keep `delegate_task` as the working primitive.
- Partially implement Level 2: profiles exist, next should add profile-specific
  tool allowlists.
- Minimally implement Level 3: add a protected Delegation Policy so the main
  Agent can call `delegate_task` automatically.
- Defer Level 4/5/6 until trace inspection, cancellation, status, and workflow
  needs are clearer.

The next concrete implementation should be:

1. Add `allowed_tools` to `SubAgentProfile`. Done.
2. Give `researcher` local read + web read tools. Done.
3. Give `reviewer` local read tools first; safe checks can be added later. Done.
4. Give `interviewer` web read tools for interview-topic lookup. Done.
5. Add a main-context `Delegation Policy` section after profile permissions are
   clear. Done.

Implemented Phase 2B:

- `SubAgentProfile.allowed_tools`
- profile-specific child tool registries
- protected `Delegation Policy` context section
- optional `delegate_task.reason`
- trace metadata: `delegation_reason` and `delegation_mode`

Focused verification:

```text
python -m pytest tests/test_subagent.py tests/test_context_builder.py tests/test_agent_trace.py tests/test_agent_loop.py
24 passed
```

Next recommended validation:

```text
python -m pytest
```

Manual CLI test after full verification:

```text
帮我查一下主流 Agent 框架是怎么做 SubAgent 自动委托的，并结合当前项目给出下一步建议
```

Expected behavior:

- The user does not need to say "委托 researcher".
- The main Agent may proactively call `delegate_task`.
- Trace should show `subagent_start` with `delegation_mode=automatic` when the
  user did not explicitly request a subagent.
## AgentLoop Phase 2 Review

After the SubAgent checkpoint, the next module is AgentLoop because it is now the
runtime coordinator for context, tools, memory, skills, MCP, web search, trace,
and SubAgent delegation.

External framework lessons recorded in:

```text
docs/modules/AGENT_LOOP.md
```

References used:

- OpenAI Agents SDK Runner: explicit run loop, max turns, handoffs, tools,
  guardrails, hooks.
- AutoGen AgentChat: explicit termination conditions such as max messages,
  timeout, handoff, external stop, and function-call termination.
- CrewAI: separates task, process, output, and guardrail concepts.
- LangGraph: suggests future state-graph direction, but that is too heavy for
  current Phase 2.

Current conclusion:

- Do not rewrite AgentLoop as a full graph runtime now.
- Do not add complex guardrails yet.
- First add a small explicit run-state layer.

Recommended next implementation:

1. Add `AgentTurnState` or `AgentRunState`. Done.
2. Track. Done:
   - iteration
   - tool call count
   - tool error count
   - repeated tool call warnings
   - stop reason
3. Add structured stop reasons. Partially done:
   - `final_output`
   - `max_tool_iterations`
   - `provider_error`
   - `tool_loop_error` deferred
   - `cancelled` deferred
4. Add a `turn_completed` trace event. Done.
5. Improve the max-tool-iteration fallback message. Done.
6. Add focused tests before broader refactors. Done.

Implemented AgentLoop Phase 2A:

- `AgentTurnState`
- `turn_completed` trace event
- `stop_reason`
- tool call/error counts
- repeated tool call warning
- clearer max-tool-limit fallback
- normalized AgentLoop tool status text to `Calling tool: ...`

Verification:

```text
python -m pytest tests/test_agent_loop.py tests/test_agent_trace.py
12 passed

python -m pytest
110 passed, 1 skipped
```

Recommended next step:

1. Commit AgentLoop Phase 2A as a focused checkpoint after user confirmation.
2. After that, decide whether the next module should be Trace inspect commands
   or Tool loop diagnostics.

## Trace Phase 2A

After AgentLoop Phase 2A, Trace became the next documented priority because the
trace now contains richer events such as `turn_completed`, `stop_reason`,
SubAgent child tool calls, and MCP startup diagnostics.

Design recorded in:

```text
docs/modules/TRACE.md
```

Implemented:

- `myagent/tracing/inspect.py`
- `python -m myagent trace latest`
- `python -m myagent trace show`
- compact turn summaries
- compact recent-event rendering
- `--session`
- `--trace-dir`
- `--limit`

Examples:

```text
python -m myagent trace latest
python -m myagent trace show --limit 20
python -m myagent trace latest --session cli:default --trace-dir data/traces
```

Current boundary:

- local JSONL only
- read-only
- no replay
- no Web UI
- no full-message dump
- no automatic redaction
- no SQLite/OpenTelemetry

Focused verification:

```text
python -m pytest tests/test_trace_store.py tests/test_cli_channel.py
21 passed
```

Next recommended validation:

```text
python -m pytest
```

Manual test:

```text
python -m myagent trace latest
python -m myagent trace show --limit 10
```

## Current Work: File Task Phase 2A

The current active work is a small ToolRegistry improvement for practical file
tasks.

Goal:

- Let MyAgent make small targeted edits to existing workspace files.
- Avoid building a large editor subsystem too early.

Implemented direction:

- Add `edit_file(path, old_text, new_text, replace_all=false)`.
- Register it in `create_default_registry(...)`.
- Keep the tool workspace-scoped and UTF-8 text only.
- Reject ambiguous replacements by default.

How to test locally:

```text
python -m myagent
You: create note.txt with "hello old world"
You: read note.txt and replace "old" with "new"
```

Expected behavior:

- The first task should use `write_file`.
- The second task should use `read_file` and `edit_file`.
- The model should not need to rewrite the whole file for a small edit.

Recommended next step after this is tested:

- Commit this File Task Phase 2A change.
- Then return to the Phase 2 review plan and choose the next practical
  user-visible capability, without adding broad policy machinery yet.

## Current Work: File Access Approval Phase 2B

The next active work is a channel-owned approval path for practical
personal-assistant file tasks.

Goal:

- Let MyAgent copy or move a workspace file to places such as Desktop.
- Require Yes/No approval when a file tool touches paths outside the workspace.
- Keep the CLI spinner/display behavior for normal tool status.
- Do not let tools call terminal input directly.

Implemented direction:

- Add `copy_file(source_path, destination_path, overwrite=false)`.
- Add `move_file(source_path, destination_path, overwrite=false)`.
- Keep `list_dir` and `read_file` as read-only operations that do not require
  approval.
- Apply one shared outside-workspace approval policy to mutating file tools:
  `write_file`, `edit_file`, `copy_file`, and `move_file`.
- Resolve common personal folder aliases: Desktop, Downloads, Documents, 桌面.
- Publish approval requests through the CLI channel via MessageBus metadata.
- CLI displays the permission request, collects Yes/No, and resumes the turn.
- Do not create guessed external parent directories silently.

Deferred:

- QQ/Telegram buttons.
- Text-code approvals such as `approve 8F3A`.
- `allowedDirectories` config.
- Persistent rules such as "always allow Desktop".
- delete tools.

## Skills Phase 2B: Active Skill Trace

Skills Phase 2B is now complete and committed.

Recent commits:

```text
a4fe099 feat: trace skill loading
5d1c5c1 feat: trace active skills
```

What changed:

- `skill_get(skill_id)` still loads the full `SKILL.md` on demand.
- A successful `skill_get` now records `skill_loaded`.
- The same success path also records `active_skill_set`.
- `active_skill_set` is turn-scoped only.
- It does not inject a new prompt section.
- It does not persist into session memory.
- It does not change tool permissions.

The trace event shape is:

```text
event: active_skill_set
data:
  skill_id
  name
  scope: turn
  reason: loaded_by_skill_get
```

Why this matters:

- The runtime can now answer which skill was actually used in a turn.
- Future task-level active skills can build on this without changing the first
  implementation.
- This keeps Skills v2 explainable: summary in prompt, full instructions loaded
  by tool, active usage visible in trace.

Verification:

```text
python -m pytest tests/test_skill_tools.py tests/test_agent_skills.py tests/test_skills.py tests/test_context_builder.py
17 passed

python -m pytest
133 passed, 1 skipped
```

Current Skills boundary:

- Do not implement automatic SkillSelector yet.
- Do not persist active skills yet.
- Do not bind Skills to SubAgent profiles yet.
- Do not enforce `allowed-tools` at runtime yet.

Those need clearer task/run state and conflict handling before they are worth
building.

## Recommended Next Step

The next mainline step should be a short project-status cleanup, then one of two
practical module choices:

1. Continue with Trace / runtime observability:
   make it easier to inspect `runtime_skills.jsonl`, startup trace, and turn
   trace together from one command.

2. Continue with SubAgent + Skills alignment:
   document how a future SubAgent could inherit a turn-level active skill, but
   keep implementation deferred until task/run boundaries are clearer.

Recommended choice for the next coding step:

```text
Trace inspect improvement
```

Reason:

- It is user-visible immediately.
- It helps debug Skills, MCP, web search, file approval, memory, and SubAgent
  behavior.
- It does not force premature automatic SkillSelector or complex policy design.

## Trace Inspect Runtime Convenience Update

Trace inspect has started this recommended follow-up.

Implemented direction:

- Add readable previews for runtime events:
  - `skill_loaded`
  - `active_skill_set`
  - `mcp_server_registered`
  - `mcp_server_connect_failed`
- Add convenience commands:
  - `python -m myagent trace skills`
  - `python -m myagent trace startup`

Why:

- Users no longer need to remember `--session runtime:skills`.
- Users no longer need to remember `--session runtime:startup`.
- Active Skill and MCP startup behavior become easier to inspect after local
  testing.

Next validation:

```text
python -m pytest tests/test_trace_store.py tests/test_cli_channel.py
python -m pytest
```

## SubAgent + Skills Alignment Design

The next design checkpoint has been recorded in:

```text
docs/modules/SUBAGENT.md
docs/modules/SKILLS.md
```

Decision:

- Keep SubAgent profile as the authority for execution boundaries.
- Treat Skill as workflow guidance.
- Treat Active Skill as a runtime observation that can later be passed to a
  child Agent as compact context.
- Do not let Skill silently grant child Agent tools.
- Do not automatically inject full `SKILL.md` into SubAgents.

Implemented minimal bridge:

```text
Parent turn records active_skill_set
Parent calls delegate_task
DelegateTaskTool passes compact active_skill_context to SubAgentRunner
SubAgent prompt includes # Parent Active Skills
subagent_start trace records inherited_active_skills
```

Runtime boundary:

- The bridge is turn-local only.
- It does not persist active skills.
- It does not pass full `SKILL.md`.
- It does not grant child Agents new tools.

Deferred:

- automatic SkillSelector
- full skill inheritance
- skill-defined tool permissions
- profile/skill binding config
- persistent active skills

Recommended next step after validation:

```text
Run focused SubAgent/Skill tests, then let the user test a real CLI task that
uses a skill before delegation.
```

## Context Trace Inspect Update

After committing the SubAgent + Active Skill bridge, the next runtime polish step
is Context trace inspection.

Why this is different from existing trace:

- Existing `context_built` trace already stores ContextBuilder data.
- Existing `trace latest` summarizes the latest turn outcome.
- New `trace context` should summarize what went into the model context:
  sections, token estimates, history trimming, and warnings.

Implemented command:

```text
python -m myagent trace context
```

Expected output shape:

```text
turn_id: ...
message_count: ...
estimated_tokens: ...
total_chars: ...
history: included/total, dropped
sections:
- Identity: tier=protected, source=identity, tokens=..., chars=..., included=yes
- Runtime Environment: ...
- Core Memory: ...
- Available Skills: ...
- Delegation Policy: ...
```

This does not change prompt composition. It only makes the existing
ContextBuilder report easier to inspect from CLI.

## Trace HTML Report

Because command-line summaries are still hard to scan for larger runs, Trace now
has HTML inspection pages.

Implemented command:

```text
python -m myagent trace report
```

Default output:

```text
data/traces/report.html
```

The report shows:

- latest turn summary
- ContextBuilder section sizes
- history inclusion/drop information
- recent Skills runtime events
- MCP startup events
- recent session events

Boundary:

- Static HTML only.
- No server.
- No frontend framework.
- No raw full message dump.
- No trace mutation.

This is meant for local diagnosis: easier than reading JSONL, but still simple
enough for the current Phase 2 project.

## Trace Interactive Viewer

The fixed HTML report is useful, but the more flexible direction is an
interactive local viewer.

Implemented command:

```text
python -m myagent trace viewer
```

Default output:

```text
data/traces/viewer.html
```

Behavior:

- Open the HTML file in a browser.
- Select one or more saved `.jsonl` trace files.
- The page parses the files locally with browser JavaScript.
- The page shows tabs for:
  - Context
  - Events
  - Skills
  - Startup
  - Raw parsed JSON

Recommended files:

```text
data/traces/cli_default.jsonl
data/traces/runtime_skills.jsonl
data/traces/runtime_startup.jsonl
```

Boundary:

- No upload.
- No server.
- No database.
- No frontend build pipeline.
- No mutation of trace files.
