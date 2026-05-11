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

项目已经完成 Phase 1，当前处于 Phase 2：

```text
模块复盘 -> 文档校准 -> 小步增强 -> 验证 -> 用户确认
```

当前最重要的工作不是继续横向堆功能，而是：

1. 保持文档和真实实现一致。
2. 提升运行时可观测性，尤其是 Trace / Context / Skills / SubAgent 行为的可检查性。
3. 继续把 MyAgent 往个人助理 runtime 的方向校准，而不是往“工具越来越多的 coding agent”漂移。

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

## 最近记录的验证状态

我这次只做了文档阅读和状态整理，没有重新跑测试。

文档里最近一次记录到的全量测试结果是：

```text
python -m pytest
133 passed, 1 skipped
```

测试基线：

```text
python -m pytest
144 passed
```

## 当前最推荐的下一步

文档清理完成后，最推荐的下一步仍然是：

```text
继续做 Trace / runtime observability 的小步增强与验证
```

原因：

- 这是当前最能帮助所有模块调试的公共支点。
- 它对 Memory、Skills、SubAgent、MCP、ContextBuilder 都直接有价值。
- 它比继续扩展自动 SkillSelector、复杂 SubAgent 编排、持久 active skills 更稳。

更具体地说，下一步适合做的是：

1. 手动验证当前 trace 命令链是否顺手、输出是否一致。
2. 看是否还需要一个更统一的“runtime overview”入口，把 turn trace、startup trace、skills trace 串起来。
3. 如果验证无明显问题，再决定是否进入下一轮 trace polish，还是切回 SubAgent + Skills 的进一步整理。

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

1. `NEXT_STEPS` 之外，是否需要额外的更短项目状态页，例如 `docs/PROJECT_STATUS.md`？
2. Trace 是否需要一个更统一的 runtime overview 命令？
3. 未来 Active Skill 传递给 SubAgent 时，紧凑上下文是否已经足够，还是还缺一个 task-level abstraction？
4. Agent workspace 第一版何时真正落到 `~/.myagent/workspace`？
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
