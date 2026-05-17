# MyAgent 个人助理方向调研

## 为什么补这份文档

用户明确指出：

```text
MyAgent 应该是用户个人助理型 Agent，类似 OpenClaw，而不是只服务当前代码项目的 Coding Agent。
```

这意味着后续设计不能只围绕：

```text
读代码 -> 改代码 -> 跑测试
```

而应该围绕：

```text
长期理解用户 -> 管理个人上下文 -> 使用工具完成任务 -> 多通道陪伴式协作
```

这份文档从 OpenClaw 相关机制中提取对 MyAgent 有价值的设计方向。

## OpenClaw 值得学习的机制

### 1. Agent Workspace 是“家”

OpenClaw 把 agent 的长期状态放在 workspace 中。workspace 不是单纯代码目录，而是 agent 的家。

典型文件包括：

```text
AGENTS.md
SOUL.md
USER.md
IDENTITY.md
TOOLS.md
HEARTBEAT.md
MEMORY.md
memory/YYYY-MM-DD.md
skills/
```

可采纳经验：

- MyAgent 也应该有一个 agent workspace，而不只是当前代码仓库。
- repo workspace 和 personal agent workspace 要分开理解。
- 当前项目目录只是 MyAgent 的源码；真正运行时的个人助理状态应该能放在独立 workspace，例如：

```text
~/.myagent/workspace/
```

### 2. Persona、User、Memory 分离

OpenClaw 把 agent 自身、用户资料和长期记忆拆成不同文件：

- `SOUL.md`：persona、价值、语气、边界。
- `IDENTITY.md`：名字、外部展示。
- `USER.md`：用户是谁、偏好、称呼方式。
- `MEMORY.md`：长期事实、偏好和决策。
- `AGENTS.md`：操作规则和工作方式。

可采纳经验：

- MyAgent 不应把所有长期上下文都叫 memory。
- 应区分：

```text
Identity
Persona
User Profile
Operating Rules
Long-term Memory
Tool Notes
```

这比当前 ContextBuilder 里简单的 `Identity + Memory + Skills` 更适合个人助理。

### 3. Daily Notes + Curated Memory

OpenClaw 常见 memory 层：

- `memory/YYYY-MM-DD.md`：每日 running context 和观察。
- `MEMORY.md`：人工或 agent 整理后的长期 durable memory。
- `MEMORY_PROPOSALS.md`：长期记忆候选的临时缓冲区，后台整理后归档清空，避免长期堆积。

可采纳经验：

- MyAgent 需要 working memory，不应该每条信息都直接进入长期 memory。
- `working` 层可以保存最近观察和候选记忆。
- `profile/project` 层保存长期、稳定、精炼内容。

这和 Memory v2 的三层设计一致：

```text
profile
project
working
```

### 4. Context 可见性

OpenClaw 强调 context 和 memory 不同：

- context 是当前发给模型的内容。
- memory 是磁盘上的长期状态。
- `/context`、`/status` 等命令让用户知道当前窗口里有什么。

可采纳经验：

- MyAgent 后续应让用户能 inspect context。
- Memory 召回不应该是黑箱。
- Trace 只能给开发者看；个人助理需要更用户友好的状态解释。

未来可以考虑：

```text
/context
/memory
/status
```

### 5. Skills 是可复用工作流

OpenClaw Skills 不是简单插件，而是让 agent 学会“什么时候、怎么用工具”的 Markdown 指南。

关键点：

- skill 是重复工作流的封装。
- skill 可以有全局层和 workspace 层。
- workspace skill 优先级更高。
- 第三方 skill 有安全风险，需要 review。

可采纳经验：

- MyAgent 的 Skills 不应该只停留在 system prompt 摘要。
- Skills 应成为个人助理的“长期能力手册”。
- 未来应支持：

```text
global skills
workspace skills
personal skills
```

- Skills 与 Memory 的边界：
  - Memory 记事实、偏好、状态。
  - Skills 记可复用流程和方法。

### 6. Tools / Skills / Plugins 分层

OpenClaw 区分：

- Tools：agent 实际调用的 typed functions。
- Skills：教 agent 什么时候、如何用工具。
- Plugins：打包工具、技能、通道、模型等能力。

可采纳经验：

- MyAgent 现在有 ToolRegistry、Skills、MCP，但缺少统一能力模型。
- 后续可以解释为：

```text
ToolRegistry = action surface
Skills = procedural guidance
MCP = external tool provider
Future Plugin = packaging layer
```

这能让 MyAgent 不只是 coding agent，而是可接入各种生活/工作工具的个人助理。

### 7. Channels 与 Routing

OpenClaw 的个人助理强在多通道：

- DM 和 group 分开。
- group 默认 allowlist + mention gating。
- direct message 可以走主 session。
- channel routing 是宿主层确定的，不让模型自由选择发到哪里。

可采纳经验：

- MyAgent 后续 QQ Channel 应作为 Channel 层，不改 AgentLoop。
- 群聊必须默认保守：白名单、require mention。
- 模型不应决定任意发消息到哪个 channel。
- session key 应区分：

```text
direct
group
thread/topic
```

当前可以先不做 IM，但设计要预留。

### 8. Heartbeat / Proactive Agent

OpenClaw 支持 heartbeat：

- 周期性运行 agent turn。
- 检查待办、日程、提醒、未完成任务。
- 没事时返回 `HEARTBEAT_OK` 并静默。
- 初期建议关闭或非常保守，避免打扰和误操作。

可采纳经验：

- 个人助理不能永远只被动响应。
- 但主动性必须晚于安全、工具权限和 memory 管理。
- MyAgent 后续可以设计：

```text
heartbeat disabled by default
manual wake first
active hours
only summarize, not execute risky actions
```

### 9. Safety First

OpenClaw personal assistant setup 强调：

- 不要开放给全世界。
- 通道要 allowlist。
- heartbeat 初期关闭。
- 工具权限从保守开始。
- group 默认 require mention。

可采纳经验：

- MyAgent 的个人助理方向必须先有安全边界。
- 如果后续加入写文件、exec、QQ、web、邮箱等能力，必须有：

```text
allowlist
confirmation
tool risk level
dry-run
trace/audit
```

否则个人助理越强，风险越大。

## MyAgent 应该怎么转向

### 当前问题

当前 MyAgent 的实现和文档容易给人感觉是：

```text
本地 CLI coding agent runtime
```

原因：

- 当前入口是 CLI。
- 当前工具只有读文件。
- 当前文档大量围绕代码模块和项目复盘。
- Memory 之前围绕当前项目状态讲得太多。

但用户期望的是：

```text
用户个人助理 Agent runtime
```

所以后续路线要调整。

### 新定位

MyAgent 应定位为：

```text
一个 local-first、可教学、可扩展的个人助理 Agent runtime。
```

它首先服务个人长期协作，而不是只服务代码任务。

### 核心模块重命名理解

当前模块可以重新解释：

```text
CLI Channel
  当前只是第一个入口，未来可接 QQ/IM。

MessageBus
  多通道消息统一入口。

AgentLoop
  个人助理的决策循环，不只是 coding loop。

ContextBuilder
  组装 identity、persona、user profile、memory、skills、tools。

Memory
  个人长期状态。

Skills
  个人助理可复用工作流。

MCP / ToolRegistry
  外部世界的行动接口。

Trace
  行为审计和调试。

SubAgent
  复杂任务的内部专业分工。
```

### 建议新增概念：Agent Workspace

MyAgent 后续应设计一个运行时 workspace：

```text
~/.myagent/workspace/
  AGENT.md
  PERSONA.md
  USER.md
  TOOLS.md
  MEMORY.md
  memory/
    YYYY-MM-DD.md
  skills/
```

第一版不必全部实现，但文档要确定方向。

与当前源码仓库不同：

```text
E:\ClaudeCode\openSource\MyAgent
  是 MyAgent 的源码项目。

~/.myagent/workspace
  是某个用户个人助理的长期状态。
```

### 建议的近期开发优先级

为了避免又变成 coding agent，后续不应该马上堆更多代码工具，而应该优先稳定个人助理的基础状态：

1. Memory v2：profile / project / working 三层。
2. ContextBuilder v2：注入 persona、user profile、memory sections。
3. Skills v2：从摘要注入升级为可激活工作流。
4. CLI `/memory` / `/status`：让用户能看到状态。
5. QQ Channel 设计：先私聊，群聊 require mention。

暂不优先：

- exec/write_file。
- 大量 coding 工具。
- 复杂 SubAgent。
- Web UI。

## 对 Memory 设计的影响

Memory 不应只保存：

```text
当前项目做到哪里了
```

它应该保存：

```text
用户长期偏好
用户正在做的长期目标
当前重要项目/生活/学习任务
协作中的稳定约束
最近观察和待整理事项
```

因此 Memory v2 的 scope 应是：

```text
profile
project
working
```

而不是：

```text
repo
code
task-only
```

## 参考链接

- OpenClaw Personal Assistant Setup: https://docs.openclaw.ai/clawd
- OpenClaw Agent Workspace: https://docs.openclaw.ai/concepts/agent-workspace
- OpenClaw Agent Runtime: https://docs.openclaw.ai/concepts/agent
- OpenClaw Memory Overview: https://docs.openclaw.ai/concepts/memory
- OpenClaw Context: https://docs.openclaw.ai/concepts/context
- OpenClaw Tools and Plugins: https://docs.openclaw.ai/tools
- OpenClaw Skills: https://docs.openclaw.ai/tools/skills
- OpenClaw Groups: https://docs.openclaw.ai/groups
- OpenClaw Channel Routing: https://docs.openclaw.ai/provider-routing
- OpenClaw Heartbeat: https://openclawlab.com/en/docs/gateway/heartbeat/
- SOUL.md Guide: https://clawdocs.org/guides/soul-md/
