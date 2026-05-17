# MyAgent 阶段性项目报告 - 2026-05-17

## 一句话总结

MyAgent 当前已经从“本地 CLI Agent 骨架”推进到“可在 Feishu 中真实使用的 local-first 个人助理 runtime”。主链路包括对话、工具调用、文件操作、Shell、记忆、Skills、SubAgent、MCP、Trace、Cron 和 Feishu Gateway，当前阶段重点不是继续堆功能，而是保持可运行、可解释、可演示。

## 当前定位

MyAgent 的定位是：

```text
一个 local-first、轻量、可教学、可面试讲解的个人助理 Agent runtime。
```

这不是一个追求生产级复杂调度的平台。当前设计更重视：

- 主链路能跑通。
- 模块边界清楚。
- 每个取舍能解释。
- 文档能承接跨对话继续开发。
- 功能足够贴近个人助理场景，而不只是 coding demo。

## 已完成能力

### Agent 主链路

- CLI Channel / MessageBus / AgentLoop 已形成基本闭环。
- 支持 OpenAI-compatible provider 和 EchoProvider。
- 支持 OpenAI-compatible tool calling。
- AgentLoop 能执行工具、回填工具结果，并生成最终回复。

### Context

- ContextBuilder 支持预算控制、system section 分层、history 裁剪。
- Conversation summary 已落地：保留 running summary 和最近原始消息。
- 当前没有做复杂的 working-turn tool result compaction，大文件依靠 `read_file offset/limit` 分页读取。

### Tools

默认工具集合包括：

```text
list_dir
read_file
write_file
edit_file
copy_file
move_file
web_search
web_fetch
execute_command
delegate_task
memory tools
message tool
skill tools
```

文件工具采用一个清楚的边界：

- 工作区内读写：默认允许。
- 工作区外只读：允许。
- 工作区外变更：走当前 Channel 审批。

Shell 工具当前支持：

- Windows PowerShell 语义。
- 持久 working directory。
- 常见只读命令直接执行。
- 只读 PowerShell 管道直接执行，例如 `Get-Process | Measure-Object | Select-Object ...`。
- 杀进程、删除、写文件、未知复杂命令仍走审批。

### Feishu Gateway

Feishu Gateway 已进入可用阶段：

- Gateway 模式运行 ChannelManager + AgentLoop + CronService。
- `/new` 可在飞书聊天里开启新上下文。
- 普通回复支持 Markdown-ish 到 Feishu `post` 富文本转换。
- 审批请求会以 Feishu interactive card 回到当前 chat。
- 用户可在卡片上点击“允许 / 拒绝”。
- 真实 smoke test 已通过。

已验证场景：

```text
/new
查看当前进程数量
带标题和列表的项目总结
总结 docs/NEXT_STEPS.md
关闭手机连接应用并触发审批
```

### Memory

Memory 已从早期 JSONL recall 转向 Markdown-backed workspace：

```text
MEMORY.md
MEMORY_PROPOSALS.md
daily/YYYY-MM-DD.md
```

当前取舍：

- 稳定长期资料进入 `MEMORY.md`。
- 候选长期记忆先进入 `MEMORY_PROPOSALS.md`。
- 当天观察和 open loop 进入 daily 文件。
- 不新增 `MemoryCurator`。
- 不做人工 review UI。
- 暂不做专项“写入质量观察”，因为它不容易形成可靠验收，容易变成额外负担。

### Skills

Skills 当前是“按需加载的工作流说明”：

- `skill_get(skill_id)` 加载完整 `SKILL.md`。
- 记录 `skill_loaded`。
- 记录 turn-scoped active skills。
- SubAgent 可以继承紧凑 active skill context。
- 暂不做自动 SkillSelector 和 persistent active skills。

### SubAgent

SubAgent 已可用于同步、短生命周期任务委托：

- 内置 `researcher`、`reviewer`、`interviewer` profile。
- 子 Agent 使用受限工具集合。
- 子 Agent 可以读文件和用只读 web 工具。
- 子 Agent 不写文件、不递归委托、不继承任意 MCP 工具。

### MCP

MCP 已支持 stdio / HTTP / SSE 风格接入：

- 启动时连接配置中的 MCP server。
- 发现 tools 并注册到 ToolRegistry。
- 支持 include/exclude tool filtering。
- 启动期会记录 MCP connection summary。

### Trace

Trace 已有 JSONL 记录和 CLI 查看能力：

```text
python -m myagent trace latest
python -m myagent trace show --limit 20
python -m myagent trace context
python -m myagent trace report
python -m myagent trace viewer
```

当前用户暂不想做可观察性专项清理，因此 Trace 后续只在真实问题暴露时小步补强。

## 最近完成的关键工作

### 1. Feishu `/new`

飞书聊天场景不像控制台那样天然有“关闭重开”的入口，所以新增 `/new`，让用户可以在同一个 chat 里显式切新上下文。

价值：

- 解决聊天渠道上下文过长的问题。
- 贴近豆包等 IM bot 的使用习惯。
- 不改变 AgentLoop 核心，只在 Channel/会话层处理。

### 2. Feishu 审批卡片

危险工具操作不再只能依赖 CLI 输入，而是通过当前 Channel 发回审批请求。

价值：

- 飞书里能真正完成“用户确认后执行”的闭环。
- 审批逻辑归 Channel 所有，工具只提出请求。
- 适合后续扩展到其他聊天渠道。

### 3. Feishu 富文本渲染

普通 Markdown-ish 回复转成 Feishu `post` 消息：

- 标题
- 列表
- 粗体
- 链接
- 代码块

价值：

- 避免飞书把 Markdown 当纯文本或行号样式显示。
- 项目总结、报告、列表型回复更可读。

### 4. Shell 工具可用性修复

修复了 Windows PowerShell 场景下两个重要问题：

- 只读管道不再一律触发审批。
- Gateway 也接入 approval callback，审批能回到飞书 chat。

典型结果：

```text
Get-Process | Measure-Object | Select-Object -ExpandProperty Count
```

现在是只读查询，不触发审批。

```text
taskkill /f /im PhoneExperienceHost.exe
```

仍然触发审批，因为它会杀进程。

## 当前验证状态

自动测试：

```text
python -m pytest
256 passed
```

真实 Feishu smoke test：

```text
passed
```

已验证：

- `/new`
- 只读 shell 查询
- Feishu 富文本回复
- 文件读取/项目状态总结
- 杀进程审批卡片

## 当前限制

### 工具审批偏多

目前 Shell 权限仍主要依赖安全命令列表和危险命令列表。它已经比最初可用，但还不是成熟的风险策略。

后续建议单独设计：

```text
allow   直接执行
confirm 需要审批
deny    直接拒绝
```

不建议现在夹在其他收口任务里顺手做。

### Memory 质量不易验收

Memory 是个人助理的核心，但“写得好不好”很难靠一次自动测试判断。当前先保持结构稳定，不做新的 MemoryCurator 或 review UI。

### Feishu 渲染仍是小子集

当前只支持常见 Markdown-ish 内容，不追求完整 Markdown 兼容。对报告和普通对话已经够用，复杂表格、嵌套列表、图片混排可后续再补。

### 非管理员操作限制

审批通过不代表系统一定允许执行。例如 `taskkill` 可能仍因 Windows 权限不足返回 `Access is denied`。这是系统权限限制，不是审批卡片失败。

## 下一步建议

短期建议不要继续横向堆新功能。优先顺序：

1. 保持 Feishu Gateway 主链路稳定。
2. 遇到真实工具使用卡点时，小步修工具体验。
3. 单独设计工具权限风险分层，减少低风险审批打断。
4. Memory 暂时不专项观察，等出现真实记忆噪声或漏记问题再调。
5. Trace 暂时不专项清理，保留现有 inspect/report/viewer 能力即可。

不建议现在做：

- 重型 workflow graph runtime。
- 自动 SkillSelector。
- 人工 memory review UI。
- 向量库 / SQLite / knowledge graph memory。
- 子 Agent 写文件。
- recursive subagent delegation。
- 新 IM Channel 大规模接入。

## 适合对外讲解的版本

可以这样介绍项目：

> MyAgent 是一个 local-first 的个人助理 Agent runtime。它不是只做一次 prompt 调用，而是把 Channel、AgentLoop、Context、Memory、Tools、SubAgent、MCP 和 Trace 拆成清楚的模块。当前已经能在 CLI 和 Feishu 中运行，支持工具调用、文件操作、Shell 查询、审批卡片、定时任务和 Markdown-backed memory。设计上优先保持轻量、可解释、可测试，避免一开始就引入复杂的工作流引擎或重型存储。

如果强调最近成果：

> 最近主要把 Feishu 渠道从“能收发消息”推进到“可真实使用”：支持 `/new` 切上下文、富文本回复、工具审批卡片，以及 Windows Shell 查询/审批链路。真实 smoke test 已通过，全量测试 256 passed。

