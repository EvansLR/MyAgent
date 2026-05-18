# MyAgent 面试模块亮点

这份文档用于面试和项目复盘。它不记录所有实现细节，而是帮助把每个模块讲成一个清楚的问题、设计取舍和可追问回答。

## 总体讲法

MyAgent 可以概括为：

```text
一个 local-first 的个人助理 Agent runtime。
它把 Channel、AgentLoop、Context、Memory、Tools、SubAgent、MCP、Trace 和 Cron 拆成清楚的模块，
优先保证能真实运行、能解释、能测试，而不是一开始就引入重型平台架构。
```

面试时不要把它讲成“我做了一堆功能”。更好的讲法是：

> 我做的是一个轻量 Agent runtime。核心问题不是单次 LLM 调用，而是怎么在真实对话渠道里管理上下文、调用工具、处理权限、保留记忆、做可观察性，并且保持模块边界可解释。

## 一页亮点

| 模块 | 一句话亮点 | 关键取舍 |
| --- | --- | --- |
| AgentLoop | 跑通 ReAct/tool calling 主循环 | 保持同步短循环，不急着做图调度 |
| ContextBuilder | 预算化组装 system/history/summary/memory | summary 只做上下文视图，不改原始 history |
| ToolRegistry | 用统一 Tool 抽象接文件、Web、Shell、MCP | 工具风险先保守处理，后续再分层 |
| Feishu Gateway | 把 Agent 从 CLI 推到真实聊天渠道 | Channel 只管输入输出和审批呈现 |
| Memory | Markdown-backed memory，分长期、候选、daily | 不做向量库和人工 review UI |
| Skills | 按需加载的工作流知识 | 不做自动 SkillSelector |
| SubAgent | 受控短生命周期委托 | 子 Agent 不写文件、不递归 |
| MCP | 外部工具接入和过滤 | 只接 tools，resources/prompts 后置 |
| Trace | 本地 JSONL inspect/report/viewer | 先可读可调试，不上 OpenTelemetry |
| Cron/Message | 支持主动触达和定时任务 | 保持轻量，不做复杂 workflow engine |

## 1. AgentLoop

### 模块定位

AgentLoop 是主 Agent 的运行核心，负责把一轮用户消息变成：

```text
context -> provider call -> tool calls -> tool results -> final answer
```

### 核心亮点

- 支持 OpenAI-compatible tool calling。
- 能把工具结果作为 `role=tool` 消息回填给 provider。
- 有最大工具迭代次数，避免模型反复调用工具造成死循环。
- 工具执行、最终回答、trace、memory extraction 都由主循环串起来。
- 不把具体工具逻辑写死在 AgentLoop 里，而是委托给 ToolRegistry。

### 关键取舍

- 没有直接上 LangGraph / workflow graph。
- 保持“一个用户 turn 内的短循环”更容易解释和测试。
- 复杂多步骤任务先靠工具和 SubAgent，不急着做持久任务图。

### 面试怎么讲

> AgentLoop 是这个项目的运行心脏。我没有把 Agent 写成一次 prompt 调用，而是实现了一个轻量 ReAct 循环：模型可以返回 tool calls，系统执行工具，把结果回填，再让模型生成最终答复。同时我设置了迭代上限和 trace，保证它能调试、不会无限循环。

### 可能追问

**为什么不用 LangGraph？**

当前目标是学习和面试可讲的 runtime。LangGraph 适合复杂工作流，但会把核心机制藏到框架里。这个项目先把 AgentLoop、工具调用、上下文和 trace 自己实现清楚，后续如果任务图复杂度真的上来，再接 graph runtime 更合理。

**如何避免工具死循环？**

用最大工具迭代次数限制，并在 trace 中记录工具调用数量、重复调用和停止原因。当前更偏“可控 demo/runtime”，不是无限自治 Agent。

## 2. ContextBuilder

### 模块定位

ContextBuilder 负责把模型可见上下文组装出来，包括 system sections、history、conversation summary、memory 和运行环境信息。

### 核心亮点

- 有 token budget 意识，而不是无限塞历史。
- system sections 支持 tier / retention policy。
- history 先按消息数量，再按 token budget 裁剪。
- conversation summary 已落地，用 `running summary + recent raw messages` 兼顾连续性和细节。
- 大文件不靠一次塞全文，而是通过 `read_file offset/limit` 分页。

### 关键取舍

- Summary 是 model-visible context view，不写入 Memory。
- 不修改原始 `_history`，避免“摘要污染历史”。
- 当前 turn 内 tool result 不做复杂压缩，避免破坏 tool call/result 消息结构。

### 面试怎么讲

> ContextBuilder 解决的是长对话下“给模型看什么”的问题。我把上下文分成稳定 system、近期 history、conversation summary、memory 等不同来源，并做预算控制。summary 只是给模型看的上下文视图，不会覆盖原始历史，也不会混进长期记忆。

### 可能追问

**为什么 summary 不写进 Memory？**

Summary 是为了当前对话连续性，Memory 是跨会话长期事实。把二者混在一起会让临时任务和长期偏好混淆，所以我刻意分开。

**长文件总结怎么看全？**

不靠工具结果压缩成前几千字，而是让 `read_file` 支持 offset/limit 分页。模型需要继续读时可以请求下一段，避免一次性把大文件塞满上下文。

## 3. ToolRegistry

### 模块定位

ToolRegistry 是所有工具的统一入口，负责注册、暴露 schema、参数校验和执行。

### 核心亮点

- 每个工具有统一的 `name / description / parameters / execute` 接口。
- 工具 schema 可直接用于 OpenAI-compatible tool calling。
- 默认工具覆盖文件、Web、Shell、Memory、Skills、SubAgent、Message。
- 文件工具复用统一路径和审批策略。
- MCP tools 可以被包装成普通 Tool 接入同一套 registry。

### 关键取舍

- 工具层保持简单显式，不做复杂插件生命周期。
- 文件操作的边界优先清楚：工作区内允许，工作区外变更审批。
- Shell 权限目前保守，后续再做 `allow / confirm / deny` 风险分层。

### 面试怎么讲

> ToolRegistry 的价值是让 AgentLoop 不关心具体工具实现。模型只返回工具名和参数，Registry 负责校验和执行。这样文件工具、Web 工具、Shell 工具、MCP 工具都能用统一接口进入 Agent。

### 可能追问

**为什么不用模型直接执行任意 shell？**

Shell 风险太高，尤其在个人电脑上。项目把 shell 放进受控工具里，用白名单/危险命令/审批机制先兜住风险，后续再做更细的风险分类。

**为什么工作区内写文件不审批？**

这个项目本身是 coding/agent runtime，用户已经授权在项目工作区开发。工作区内写文件是核心能力；真正需要审批的是工作区外个人文件和系统级操作。

## 4. Feishu Gateway

### 模块定位

Feishu Gateway 把 MyAgent 从本地 CLI 扩展到真实聊天渠道。

### 核心亮点

- Gateway 模式运行 ChannelManager + AgentLoop + CronService。
- 支持 `/new`，解决 IM 场景没有“新建会话按钮”的问题。
- 支持 Feishu interactive card 审批。
- 普通回复支持 Markdown-ish 到 Feishu `post` 富文本。
- 审批请求会路由回当前 chat，而不是固定回 CLI。

### 关键取舍

- Channel 只负责输入输出、消息渲染、审批呈现。
- AgentLoop 不写死飞书逻辑。
- Feishu 渲染只支持常见 Markdown 子集，不追求完整 Markdown 引擎。

### 面试怎么讲

> Feishu Gateway 是这个项目从 demo 走向真实使用的重要一步。CLI 里可以关掉重开对话，但飞书聊天没有天然的新会话按钮，所以我实现了 `/new`。另外危险工具操作会变成飞书审批卡片，用户在当前 chat 里点允许或拒绝。

### 可能追问

**为什么审批放在 Channel 层？**

审批是用户交互，不应该由工具直接读终端输入。工具只声明“这个操作需要确认”，Channel 负责用当前渠道合适的方式展示，比如 CLI prompt 或 Feishu card。

**为什么不直接发 Markdown？**

飞书对 Markdown 支持有限，直接发会显示效果差。项目把常见标题、列表、粗体、链接、代码块转成 Feishu `post` 富文本，保证报告和总结类回复可读。

## 5. Memory

### 模块定位

Memory 负责跨对话保留对未来有用的信息，让 Agent 更像个人助理。

### 核心亮点

- 从旧 JSONL recall 转向 Markdown-backed workspace。
- 分成稳定长期记忆、候选记忆、daily 临时上下文。
- `memory_propose_long_term` 默认先写 proposal。
- 用户明确要求“记住”的内容才直接进入长期记忆。
- 定时 consolidation 可整理候选，避免 proposal 无限堆积。

### 关键取舍

- 不上向量库、SQLite、knowledge graph。
- 不做人工 memory review UI。
- 不新增 `MemoryCurator`。
- 写入质量暂不专项观察，等真实噪声出现再调。

### 面试怎么讲

> Memory 这块我没有一开始上向量数据库，因为当前问题不是语义检索规模，而是个人助理到底该记什么。我先用 Markdown 文件把长期记忆、候选记忆、daily 上下文分开，让它可读、可人工检查、也方便面试解释。

### 可能追问

**为什么不用向量库？**

向量库解决的是大规模语义召回，但当前阶段更重要的是记忆边界和写入质量。Markdown-backed memory 更透明，也更符合 local-first 和学习型项目定位。

**Memory 和 Summary 有什么区别？**

Summary 服务当前对话连续性，Memory 服务跨会话长期偏好和事实。Summary 可以频繁更新，Memory 必须少而准。

## 6. Skills

### 模块定位

Skills 是按需加载的工作流知识，用来保存可复用的任务说明和操作规范。

### 核心亮点

- 扫描本地 skill 定义。
- `skill_get(skill_id)` 按需加载完整 `SKILL.md`。
- 加载成功记录 `skill_loaded` trace。
- turn-scoped active skills 会记录 `active_skill_set`。
- SubAgent 可以继承紧凑的 active skill context。

### 关键取舍

- 不做自动 SkillSelector。
- 不做 persistent active skills。
- 不让 skill 直接定义工具权限。

### 面试怎么讲

> Skills 不是工具，它更像可复用的工作流说明。模型不需要每次都把所有 skill 全量塞进上下文，而是先知道有哪些，需要时再通过 `skill_get` 加载全文，这样能控制上下文大小。

### 可能追问

**为什么不自动选择 skill？**

自动 SkillSelector 会引入另一层模型判断和误选问题。当前阶段先做显式按需加载，更容易验证效果，也能避免上下文膨胀。

## 7. SubAgent

### 模块定位

SubAgent 用于把局部任务委托给受控的短生命周期 Agent。

### 核心亮点

- 内置 `researcher`、`reviewer`、`interviewer` profile。
- 支持 profile-specific child tool allowlist。
- 子 Agent 可读文件、用只读 web 工具。
- 子 Agent 可继承父 turn 的紧凑 skill context。
- 主 Agent 保持控制权，子 Agent 返回结果后结束。

### 关键取舍

- 同步执行，不做后台长期任务。
- 不允许子 Agent 写文件。
- 不允许递归委托。
- 不继承任意 MCP 工具。

### 面试怎么讲

> SubAgent 这块我没有做成完全自治的多 Agent 系统，而是做成受控委托。主 Agent 可以把局部研究、审查、面试模拟交给子 Agent，但子 Agent 工具权限更小，生命周期更短，避免复杂度失控。

### 可能追问

**为什么子 Agent 不写文件？**

写文件会带来合并冲突、权限和责任归属问题。当前 SubAgent 更适合读、分析、总结，把最终改动权留给主 Agent。

**为什么不递归委托？**

递归委托很容易让控制流和调试复杂化。当前项目优先可解释和稳定，所以只做一层受控委托。

## 8. MCP

### 模块定位

MCP 让 MyAgent 能接入外部工具 server，并把外部 tools 包装进 ToolRegistry。

### 核心亮点

- 支持 stdio / HTTP / SSE 风格 MCP client。
- 能发现 tools 并注册成统一 Tool。
- 工具名加 server 前缀，避免冲突。
- 支持 include/exclude tool filtering。
- 启动期记录 connection summary。

### 关键取舍

- 当前只接 tools，不急着支持 resources/prompts/sampling。
- 通过 filtering 避免把过多外部工具暴露给模型。
- MCP tool result 先统一压成文本，保持 ToolRegistry 简单。

### 面试怎么讲

> MCP 的价值是把外部工具生态接进来，但我没有让它破坏内部工具抽象。每个 MCP tool 都会被 adapter 包装成统一 Tool，AgentLoop 仍然只认识 ToolRegistry。

### 可能追问

**为什么要做 include/exclude？**

MCP server 可能暴露很多工具。全部塞给模型会增加上下文成本和误调用概率，所以配置层必须能过滤。

## 9. Trace

### 模块定位

Trace 用来记录 Agent 运行过程，帮助调试上下文、工具调用、memory、skills 和 subagent。

### 核心亮点

- JSONL 本地 trace。
- CLI inspect 命令：latest/show/context。
- HTML report/viewer。
- 记录 tool_call、tool_result、context_built、memory、skill、subagent 等事件。
- startup trace 可记录 MCP 连接摘要。

### 关键取舍

- 不上 OpenTelemetry。
- 不记录完整 messages，避免隐私和体积问题。
- 当前用户不想做可观察性专项清理，所以后续按真实问题补。

### 面试怎么讲

> Trace 解决的是 Agent 不透明的问题。工具调用、上下文裁剪、summary 更新、memory 写入如果看不到，就很难调。我先用 JSONL 做本地 trace，足够可读、可测试，也符合 local-first。

### 可能追问

**为什么不用 OpenTelemetry？**

OpenTelemetry 更适合生产分布式系统。MyAgent 当前是本地学习和演示项目，JSONL 更轻、更直接，能把 Agent 内部事件讲清楚。

## 10. Cron / Message

### 模块定位

CronService 和 MessageTool 支持 Agent 主动触达用户，而不只是被动回复。

### 核心亮点

- CronService 支持 `every / at / once`。
- 用户 cron 会路由回创建时的 channel/chat_id。
- 系统 cron 可用于 memory consolidation。
- MessageTool 支持显式发送消息和文件。
- MessageTool 会抑制重复最终回复，避免用户收到两份内容。

### 关键取舍

- 不做复杂 workflow engine。
- 定时任务先轻量落地。
- 主动消息仍走 Channel 抽象，不写死具体 IM 平台。

### 面试怎么讲

> Cron 和 Message 让 Agent 有主动性。比如定时整理 memory 或按计划提醒用户，都不应该绕过 Channel，而应该回到创建任务的 chat。这样 CLI、Feishu 或后续渠道都可以复用。

### 可能追问

**为什么不做完整工作流系统？**

当前目标是 personal assistant runtime 的最小可解释闭环。定时任务和主动消息已经能覆盖很多个人助理场景，复杂工作流可以作为后续扩展。

## 演示路径

面试演示建议走稳定路径，不要现场展示未打磨功能。

### CLI 演示

```text
python -m myagent
```

可以演示：

- 读取项目文件并总结。
- 调用工具查看目录。
- 查看 trace latest/context。

### Feishu 演示

```text
python -m myagent gateway
```

可以演示：

- `/new` 切新上下文。
- 让 Agent 用标题和列表总结项目。
- 查看当前进程数量，证明只读 shell 查询不审批。
- 触发一个需要审批的命令，展示 Feishu card。

### Trace 演示

```text
python -m myagent trace latest
python -m myagent trace context
python -m myagent trace report
```

可以演示：

- 上一轮用了哪些工具。
- 上下文组装情况。
- 是否发生 summary / memory / skill / subagent 事件。

## 当前不继续开的方向

这些方向不是没价值，而是当前不该继续横向扩张：

- workflow graph runtime
- 向量库 / SQLite / knowledge graph memory
- 自动 SkillSelector
- persistent active skills
- recursive subagent delegation
- 子 Agent 写文件
- 新 IM Channel 大规模接入
- 完整 Markdown 渲染引擎

统一回答口径：

> 当前项目已经有足够完整的 Agent runtime 主链路。后续重点不是堆更多方向，而是围绕真实使用反馈打磨体验，比如工具权限分层、Feishu 渲染细节、Memory 写入质量和面试材料表达。

## 最容易被问到的 8 个问题

### 1. 这个项目和普通 Chatbot 有什么区别？

普通 Chatbot 主要是一次 prompt 到一次回复。MyAgent 是一个 runtime：它有 Channel、Context、ToolRegistry、Memory、SubAgent、MCP、Trace 和 Cron，能管理多轮上下文、调用工具、处理审批、保留记忆并主动触达。

### 2. 为什么强调 local-first？

因为个人助理会接触本地文件、配置、记忆和工具。local-first 让数据更可控，也更适合学习和演示。云端化、分布式任务队列、远程存储都可以后续扩展，不是第一阶段核心。

### 3. 最大的技术难点是什么？

不是某一个算法，而是边界设计：上下文和记忆怎么分、工具权限怎么控、Channel 和 AgentLoop 怎么解耦、SubAgent 怎么不失控、Trace 怎么让运行过程可解释。

### 4. 为什么不用现成 Agent 框架？

项目目标是理解和展示 Agent runtime 的核心机制。自己实现轻量版本能把上下文、工具、审批、trace 的边界讲清楚。后续生产化时可以迁移到成熟框架，但现在不让框架掩盖设计能力。

### 5. 现在最需要打磨的地方是什么？

工具权限策略。当前审批偏保守，功能可用但体验会被打断。后续应该做 `allow / confirm / deny` 风险分层，把只读查询和真正危险操作区分得更细。

### 6. Memory 为什么没有做得很复杂？

Memory 的关键不是存储技术，而是写入质量和长期/短期边界。当前用 Markdown-backed memory 保持透明可检查，先把稳定长期记忆、候选记忆、daily 上下文分清楚。

### 7. Feishu Gateway 的价值是什么？

它证明这个 Agent 不只是 CLI demo，而能进入真实聊天渠道。`/new`、富文本、审批卡片这些都是 IM 场景里的实际问题。

### 8. 如果继续做生产化，会先做什么？

优先做工具权限风险分层、配置化允许规则、Feishu 渲染补强、Memory 写入质量评估和更稳定的运行诊断。不会优先上复杂图调度或向量库。

