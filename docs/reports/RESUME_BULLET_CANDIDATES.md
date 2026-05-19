# MyAgent 简历描述候选池

这份文档先把可写进简历的项目点都列出来。后续不要全部写进简历，而是从中筛选 3-5 条最强、最贴合目标岗位的 bullet。

## 项目一句话

候选版本：

```text
MyAgent：基于 Python 实现的 local-first 个人助理 Agent runtime，支持 OpenAI-compatible tool calling、上下文预算管理、文件/Shell/Web 工具、Markdown-backed memory、受控 SubAgent、MCP 工具接入、Trace 诊断以及 Feishu Gateway。
```

更简历化版本：

```text
实现 local-first 个人助理 Agent runtime，打通 CLI/Feishu 多渠道对话、OpenAI-compatible tool calling、上下文管理、工具权限审批、长期记忆和运行 Trace，支持真实 IM 场景下的工具调用与审批闭环。
```

更面试口语版：

```text
这个项目不是普通 Chatbot，而是一个轻量 Agent runtime。我重点做了上下文管理、工具调用、权限审批、Memory、SubAgent、MCP 和飞书渠道，让它能在本地和真实聊天渠道里跑起来。
```

## 推荐优先级

如果简历只能写 4 条，优先选：

1. Agent runtime / tool calling 主链路
2. ContextBuilder / conversation summary / token budget
3. ToolRegistry + 权限审批 + Shell/文件工具
4. Feishu Gateway / `/new` / 审批卡片 / 富文本

如果还能多写 1-2 条，再考虑：

5. Memory / Markdown-backed memory
6. SubAgent / MCP / Trace 中最贴岗位的一项

## 1. Agent Runtime / AgentLoop

### 简历 bullet 候选

```text
- 设计并实现轻量 Agent runtime 主循环，支持 OpenAI-compatible tool calling、多轮工具调用、tool result 回填和最大迭代保护，打通 user message -> context -> LLM -> tools -> final answer 的 ReAct 闭环。
```

更短版本：

```text
- 实现 AgentLoop ReAct 主链路，支持 OpenAI-compatible tool calling、工具结果回填、迭代上限保护和最终回复生成。
```

更强调工程边界：

```text
- 将 Agent 主循环、工具注册、上下文构建和渠道输入输出解耦，实现可测试、可扩展的 Agent runtime 架构。
```

### 支撑实现

- `myagent/agent/loop.py`
- `myagent/providers/base.py`
- `myagent/providers/openai_compatible.py`
- `myagent/tools/registry.py`
- `tests/test_agent_loop.py`
- `tests/test_llm_provider.py`

### 面试讲法

这条用来证明你不是只会调 API，而是理解 Agent runtime 的执行链路。重点讲：

- provider 可以返回 tool calls
- AgentLoop 执行 ToolRegistry
- tool result 作为 tool message 回填
- 再次请求模型生成 final answer
- 用 max iterations 避免死循环

### 注意不要夸大

不要写“实现多 Agent 自治调度平台”或“复杂 workflow engine”。当前是轻量 ReAct runtime，不是生产级图调度系统。

## 2. ContextBuilder / 上下文管理

### 简历 bullet 候选

```text
- 设计 ContextBuilder 上下文组装模块，引入 token budget、system section 分层、history 裁剪和 conversation summary，在长对话场景下控制 prompt 膨胀并保留近期细节。
```

更短版本：

```text
- 实现预算感知的上下文管理，支持 history 裁剪、conversation summary 和 system section 分层，降低长对话 prompt 膨胀。
```

更强调取舍：

```text
- 将 conversation summary 设计为 model-visible context view，而非长期 Memory，避免临时对话摘要污染长期记忆。
```

### 支撑实现

- `myagent/agent/context.py`
- `docs/modules/CONTEXT_BUILDER.md`
- `tests/test_context_builder.py`

### 面试讲法

这条是核心技术点。可以讲：

- Agent 不能无限塞 history
- system / history / memory / summary 需要分层
- summary 保留长对话连续性
- recent raw messages 保留细节
- summary 不写入 Memory，防止边界混乱

### 注意不要夸大

不要说“实现完整长期上下文压缩系统”。当前是预算控制 + summary + history trimming，不是复杂检索增强记忆系统。

## 3. ToolRegistry / 工具抽象

### 简历 bullet 候选

```text
- 抽象统一 ToolRegistry，基于 JSON Schema 暴露工具参数并执行参数校验，接入文件、Web、Shell、Memory、Skills、SubAgent、MCP 等工具能力。
```

更短版本：

```text
- 设计统一工具抽象和注册中心，支持工具 schema 暴露、参数校验、动态注册和 OpenAI-compatible tool calling 接入。
```

更强调扩展：

```text
- 通过 ToolRegistry 屏蔽内置工具与 MCP 外部工具差异，使 AgentLoop 仅依赖统一 tool name + arguments 执行接口。
```

### 支撑实现

- `myagent/tools/base.py`
- `myagent/tools/registry.py`
- `myagent/tools/__init__.py`
- `myagent/mcp/adapter.py`
- `tests/test_tool_registry.py`
- `tests/test_mcp_adapter.py`

### 面试讲法

重点讲工具不是散落在 AgentLoop 里的 if/else，而是统一抽象：

- 每个工具声明 name / description / parameters / execute
- Registry 负责注册、查找、参数校验和执行
- schema 能直接给模型
- MCP tool 也包装成同样接口

### 注意不要夸大

不要说“插件市场”或“完整插件生命周期”。当前是清晰的工具抽象和注册执行，不是完整插件平台。

## 4. 文件工具 / 路径边界 / 审批

### 简历 bullet 候选

```text
- 实现受控文件工具集，支持 list/read/write/edit/copy/move，并设计 workspace 内默认允许、workspace 外变更需审批的路径安全策略。
```

更短版本：

```text
- 实现文件读写与编辑工具，统一处理路径解析、工作区边界和外部文件变更审批。
```

更强调个人助理场景：

```text
- 支持个人助理常见文件任务，如读取项目文件、生成文档、复制/移动到桌面，同时通过 Channel 审批保护工作区外变更。
```

### 支撑实现

- `myagent/tools/filesystem.py`
- `tests/test_filesystem_tools.py`
- `docs/modules/TOOL_REGISTRY.md`

### 面试讲法

这条可以讲安全边界：

- 工作区内是项目开发范围
- 外部个人目录属于用户资产
- read-only 外部访问风险较低
- mutate 外部路径必须经过当前 Channel 审批

### 注意不要夸大

当前没有 delete tool，也没有复杂 ACL。可以说“路径安全策略”，不要说“完整沙箱”。

## 5. Shell Tool / Windows PowerShell / 风险控制

### 简历 bullet 候选

```text
- 实现跨平台 Shell command tool，支持 Windows PowerShell 语义、持久 working directory、输出编码兼容和命令风险审批，提升本地系统查询与自动化能力。
```

更短版本：

```text
- 接入受控 Shell 工具，支持 PowerShell 查询、工作目录持久化、输出截断和危险命令审批。
```

更强调真实问题：

```text
- 针对 Windows 真实使用场景修复 PowerShell 管道、编码和审批路由问题，使只读系统查询可直接执行，杀进程等高风险操作触发审批。
```

### 支撑实现

- `myagent/tools/shell.py`
- `tests/test_shell_tool.py`

### 面试讲法

可以讲一个真实例子：

```powershell
Get-Process | Measure-Object | Select-Object -ExpandProperty Count
```

这是只读查询，不应审批。

```powershell
taskkill /f /im PhoneExperienceHost.exe
```

这是杀进程，应该审批。

### 注意不要夸大

当前风险控制仍偏保守，还没有完整 `allow / confirm / deny` 分类。可以把它讲成“当前待打磨点”。

## 6. Feishu Gateway / 多渠道

### 简历 bullet 候选

```text
- 实现 Feishu Gateway，将 Agent 从本地 CLI 扩展到真实 IM 场景，支持 `/new` 新会话、富文本回复、工具审批卡片和当前 chat 路由。
```

更短版本：

```text
- 接入飞书长连接渠道，支持消息收发、上下文重置、审批卡片和 Markdown-ish 到飞书富文本渲染。
```

更强调用户体验：

```text
- 针对 IM 场景设计 `/new` 会话重置和 interactive card 审批流程，解决聊天渠道中上下文累积和高风险工具确认问题。
```

### 支撑实现

- `myagent/channels/feishu.py`
- `myagent/channels/manager.py`
- `myagent/approval.py`
- `myagent/cli/commands.py`
- `tests/test_channels_feishu.py`
- `tests/test_cli_channel.py`

### 面试讲法

这条很适合写简历，因为它证明项目不是只在命令行里自嗨：

- 飞书没有“新对话按钮”，所以做 `/new`
- Markdown 不能直接好看显示，所以做 `post` 富文本
- 危险工具要用户确认，所以做审批卡片
- 审批回到当前 chat，而不是固定 CLI

### 注意不要夸大

不要说“完整企业级飞书机器人平台”。当前是可用的 Feishu Gateway，不是全量飞书开放平台封装。

## 7. Memory / Markdown-backed Memory

### 简历 bullet 候选

```text
- 设计 Markdown-backed memory 机制，将可见记忆、候选记忆和事件归档分层存储，支持保守写入和定时 consolidation。
```

更短版本：

```text
- 实现 Markdown-backed memory，将长期稳定信息、候选记忆和事件归档分离，提升个人助理跨会话连续性。
```

更强调取舍：

```text
- 未直接引入向量库，而是优先打磨长期/短期记忆边界，用可读 Markdown 存储降低调试和解释成本。
```

### 支撑实现

- `myagent/memory/*`
- `myagent/tools/memory.py`
- `docs/modules/MEMORY.md`
- `tests/test_memory_tools.py`
- `tests/test_memory_consolidator.py`
- `tests/test_agent_memory.py`

### 面试讲法

讲重点：

- Memory 不是把所有对话都存起来
- 长期稳定事实、候选记忆、事件归档分开
- proposal 不长期堆积
- summary 不等于 memory

### 注意不要夸大

不要写“向量检索记忆系统”或“知识图谱”。当前亮点是边界和可解释性，不是检索规模。

## 8. Skills / 按需加载

### 简历 bullet 候选

```text
- 实现 Skills 按需加载机制，扫描本地技能说明并通过 `skill_get` 动态注入完整工作流知识，避免一次性加载造成上下文膨胀。
```

更短版本：

```text
- 设计 Skills v2，支持技能扫描、按需加载、active skill trace 和 SubAgent 技能上下文继承。
```

更强调上下文：

```text
- 将 Skills 设计为可复用工作流说明而非工具调用，按需加载 `SKILL.md` 以平衡能力复用和上下文预算。
```

### 支撑实现

- `myagent/skills.py`
- `myagent/tools/skills.py`
- `docs/modules/SKILLS.md`
- `tests/test_skills.py`
- `tests/test_skill_tools.py`

### 面试讲法

Skills 是 prompt/工作流知识，不是 API 工具。重点讲：

- 不把所有 skill 全塞上下文
- 模型需要时再 `skill_get`
- trace 记录加载情况
- SubAgent 可继承紧凑上下文

### 注意不要夸大

当前没有自动 SkillSelector，不要说“自动技能路由系统”。

## 9. SubAgent / 受控委托

### 简历 bullet 候选

```text
- 实现受控 SubAgent 委托机制，支持 researcher/reviewer/interviewer 等 profile 和工具 allowlist，在不开放写权限与递归委托的前提下处理局部分析任务。
```

更短版本：

```text
- 实现短生命周期 SubAgent，支持 profile 化 prompt、受限工具集合和父级 active skill context 继承。
```

更强调工程取舍：

```text
- 通过工具 allowlist、禁止写文件和禁止递归委托控制 SubAgent 复杂度，避免多 Agent 自治流程失控。
```

### 支撑实现

- `myagent/agent/subagent.py`
- `myagent/tools/subagent.py`
- `docs/modules/SUBAGENT.md`
- `tests/test_subagent.py`

### 面试讲法

这条可以展示你知道多 Agent 容易失控：

- 子 Agent 适合读和分析
- 主 Agent 保持最终控制权
- 不递归、不写文件
- profile 决定行为风格和工具范围

### 注意不要夸大

不要说“多 Agent 协作平台”。当前是受控委托，不是长期自治团队。

## 10. MCP / 外部工具接入

### 简历 bullet 候选

```text
- 接入 MCP stdio/HTTP 工具服务，将外部 tools 包装为统一 ToolRegistry 工具，并支持 server 前缀命名、include/exclude 过滤和启动期连接摘要。
```

更短版本：

```text
- 实现 MCP 工具接入层，支持工具发现、名称隔离、过滤配置和统一 Tool adapter。
```

更强调上下文控制：

```text
- 为 MCP tools 增加 include/exclude filtering，避免外部工具过多导致 tool schema 膨胀和误调用。
```

### 支撑实现

- `myagent/mcp/*`
- `myagent/mcp/registry.py`
- `myagent/mcp/adapter.py`
- `tests/test_mcp_*`
- `docs/modules/MCP.md`

### 面试讲法

重点讲：

- MCP server 暴露 tools
- MyAgent 用 adapter 包装为内部 Tool
- 名称前缀避免冲突
- filtering 控制暴露范围

### 注意不要夸大

当前主要接 tools，不是完整 MCP resources/prompts/sampling 平台。

## 11. Trace / 可观察性

### 简历 bullet 候选

```text
- 构建本地 JSONL Trace 体系，记录 context、tool call/result、memory、skills、subagent 和 startup 事件，并提供 CLI inspect 与 HTML report/viewer。
```

更短版本：

```text
- 实现 Agent 运行 Trace，支持 latest/show/context/report/viewer，提升上下文裁剪、工具调用和 Memory 写入的可调试性。
```

更强调取舍：

```text
- 采用 lightweight JSONL Trace 替代重型 OpenTelemetry，优先保证 local-first 项目的可读性、可测试性和面试可解释性。
```

### 支撑实现

- `myagent/tracing/*`
- `myagent/cli/commands.py`
- `docs/modules/TRACE.md`
- `tests/test_trace_store.py`
- `tests/test_agent_trace.py`

### 面试讲法

Trace 用来解释 Agent 为什么这样回答：

- 构建了什么上下文
- 调了哪些工具
- 工具返回什么
- Memory/Skill/SubAgent 是否发生

### 注意不要夸大

当前不是分布式 tracing，不要说“生产级可观测平台”。

## 12. Cron / Message / 主动触达

### 简历 bullet 候选

```text
- 实现 CronService 与 MessageTool，支持 every/at/once 定时任务、按创建 channel/chat_id 路由回复和主动消息发送能力。
```

更短版本：

```text
- 支持 Agent 主动触达能力，定时任务可路由回原始会话，并复用统一 Channel 消息发送接口。
```

更强调个人助理：

```text
- 为个人助理场景补充定时任务和主动消息能力，使 Agent 不仅能被动回答，也能在指定时间回到用户所在渠道。
```

### 支撑实现

- `myagent/cron/*`
- `myagent/tools/message.py`
- `tests/test_cron_*`
- `tests/test_message_bus.py`
- `tests/test_message_tool_suppress.py` 如果存在

### 面试讲法

重点讲：

- personal assistant 需要主动性
- 定时任务不绕过 Channel
- 任务创建时记录 channel/chat_id
- MessageTool 避免重复最终回复

### 注意不要夸大

当前不是完整 workflow scheduler，不要说“复杂任务编排平台”。

## 简历最终组合候选

### 组合 A：偏 Agent Runtime

```text
- 设计并实现 local-first Agent runtime，打通 OpenAI-compatible tool calling、ToolRegistry、ContextBuilder 和 Trace，形成 user message -> context -> LLM -> tools -> final answer 的 ReAct 闭环。
- 实现预算感知的上下文管理，支持 system section 分层、history 裁剪和 conversation summary，缓解长对话 prompt 膨胀并保留近期细节。
- 抽象统一 ToolRegistry，基于 JSON Schema 暴露工具参数并执行校验，接入文件、Web、Shell、Memory、SubAgent 和 MCP 外部工具。
- 构建本地 JSONL Trace 与 CLI/HTML inspect 能力，记录上下文组装、工具调用、Memory、Skills 和 SubAgent 事件，提升 Agent 调试效率。
```

### 组合 B：偏个人助理 / 真实使用

```text
- 实现 local-first 个人助理 Agent runtime，支持 CLI/Feishu 多渠道对话、工具调用、长期记忆、定时任务和主动消息发送。
- 接入 Feishu Gateway，支持 `/new` 会话重置、Markdown-ish 富文本回复、工具审批卡片和当前 chat 路由，完成真实 IM 场景 smoke test。
- 设计受控文件与 Shell 工具，支持项目文件读写、PowerShell 查询、工作目录持久化和危险操作审批，平衡本地自动化能力与安全边界。
- 设计 Markdown-backed memory，将长期稳定信息、候选记忆和事件归档分离，避免临时对话污染长期记忆。
```

### 组合 C：偏工程架构 / 可扩展性

```text
- 将 Agent runtime 拆分为 Channel、MessageBus、AgentLoop、ContextBuilder、ToolRegistry、Memory、SubAgent、MCP 和 Trace 等模块，保持核心链路可测试、可替换。
- 通过 ToolRegistry 和 MCP adapter 统一内置工具与外部工具接入，支持工具 schema 暴露、参数校验、名称隔离和 include/exclude 过滤。
- 设计 Channel-owned approval workflow，将工具审批请求路由到当前 CLI/Feishu 会话，避免工具层直接耦合具体交互方式。
- 实现受控 SubAgent 委托，基于 profile 和工具 allowlist 限制子 Agent 能力，避免递归委托和写文件带来的复杂度失控。
```

## 最推荐写进简历的 5 条

如果只能选最有含金量的，我建议优先：

```text
- 设计并实现 local-first Agent runtime，打通 OpenAI-compatible tool calling、ToolRegistry、ContextBuilder 和 Trace，形成 user message -> context -> LLM -> tools -> final answer 的 ReAct 闭环。
- 实现预算感知的上下文管理，支持 system section 分层、history 裁剪和 conversation summary，缓解长对话 prompt 膨胀并保留近期细节。
- 抽象统一 ToolRegistry，基于 JSON Schema 暴露工具参数并执行校验，接入文件、Web、Shell、Memory、SubAgent 和 MCP 外部工具。
- 接入 Feishu Gateway，支持 `/new` 会话重置、Markdown-ish 富文本回复、工具审批卡片和当前 chat 路由，完成真实 IM 场景 smoke test。
- 设计 Markdown-backed memory 与受控 SubAgent 机制，将可见/候选/归档记忆分层，并通过 profile + tool allowlist 控制子 Agent 任务边界。
```

## 下一步筛选方式

后续筛选时按岗位调整：

- 如果投 Agent / LLM 应用开发：优先 AgentLoop、ContextBuilder、ToolRegistry、Feishu Gateway、Memory。
- 如果投后端工程：优先模块拆分、ToolRegistry、MCP、Trace、Cron/Message。
- 如果投平台 / 基础设施：优先 ToolRegistry、MCP、Trace、权限审批、Context budget。
- 如果投偏产品型 AI 应用：优先 Feishu Gateway、Memory、Cron/Message、工具审批、真实 smoke test。

