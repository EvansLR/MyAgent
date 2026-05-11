# Skills 模块设计

## 职责

Skills 负责让 MyAgent 发现和使用本地的能力说明文档。

一句话版本：

```text
Skills 扫描 skills/*/SKILL.md，提取摘要注入 ContextBuilder，让模型知道当前有哪些可用能力。
```

它属于 `Capability Layer`，但第一版更接近“提示词能力扩展”，不是 Python 插件系统。

## 当前状态速览

这份文档前半部分保留了 Skills 第一阶段的设计口径，用来解释它为什么从
`skills/*/SKILL.md` 摘要扫描开始。

但当前真实实现已经进入 Phase 2，Skills 不再只是“摘要注入”：

- ContextBuilder 会继续注入 `# Available Skills` 摘要。
- Agent 可以通过 `skill_get(skill_id)` 按需加载完整 `SKILL.md`。
- `skill_get` 成功后，runtime 会记录：
  - `skill_loaded`
  - `active_skill_set`
- `active_skill_set` 当前是 turn-scoped runtime observation，不持久化。
- SubAgent 已能继承紧凑的 active skill context，但不会自动获得新工具。

当前边界：

- 不做 automatic SkillSelector。
- 不做 persistent active skills。
- 不做 skill-defined tool permissions。
- 不自动把完整 `SKILL.md` 注入 SubAgent。

## 为什么需要它

现在 MyAgent 已经有：

- 基础对话
- 工具调用
- Trace
- Memory

但如果我们希望 MyAgent 在特定任务上表现更稳定，只靠通用 system prompt 不够。

比如后续我们可能希望有：

```text
skills/interview/SKILL.md
skills/code-review/SKILL.md
skills/project-docs/SKILL.md
```

每个 skill 说明：

- 什么时候应该使用它
- 它擅长什么
- 回答时要遵守什么流程
- 需要读取哪些补充材料

Skills 的价值是把这些能力模块化，而不是把所有提示词都塞进一个超长 system prompt。

## 参考 NanoBot 的取舍

NanoBot 的 skill 机制更完整，通常包含：

- skill metadata
- trigger rules
- lazy loading
- skill registry
- active skills
- context budget
- 和工具/MCP 的联动

MyAgent 第一阶段最初只保留：

- 扫描 `skills/*/SKILL.md`
- 提取 name / description
- 提取 summary
- 注入 `# Available Skills`
- 暂时不自动加载全文

暂不实现：

- LLM 自动选择 skill
- active skills
- skill 全文按需加载
- skill 内工具注册
- skill marketplace
- 复杂 trigger 规则
- token budget

这样能先跑通：

```text
本地能力文档 -> SkillRegistry -> ContextBuilder -> LLM
```

这段描述的是最初设计口径；当前真实实现已经增加 `skill_get`、`skill_loaded`、`active_skill_set` 和 SubAgent 轻量继承路径，见本文顶部“当前状态速览”。

## Skill 文件结构

第一版约定每个 skill 是一个目录：

```text
skills/<skill-name>/SKILL.md
```

示例：

```text
skills/interview/SKILL.md
```

推荐格式：

```markdown
---
name: interview
description: Help MyAgent answer in an interview-oriented way.
---

# Interview Skill

## Description

Help MyAgent answer in an interview-oriented way.

## When To Use

Use when the user asks about interview preparation, project explanation, resume polishing, or mock interview questions.

## Instructions

- Prefer structured answers.
- Explain tradeoffs.
- Connect answers to MyAgent's architecture when relevant.
```

第一版解析规则保持简单：

- 如果存在 YAML frontmatter，优先读取 `name` 和 `description`
- `# ...` 作为 skill name
- `## Description` 下第一段作为 description
- 如果没有 Description，就取文件前几行作为 summary
- skill id 来自目录名

YAML frontmatter 是公开 agent skill 示例里常见的写法，MyAgent 第一版可以兼容它，但不要求完整 YAML 解析器；只需要识别简单的 `name` / `description` 即可。

## 数据结构

建议新增：

```text
myagent/skills/
  __init__.py
  entries.py
  loader.py
  registry.py
```

### SkillEntry

字段：

```text
id: str
name: str
description: str
path: Path
```

第一版只需要这些字段。

后续可以扩展：

```text
triggers
full_content
priority
metadata
```

### SkillLoader

负责从文件系统读取 `SKILL.md`：

```text
load_skill(path) -> SkillEntry
scan(root="skills") -> list[SkillEntry]
```

如果 `skills/` 不存在，返回空列表。

### SkillRegistry

负责管理扫描结果：

```text
list_skills() -> list[SkillEntry]
format_for_context() -> str
```

第一版不需要复杂注册逻辑，只要能扫描并格式化即可。

## ContextBuilder 接入

ContextBuilder 增加可选：

```text
skill_registry
```

构建 system prompt 时，如果存在 skills，就注入：

```text
# Available Skills

- interview: Interview Skill - Help MyAgent answer in an interview-oriented way.
- project-docs: Project Docs Skill - Help maintain project documentation.
```

注意：

```text
第一版只注入摘要，不注入全文。
```

原因：

- 避免 prompt 太长。
- 先让模型知道“有哪些 skill”。
- 后续再做按需加载全文。

## 与 AgentLoop 的关系

AgentLoop 默认创建 SkillRegistry 并交给 ContextBuilder。

流程：

```text
AgentLoop init
  -> scan skills/
  -> ContextBuilder(skill_registry=...)
process_message
  -> ContextBuilder builds system prompt with Available Skills
```

第一阶段最初 Skills 不直接参与 tool calling，它只是上下文能力提示。

当前真实状态已经继续演进：

- AgentLoop 在存在 skill 时会注册 `skill_get`
- provider 可在当前 turn 中调用 `skill_get`
- runtime 会把成功加载的 skill 记录为 active skill trace

## 与 Memory 的区别

Memory 是用户长期事实。

Skills 是系统能力说明。

区别：

```text
Memory: 用户是谁、偏好是什么、长期目标是什么
Skills: MyAgent 会什么、遇到某类任务应该怎么做
```

两者都会进入 ContextBuilder，但来源和用途不同。

## 与 MCP 的关系

Skills 不是 MCP。

Skills 是本地 prompt/document 能力说明。

MCP 是外部工具协议。

后续可以组合：

```text
Skill 告诉模型什么时候应该使用某类能力
MCP 提供实际可调用工具
```

但第一版 Skills 不注册工具。

## 第一阶段范围

第一阶段实现：

- `SkillEntry`
- 扫描 `skills/*/SKILL.md`
- 解析 name 和 description
- SkillRegistry 格式化 Available Skills
- ContextBuilder 注入 skills section
- 测试覆盖
- 三个示例 skill

当前示例：

```text
skills/interview-prep/SKILL.md
skills/code-review/SKILL.md
skills/commit-message/SKILL.md
```

这三个 skill 用于测试扫描和上下文注入：

- `interview-prep`：面试准备和项目讲解
- `code-review`：代码审查
- `commit-message`：提交信息生成

## 暂不实现

第一阶段暂不实现：

- LLM 自动选择 active skill
- skill 全文按需加载
- skill trigger 复杂规则
- skill 内工具注册
- skill 优先级
- skill 热更新
- skill 子命令
- skill marketplace
- token budget

## 测试点

建议新增：

```text
tests/test_skills.py
tests/test_context_builder.py
```

测试内容：

1. 没有 `skills/` 目录时返回空列表。
2. 能扫描 `skills/*/SKILL.md`。
3. 能从一级标题读取 skill name。
4. 能从 `## Description` 读取 description。
5. SkillRegistry 能格式化 Available Skills。
6. ContextBuilder 能注入 Available Skills section。

## 手动测试方式

创建：

```text
skills/interview-prep/SKILL.md
```

运行：

```text
python -m myagent
```

然后问：

```text
你现在有哪些 skills？
```

预期模型能从 system prompt 里知道当前有哪些可用 skill。

## 面试表达

可以这样讲：

> 我把 Skills 设计成一种本地提示词能力扩展，而不是 Python 插件系统。每个 skill 是一个 `SKILL.md`，启动时扫描摘要并注入 ContextBuilder，让模型知道当前有哪些领域能力。第一版只注入摘要，避免上下文太长；后续可以根据模型判断再按需加载 skill 全文，升级成 active skill 机制。

如果面试官问“Skills 和工具有什么区别”，可以回答：

> Tool 是可执行能力，比如读文件、查目录、调用 MCP；Skill 是行为指导，告诉模型遇到某类任务应该采用什么策略。Skill 不一定执行动作，它更像可插拔的提示词知识包。

## 后续扩展方向

后续可以增强：

- active skill selection
- 按需加载完整 `SKILL.md`
- trigger rules
- skill priority
- skill metadata
- skill trace
- skill CLI 子命令
- skill + MCP 联动
- token-aware skill injection
- skills marketplace

## 第二次迭代重点

第一版 Skills 只做：

```text
扫描 skills/*/SKILL.md
-> 注入 name / description / path
-> 让模型知道有哪些可用能力
```

但这还不是完整的 skill 调用机制。

第二次迭代需要重点完善：

```text
模型或 AgentLoop 如何加载完整 SKILL.md？
```

目前有两个可选方向：

### 方向一：借助已有 read_file 工具

第一版在 `# Available Skills` 里注入 path：

```text
- code-review
  Description: Review code changes for bugs...
  Path: skills/code-review/SKILL.md
```

模型如果判断需要使用该 skill，可以调用已有工具：

```text
read_file(path="skills/code-review/SKILL.md")
```

优点：

- 实现成本低
- 复用 ToolRegistry
- 用户能看到正在调用工具

缺点：

- 依赖模型自己判断何时读取
- 不够稳定
- 可能忘记读取完整 skill

### 方向二：实现 SkillSelector / Active Skills

AgentLoop 或独立模块先判断当前用户问题适合哪些 skill：

```text
user message
  -> SkillSelector
  -> selected skill ids
  -> load full SKILL.md
  -> ContextBuilder injects # Active Skills
  -> Provider
```

优点：

- 更稳定
- 更像成熟 Agent 系统
- 能控制注入哪些 skill 全文

缺点：

- 需要额外设计 selector
- 要考虑 token budget
- 要处理多 skill 冲突

### 当前结论

这个增强不在第一版实现。

先把第一版扫描和摘要注入跑通，第二次迭代再设计：

```text
SkillSelector
Active Skills section
Full SKILL.md lazy loading
```

这会是 Skills 模块从“能力列表提示”升级为“可激活能力机制”的关键一步。

## Phase 2 Research

第二轮参考了成熟 Agent / Coding Agent 的能力加载机制：

- Claude Code / Agent Skills 强调 progressive disclosure：先向模型暴露 skill metadata，完整说明按需加载。
- Claude Code skills 使用 `SKILL.md`，可带 frontmatter，例如 `name`、`description`、`allowed-tools`。
- Codex / AGENTS.md 的经验说明：稳定规则应放入本地可读文件，而不是依赖早期对话。
- OpenClaw 的 context 经验说明：默认 context 应保持轻量，可通过工具读取更多 workspace / skill 内容。

可采纳结论：

```text
Skills v2 不应该把所有 SKILL.md 全文塞进 system prompt。
默认注入轻量 skill summary。
当模型判断需要完整流程时，通过显式工具加载完整 skill。
```

## Phase 2A Implementation Notes

本阶段已经把 Skills 从“摘要注入”升级为“摘要注入 + 按需加载全文”的最小闭环。

新增/修改能力：

```text
SkillEntry.allowed_tools
SkillRegistry.get(skill_id)
SkillRegistry.read_skill(skill_id)
skill_get(skill_id)
```

### Progressive Disclosure

`# Available Skills` 仍然只注入轻量摘要：

```text
- code-review
  Name: code-review
  Description: Review code changes...
  Path: skills/code-review/SKILL.md
  Allowed Tools: read_file, list_dir
  Full Instructions: call skill_get with this skill id when needed.
```

完整 `SKILL.md` 不默认进入 context。

当模型需要完整 skill 工作流时，应调用：

```text
skill_get(skill_id="code-review")
```

这会返回：

```text
Skill metadata
Allowed tools
Full SKILL.md content
```

### AgentLoop 接入

当 `SkillRegistry` 中存在 skill 时，`AgentLoop` 默认注册：

```text
skill_get
```

这样 skill 全文加载变成可观测工具调用，而不是隐藏 prompt 注入。

### 当前边界

当前还没有实现：

- 自动 SkillSelector
- 多 skill 冲突处理
- active skill section 持久化
- allowed-tools 权限强制
- skill marketplace
- skill 热加载

这些等 Skills pipeline 继续变复杂后再做。

### 测试

新增/更新测试：

```text
tests/test_skill_tools.py
tests/test_skills.py
tests/test_agent_skills.py
```

覆盖内容：

- frontmatter 解析 `allowed-tools`
- Available Skills 提示使用 `skill_get`
- `skill_get` 返回完整 `SKILL.md`
- AgentLoop 在存在 skill 时注册 `skill_get`

验证结果：

```text
python -m pytest
90 passed, 1 skipped
```

### Imported Skills For Local Testing

为了测试 `skill_get` 和 progressive disclosure，本地新增了 5 个公开示例 skill。

来源：

```text
https://github.com/anthropics/skills
commit: d211d437443a7b2496a3dad9575e7dddd724c585
```

新增目录：

```text
skills/doc-coauthoring/
skills/frontend-design/
skills/mcp-builder/
skills/skill-creator/
skills/webapp-testing/
```

它们用于覆盖不同触发场景：

- `doc-coauthoring`：写文档、技术方案、proposal。
- `frontend-design`：前端页面、组件、UI 美化。
- `mcp-builder`：设计和实现 MCP server。
- `skill-creator`：创建、优化、评测 skill。
- `webapp-testing`：用 Playwright 测试本地 web app。

本地触发示例：

```text
请先加载 webapp-testing skill，然后告诉我怎么测试本地前端页面。
```

```text
请使用 mcp-builder skill，帮我设计一个 GitHub issue 管理 MCP server。
```

如果触发成功，CLI 应显示类似：

```text
正在调用工具：skill_get skill_id=mcp-builder
```

## 第一阶段实现记录

本阶段已经完成 Skills 第一版：扫描本地 skill 摘要并注入 ContextBuilder。

新增/修改文件：

```text
myagent/skills/__init__.py
myagent/skills/entries.py
myagent/skills/loader.py
myagent/skills/registry.py
myagent/agent/context.py
myagent/agent/loop.py
skills/interview-prep/SKILL.md
skills/code-review/SKILL.md
skills/commit-message/SKILL.md
tests/test_skills.py
tests/test_context_builder.py
tests/test_agent_skills.py
```

### 代码阅读顺序

建议按这个顺序看：

1. `myagent/skills/entries.py`
2. `myagent/skills/loader.py`
3. `myagent/skills/registry.py`
4. `myagent/agent/context.py`
5. `myagent/agent/loop.py`
6. `tests/test_agent_skills.py`

### SkillLoader

`SkillLoader` 默认扫描：

```text
skills/*/SKILL.md
```

支持两种信息来源：

1. YAML frontmatter：

```yaml
---
name: code-review
description: Review code changes for bugs, regressions, missing tests, and maintainability risks.
---
```

2. Markdown fallback：

```text
# Code Review

## Description

Review code changes...
```

如果都没有，就使用目录名和文件前几行作为 fallback。

### SkillRegistry

`SkillRegistry` 保存扫描到的 skill，并格式化为 ContextBuilder 可注入的文本。

示例：

```text
- code-review
  Name: code-review
  Description: Review code changes for bugs, regressions, missing tests, and maintainability risks.
  Path: skills/code-review/SKILL.md
```

注意这里会注入 `Path`。

第一版模型不会自动“调用 skill”，但它能看到 path；如果需要读取完整 skill，可以通过已有 `read_file` 工具读取该路径。

### ContextBuilder 接入

ContextBuilder 新增：

```python
skill_registry=SkillRegistry(...)
```

如果存在 skills，会注入：

```text
# Available Skills

...
```

没有 skills 时不注入这个 section。

### AgentLoop 默认行为

AgentLoop 默认执行：

```python
SkillRegistry.from_directory()
```

也就是扫描项目根目录下的：

```text
skills/
```

然后把 registry 交给 ContextBuilder。

### 示例 Skills

当前内置三个示例：

```text
skills/interview-prep/SKILL.md
skills/code-review/SKILL.md
skills/commit-message/SKILL.md
```

它们主要用于：

- 手动测试
- 自动化测试
- 展示 Skills 文件格式

### 手动测试

运行：

```text
python -m myagent
```

输入：

```text
你现在有哪些 skills？请列出 name、description、path。
```

预期能看到：

```text
interview-prep
code-review
commit-message
```

以及对应：

```text
skills/.../SKILL.md
```

如果想验证读取完整 skill，可以输入：

```text
请先读取 skills/code-review/SKILL.md，然后严格按照这个 skill 的 Output Shape 来审查 Memory 模块。
```

这时应该能看到工具状态：

```text
正在调用工具：read_file path=skills/code-review/SKILL.md
```

### Spinner 说明

第一版 Skills 不会在 spinner 里显示：

```text
正在调用 skill：code-review
```

原因是它还不是显式 action。

它只是 system prompt 里的 `# Available Skills` section。

只有当模型使用 `read_file` 读取完整 `SKILL.md` 时，才会显示工具调用状态。

### 测试说明

新增/更新测试：

```text
tests/test_skills.py
tests/test_context_builder.py
tests/test_agent_skills.py
```

覆盖内容：

- skills 目录不存在时返回空列表
- 扫描 `skills/*/SKILL.md`
- 解析 frontmatter name / description
- fallback 到 Markdown 一级标题和 Description section
- SkillRegistry 格式化 Available Skills
- ContextBuilder 注入 Available Skills section
- AgentLoop 默认把 skills 注入 system prompt

验证结果：

```text
python -m pytest
67 passed
```

### 当前边界

当前 Skills 已经能让模型知道有哪些能力摘要，但还没有：

- active skill selection
- 自动加载完整 SKILL.md
- skill trace
- skill 子命令
- token budget
- skill trigger 规则

这些留到第二次迭代。
## Phase 2B Design Note

### Context Lifecycle

MyAgent rebuilds the system prompt for every user turn. This does not mean skill
content is appended to conversation history over and over.

Current flow:

```text
user message
  -> AgentLoop loads session history
  -> ContextBuilder renders a fresh system prompt
  -> Available Skills summary appears once in that prompt
  -> provider may call skill_get
  -> skill_get result is used inside the current turn
  -> only user message and final assistant answer are saved to session history
```

So there are three different scopes:

```text
system prompt:
  skill summaries, rebuilt each turn, not saved into history

current turn working messages:
  tool calls and tool results, including full SKILL.md from skill_get

session history:
  user messages and final assistant answers
```

This matches the usual progressive-disclosure pattern used by agent frameworks:
metadata stays cheap and always visible; full instructions are loaded only when
the model decides they are needed.

### Skill / Tool / SubAgent Boundary

```text
Skill:
  describes how to approach a class of tasks

Tool:
  performs an action such as reading files, writing files, searching, or loading
  a skill

SubAgent:
  runs a bounded task with its own prompt and restricted tool set
```

Skills are not a replacement for SubAgents. A skill is a workflow or capability
guide. A SubAgent is an execution unit that can apply a skill-like workflow while
keeping context and permissions scoped.

### Phase 2B Scope

The next small improvement is observability, not automatic skill selection.

Implemented direction:

```text
skill_get(skill_id)
  -> load full SKILL.md
  -> emit trace event: skill_loaded
  -> emit trace event: active_skill_set
```

Trace event:

```text
session: runtime:skills
turn: skills
event: skill_loaded
data:
  skill_id
  name
  description
  path
  content_length
```

Trace event:

```text
session: runtime:skills
turn: skills
event: active_skill_set
data:
  skill_id
  name
  scope: turn
  reason: loaded_by_skill_get
```

Deferred:

- automatic SkillSelector
- persistent Active Skills section
- multi-skill conflict handling
- skill usage scoring
- skill + SubAgent automatic routing

## Active Skill Proposal

### What It Means

An Active Skill is an explicit runtime observation that a skill is being used for
the current work.

It is different from Available Skills:

```text
Available Skills:
  the model can see that a skill exists

Loaded Skill:
  the model called skill_get and received the full SKILL.md content

Active Skill:
  the runtime records that this skill is relevant to the current turn/task
```

For example:

```text
User: Help me design a club promotion HTML page.
Model: skill_get(frontend-design)
Runtime: active_skill_set skill_id=frontend-design scope=turn
```

The main purpose is observability and future control. It lets us answer:

```text
Which skill did the agent actually use for this turn?
Was this skill only used once, or should it keep affecting the task?
Should a reviewer/researcher SubAgent inherit this skill context later?
```

### Why It Exists

Without Active Skill, MyAgent only knows that `skill_get` was called.

That is useful, but incomplete:

```text
skill_get:
  means full instructions were loaded

active_skill:
  means the runtime considers that skill part of the current task state
```

This distinction matters later because not every loaded skill should become
long-lived state. A model may inspect a skill and then decide it is not useful.

### First Implementation Scope

The first version should be turn-level only.

```text
scope = turn
```

Behavior:

```text
skill_get succeeds
  -> trace skill_loaded
  -> trace active_skill_set
```

Trace event:

```text
event: active_skill_set
data:
  skill_id
  name
  scope: turn
  reason: loaded_by_skill_get
```

It should not:

- persist into session history
- inject a new Active Skills section into future turns
- automatically select skills before the model asks
- override model behavior
- bind SubAgents automatically

This keeps the feature explainable:

```text
Active Skill v1 is an observation, not a controller.
```

### Future Versions

Later, after Task/Run state becomes clearer, Active Skill can grow into:

```text
session-level active skills:
  continue applying across a short conversation

task-level active skills:
  attach to a task/run until the task completes

selector-driven active skills:
  model or heuristic selects likely skills before first provider call

subagent skill inheritance:
  delegated researcher/reviewer can receive selected skill context
```

These are intentionally deferred because they need clearer task boundaries,
conflict handling, and token budgeting.

### Implementation Note

Implemented in the first Active Skill step:

```text
skill_get success
  -> active_skill_set trace event with scope=turn
```

No behavior change. No new prompt section. No persistence.

## SubAgent Alignment

Active Skill is intentionally designed so it can later help SubAgents without
making Skills responsible for execution boundaries.

The boundary is:

```text
Skill:
  workflow guidance

Active Skill:
  runtime observation that a skill was used in the current turn

SubAgentProfile:
  role, instructions, allowed tools, and execution limits
```

Recommended future behavior:

```text
Parent turn activates a skill
Parent delegates a task
Child SubAgent may receive compact active skill context
Child SubAgent does not automatically receive new tools
```

Implemented first slice:

```text
skill_get
  -> active_skill_set
  -> later delegate_task in the same turn
  -> child prompt receives compact # Parent Active Skills context
  -> subagent_start trace records inherited_active_skills
```

This means Active Skill can answer:

```text
Which workflow was the parent Agent using?
Should the child Agent be aware of that workflow?
```

It should not answer:

```text
What tools is the child Agent allowed to use?
Should the child Agent receive every full SKILL.md?
Should this skill remain active forever?
```

Full skill inheritance, skill/profile binding, and automatic SkillSelector stay
deferred until task/run state and conflict handling are clearer.

The implementation is intentionally turn-local. Active skills are not saved into
memory and are not carried into future turns.

Current lifecycle rule:

```text
skill_get succeeds
  -> the skill becomes active for the rest of the current turn

final answer is published
  -> turn ends
  -> active skill state is cleared
```

This means Active Skill is not "used until explicitly finished". It is simply
"active for this turn, then cleared when the turn completes."

## Implementation Note: Turn-Scoped Active Skills

This step is now implemented.

What changed:

- `ContextBuilder` now accepts an optional `active_skills_provider`.
- When the current turn has active skills, ContextBuilder adds a compact:

```text
# Active Skills
```

section to the system prompt.
- `AgentLoop` now exposes compact current-turn active skill context to ContextBuilder.
- `AgentLoop` refreshes the system prompt before each provider call inside the
  tool loop, so turn-local runtime state can appear after tools run.

Current lifecycle rule:

```text
skill_get succeeds
  -> active_skill_set is recorded for the current turn
  -> later provider calls in the same turn include # Active Skills
  -> final answer ends the turn
  -> active skills for that turn are cleared
```

So Active Skill is not cleared because the runtime decides the skill is
"finished" mid-turn. It stays active for the rest of the current turn and is
cleared when the turn completes.

This means:

- same user turn: active
- next user turn: inactive unless a skill is loaded again

What it does:

- reinforces the selected workflow inside long tool-heavy turns
- gives the parent Agent an explicit compact reminder of the current skill
- keeps skill influence turn-local instead of persistent

What it still does not do:

- no cross-turn persistence
- no explicit deactivation in the middle of a turn
- no automatic replacement/conflict policy
- no automatic skill selection
- no permission changes based on skills

Focused verification:

```text
python -m pytest tests/test_context_builder.py tests/test_agent_skills.py
16 passed
```
