# MyAgent 当前状态与下一步

这份文档用于跨对话续接。新对话开始时先读这里，再按需读相关模块文档和代码。

## 当前项目定位

MyAgent 当前定位是：

```text
一个 local-first、轻量、可教学、可面试讲解的个人助理 Agent runtime。
```

当前阶段不追求生产级平台复杂度，优先保证：

- 主链路稳定可运行。
- 核心模块边界清楚。
- 文档和实现一致。
- 关键取舍能讲清楚。
- 后续方向有记录，但不过早做重型系统。

## 当前主链路能力

已经具备并在代码中可见的能力：

- CLI Channel / MessageBus / AgentLoop
- ContextBuilder：预算控制、history 裁剪、conversation summary、trace report
- OpenAI-compatible provider 和 EchoProvider
- ToolRegistry 与默认工具
- Filesystem tools：`list_dir`、`read_file`、`write_file`、`edit_file`、`copy_file`、`move_file`
- Shell tool：`execute_command`
- Memory tools 和 Markdown-backed memory
- Skills 扫描、按需加载和 turn-scoped active skill trace
- MCP stdio / HTTP / SSE 工具接入
- SubAgent 同步委托
- JSONL trace、inspect/report/viewer
- Feishu Gateway
- CronService
- MessageTool

常用入口：

```text
python -m myagent
python -m myagent gateway

python -m myagent trace latest
python -m myagent trace show --limit 20
python -m myagent trace context
python -m myagent trace report
python -m myagent trace viewer
```

## 最近完成

### Context

ContextBuilder 已完成当前阶段的主要上下文控制：

- `ContextBudget.max_prompt_tokens` 默认 6000。
- `history_token_ratio` 默认 0.35。
- system sections 按 tier / retention policy 进入预算。
- history 先按消息数、再按 token budget 裁剪。
- `ConversationSummary` 已落地：`running summary + recent raw messages`。
- summary 只作为 model-visible context view，不写入 Memory，不修改原始 `_history`。
- 当前 turn 内 tool result 不做 working-turn compaction；大文件依靠 `read_file offset/limit` 分页。

设计记录：

- `docs/modules/CONTEXT_BUILDER.md`

### Memory

Memory 已从旧 JSONL recall 主路径转向 Markdown-backed workspace：

```text
MEMORY.md
  稳定长期记忆，默认可进入上下文。

MEMORY_PROPOSALS.md
  临时长期记忆候选区；定时 consolidation 后归档并清空，避免长期堆积。

daily/YYYY-MM-DD.md
  近期工作观察、临时上下文、open loop。
```

当前 Memory 取舍：

- `memory_propose_long_term` 默认 `apply=false`，先写 proposal。
- 用户明确要求“记住”的稳定资料才使用 `apply=true` 写入 `MEMORY.md`。
- `MemoryExtractor` 每轮后运行，但应保守写入，只抽取未来仍会影响服务用户的信息。
- 不新增 `MemoryCurator`。
- 不做人工 review UI。
- proposal 不作为长期待办池。
- 低置信度候选宁可在 consolidation 后归档出主链路，也不要无限留在当前 proposal 文件里。

设计记录：

- `docs/modules/MEMORY.md`
- `docs/modules/MEMORY_PHASE2_RESEARCH.md`

### Skills

Skills v2 已形成最小可观察闭环：

- `skill_get(skill_id)` 按需加载完整 `SKILL.md`。
- 成功加载会记录 `skill_loaded`。
- turn-scoped active skills 会记录 `active_skill_set`。
- SubAgent 可继承紧凑的 parent active skill context。
- 暂不做自动 SkillSelector、persistent active skills 或 skill-defined tool permissions。

设计记录：

- `docs/modules/SKILLS.md`

### SubAgent

SubAgent 已进入可用阶段：

- `delegate_task` 已接入主 Agent。
- 内置 profile：`researcher`、`reviewer`、`interviewer`。
- 支持 profile-specific child tool allowlist。
- 支持自动委托策略，但仍保持同步、短生命周期。

当前边界：

- 子 Agent 可以读本地文件和使用只读 web 工具。
- 子 Agent 不写文件。
- 子 Agent 不递归委托。
- 子 Agent 不获得任意 MCP 工具权限。

设计记录：

- `docs/modules/SUBAGENT.md`

### Gateway / Cron / Message

Feishu Gateway、CronService、MessageTool 已落地：

- Gateway 模式运行 ChannelManager + AgentLoop + CronService。
- Feishu 审批请求会回到当前 chat，并以 interactive card 展示允许/拒绝按钮。
- Feishu 普通回复会将 Markdown-ish 内容转成 `post` 富文本，短纯文本仍用 `text`。
- Gateway 已接入同一条 approval callback；需要审批的工具操作会路由回当前 Feishu chat。
- Shell tool 已支持常见 PowerShell 只读管道，例如 `Get-Process | Measure-Object | Select-Object ...` 不再误触发审批。
- CronService 支持 `every` / `at` / `once`。
- 用户 cron 会路由回创建时的 channel/chat_id。
- 系统 cron 会注册 `memory_consolidation`。
- MessageTool 支持 Agent 显式发送消息和文件，并抑制重复最终回复。

## 最近验证

最近全量测试：

```text
python -m pytest
257 passed
```

最近 Feishu 长连接稳定性修正：

```text
python -m pytest tests/test_channels_feishu.py
23 passed

python -m pytest tests/test_channels_feishu.py tests/test_cli_channel.py tests/test_shell_tool.py tests/test_channels_manager.py
65 passed

python -m pytest
257 passed
```

最近代码收敛清理：
- 删除只剩测试引用的旧便捷 API：`ContextBuilder.build_messages`、`AgentLoop.history_for`、`AgentLoop.conversation_summary_for`、`MessageBus.inbound_size/outbound_size`、`CronService.get_job`、`WorkspaceLoader.load_all`。
- 删除旧 JSONL memory 时代遗留的 `MemoryEntry` 结构；当前主线使用 Markdown-backed memory。
- 对应测试改为验证主链路行为或现有核心接口，避免测试继续“供养”不再使用的旧代码。

实现记录：
- Feishu WebSocket 增加外层重连循环；如果 lark-oapi `client.start()` 异常退出或意外返回，gateway 进程会等待 5 秒后重建 WSClient。
- tenant_access_token 记录过期时间，发送前提前刷新；发送失败若命中 token 失效类错误，会刷新后重试一次。
- 发送失败、token 刷新失败、WebSocket 退出会打印可见诊断，避免 gateway 看起来还活着但用户侧无响应。
- 审批请求在 token 不可用时会直接返回拒绝结果，避免 future 永久挂起。

最近真实渠道 smoke test：

```text
Feishu Gateway smoke test passed.
验证项：/new、只读 shell 查询、富文本回复、项目状态总结、审批卡片。
```

最近 Memory focused verification：

```text
python -m pytest tests/test_memory_tools.py tests/test_memory_consolidator.py tests/test_agent_memory.py
14 passed
```

## 当前建议

短期不要继续横向堆功能。下一步建议从项目材料、体验边界和真实使用反馈入手：

1. 保持当前主链路稳定，优先修真实使用中暴露的卡点。
2. 后续如继续优化工具体验，优先单独设计 `allow / confirm / deny` 风险分层，减少低风险操作的审批打断。
3. Memory 写入质量暂不做专项观察；它价值高，但当前不容易可靠评估，避免为了观察而观察。
4. 如需继续增强，优先补小文档、小测试和真实验收清单，不新增重型模块。

工具权限策略已经暴露出“审批偏多”的体验问题，但当前不阻塞主功能。后续可以单独设计 `allow / confirm / deny` 风险分层，不建议夹在 Gateway 收口里做。

不建议当前立刻做：

- 新增 `MemoryCurator`。
- 人工 memory review UI。
- 向量库 / SQLite / knowledge graph memory。
- 自动 SkillSelector。
- persistent active skills。
- 子 Agent 写文件。
- recursive subagent delegation。
- 重型 workflow graph runtime。
- QQ Channel 实际接入。

## 手动检查路径

### CLI 基本链路

```text
python -m myagent
```

建议观察：

- 普通问答是否正常。
- 是否有意外 memory 写入。
- conversation summary 是否在长对话后更新。

### Feishu Gateway smoke test

```text
python -m myagent gateway
```

当前状态：已由用户真实验证通过。

建议在 Feishu 会话里依次测试：

```text
/new
帮我查看当前进程数量
用标题和列表总结一下这个项目现在能做什么
帮我总结一下 docs/NEXT_STEPS.md 的当前状态
帮我关闭手机连接应用
```

预期观察：

- `/new` 会开始一个新的 Feishu 会话上下文。
- 进程数量查询应走只读 shell 管道，不触发审批。
- 带标题和列表的回复应渲染为 Feishu `post` 富文本，而不是带行号的纯 Markdown。
- 总结项目状态时应能调用文件/上下文工具并给出最终回复。
- 关闭手机连接应用这类杀进程操作应触发 Feishu interactive card 审批；用户点允许后再执行，点拒绝则返回拒绝结果。
- 如果 Windows 权限不足，审批通过后仍可能返回 `Access is denied`，这是系统权限限制，不是卡片渲染失败。

### Trace

```text
python -m myagent trace latest
python -m myagent trace show --limit 10
python -m myagent trace context
python -m myagent trace report
python -m myagent trace viewer
```

建议观察：

- `context_built`
- `context_dropped`
- `conversation_summary_updated`
- `memory_candidates_saved`
- `skill_loaded`
- `active_skill_set`
- `subagent_start`

### SubAgent + Skills

给一个需要先加载 skill、再适合委托文件探索的真实任务，观察：

- 是否出现 `active_skill_set`
- 是否出现 `subagent_start`
- `subagent_start` 是否带 `inherited_active_skills`

## 用户偏好与工作约束

开发时继续遵守：

- 重要实现前先更新相关文档。
- 每个核心模块保持独立模块文档。
- 改完后回填实现说明和验证方式。
- 先让用户确认，再做 Git 提交。
- 提交按模块边界进行，不为每个小改动单独提交。
- 不提交真实配置、密钥、memory、trace、cache、本地测试目录。
- 项目优先服务学习、演示、面试表达，避免过度工程化。
- 不要一味迎合用户；发现设计冲突或复杂度过高时要直接指出。

## 续接顺序

新对话继续这个项目时，建议按下面顺序恢复上下文：

1. 读本文件。
2. 读 `docs/README.md` 了解文档地图。
3. 必要时读 `docs/PHASE2_REVIEW_PLAN.md` 了解历史复盘方法。
4. 按任务读模块文档：
   - `docs/modules/CONTEXT_BUILDER.md`
   - `docs/modules/MEMORY.md`
   - `docs/modules/SKILLS.md`
   - `docs/modules/SUBAGENT.md`
   - `docs/modules/TRACE.md`
5. 再看代码和测试。

## 最近提交

```text
94b7849 feat: improve feishu tool interactions
ec90d32 feat: add feishu approval cards
3fa3664 fix: shell tool hangs in gateway mode + encoding issues
70f79e8 feat: add execute_command tool for shell command execution
dbe2f47 feat: add /new command for all channels to start fresh session
22ab495 docs: consolidate project status docs
b884876 docs: clarify temporary memory proposals
b992e5f feat: clarify memory proposal workflow
```

## Profile / Memory / Runtime 边界收敛

当前按成熟 coding-agent 工具的做法，把“人写的稳定指令”和“Agent 自己记住的内容”分开：

```text
~/.myagent/profile/
  AGENT.md   # MyAgent 运行时身份、原则、行为风格
  USER.md    # 用户资料和稳定偏好
  TOOLS.md   # 工具使用提示

~/.myagent/memory/
  MEMORY.md
  MEMORY_PROPOSALS.md
  daily/YYYY-MM-DD.md

~/.myagent/runtime/
  cron/jobs.json
```

语义边界：
- `AGENTS.md` 是开发这个 repo 的协作规则，不进入 MyAgent runtime prompt。
- `profile/AGENT.md` 是 MyAgent 运行时 profile，类似 Claude Code 的 `CLAUDE.md` / Cursor rules。
- `memory/MEMORY.md` 是长期记忆，只存用户偏好、长期事实、稳定目标。
- session history、conversation summary、active skills 是进程内 session state，不是 long-term memory。
- trace、cron jobs 是 runtime data，不是 memory。

重命名策略：
- 不保留 `~/.myagent/workspace/` runtime 兼容读取，避免 workspace 概念继续污染 profile / memory / runtime。
- 旧 profile 文件需要手动移动到 `~/.myagent/profile/`。
- 旧 memory 文件需要手动移动到 `~/.myagent/memory/`。
- 旧 cron 文件需要手动移动到 `~/.myagent/runtime/cron/jobs.json`。
- 代码层删除 `myagent.workspace.WorkspaceLoader`，改为 `myagent.profile.ProfileLoader`。
