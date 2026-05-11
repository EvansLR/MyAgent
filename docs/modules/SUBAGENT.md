# SubAgent 设计与二期调研记录

## 职责

SubAgent 用来把一个复杂任务拆给更专门、更小上下文的 Agent 去完成。

在 MyAgent 里，它不是第一阶段必须做复杂的多 Agent 平台，而是作为后续能力扩展：

- 主 Agent 继续负责和用户对话、理解目标、整合最终答案。
- 子 Agent 负责一个明确的小任务，例如浏览某个目录、阅读一组文档、检查某类代码问题、准备某个面试专题。
- 子 Agent 完成后只返回结果摘要、证据和必要的结构化信息，不直接接管用户会话。

## 为什么需要它

当前 MyAgent 已经有工具调用、Skills、MCP、Memory 和 Trace。下一步如果继续扩大能力，单个 Agent 会遇到几个问题：

- 上下文越来越长，模型容易被无关信息干扰。
- 所有任务都由一个 Agent 决策，职责会变得不清晰。
- 浏览文件、总结文档、代码审查、面试陪练等任务的提示词策略不同，混在一起不好维护。
- 面试讲解时，多 Agent 架构是一个很有价值的设计点，可以体现系统拆分、任务编排和可观测性。

SubAgent 的价值不在于“更炫”，而在于把复杂任务拆成可解释、可追踪、可限制的小执行单元。

## 常见架构调研

### OpenAI Agents SDK

OpenAI 官方 Agents SDK 里常见两种组合方式：

1. Manager / agents as tools

主 Agent 仍然掌握对话控制权，把专门 Agent 暴露成工具。模型需要某类专业能力时，调用对应的 agent tool，拿到结果后由主 Agent 统一总结。

这个模式适合 MyAgent 第二版优先参考，因为它和当前 ToolRegistry / tool calling 机制最接近。

2. Handoffs

主 Agent 判断用户请求属于某个专业领域后，把整个对话交接给另一个 Agent。OpenAI 文档里 handoff 会被表示成工具，例如 `transfer_to_refund_agent` 这样的工具名。接收方 Agent 可以看到交接后的上下文，并继续完成对话。

这个模式更适合客服、业务分流、多角色助手，不适合 MyAgent 现在的第一版目标。MyAgent 暂时不需要让子 Agent 直接接管用户会话。

值得记录的 OpenAI 设计点：

- 子 Agent 可以有独立 instructions。
- handoff/agent tool 会有名字和描述，让模型自己决定是否调用。
- handoff 可以带结构化输入，例如 reason、priority、summary。
- handoff 可以通过 input filter 控制传给子 Agent 的历史内容。
- 官方强调 tracing / observability，用来观察 Agent 执行过程。

参考资料：

- https://openai.github.io/openai-agents-python/agents/
- https://openai.github.io/openai-agents-python/handoffs/
- https://openai.github.io/openai-agents-js/guides/agents/
- https://openai.github.io/openai-agents-js/guides/handoffs/
- https://platform.openai.com/docs/guides/agents-sdk/

### LangGraph Supervisor

LangGraph 的 supervisor 思路是：有一个中心 supervisor 负责调度多个 specialized agents。每个子 Agent 可以有不同工具和提示词，supervisor 决定下一步交给谁。

价值：

- 流程清楚，适合画图和面试讲解。
- 可以和状态机、checkpoint、resume 结合。
- 适合复杂工作流，例如“先检索，再分析，再生成，再审查”。

代价：

- 工程复杂度比 MyAgent 当前阶段高。
- 需要更明确的 state graph 设计。
- 如果现在就做，容易偏离“先跑起来、能讲清楚”的目标。

二期可以借鉴它的“中心调度 + 状态记录”思想，但不急着引入完整图执行框架。

### LangGraph Swarm

Swarm 更强调去中心化，多个 Agent 之间可以相互交接控制权。

价值：

- 适合开放式任务探索。
- 每个 Agent 更像一个自治角色。

代价：

- 调试难度更高。
- 任务边界不稳定。
- 不适合 MyAgent 当前这种学习型、面试型项目。

MyAgent 二期暂时不推荐采用 swarm 作为主架构，只把它作为扩展方向记录。

### AutoGen

AutoGen 经典思路是多 Agent 对话，例如 assistant、user proxy、critic、planner 等角色通过消息轮流协作。

价值：

- 很适合展示多角色协作。
- 对“规划-执行-审查”这类流程表达直观。
- 可以做代码生成、审查、讨论型任务。

代价：

- 容易产生多轮无效对话。
- token 成本高。
- 控制终止条件和结果质量需要额外机制。

MyAgent 可以在二期借鉴“critic/reviewer 子 Agent”，但不建议把主流程改成多 Agent 群聊。

### CrewAI

CrewAI 强调 role、goal、task、process。它把 Agent 更产品化地组织成一个 crew，每个 Agent 有角色，每个 Task 有目标和产出。

价值：

- 很适合教学和面试表达。
- 角色、任务、产出物边界清楚。
- 可以自然支持顺序执行、层级执行。

代价：

- 对 MyAgent 来说抽象稍重。
- 当前项目不需要完整 crew/task DSL。

二期可以借鉴它的 `AgentProfile` 和 `TaskSpec` 概念，让 SubAgent 配置更清楚。

### Claude Code Subagents

Claude Code 的 SubAgent 更偏向工程任务代理：为特定任务配置独立上下文、专门系统提示词、可用工具范围。

价值：

- 非常适合 MyAgent 的代码/文档/面试场景。
- 独立上下文可以减少主 Agent 被细节污染。
- 工具权限可以按子 Agent 类型限制。

代价：

- 如果要做后台并发、任务恢复、结果合并，会增加复杂度。

MyAgent 二期可以重点学习这个方向：不同类型子 Agent 拥有不同 prompt 和工具策略。

## 二期值得改的点

### 1. 采用 Manager / delegate_task 作为第一版 SubAgent

MyAgent 不先做 handoff，也不做 swarm。先做一个同步工具：

```text
delegate_task(task, agent_type, context)
```

主 Agent 调用这个工具，工具内部创建一个子 Agent 执行任务，然后把结果返回给主 Agent。

推荐原因：

- 和当前 ToolRegistry 最兼容。
- 用户体验稳定，最终回答仍由主 Agent 控制。
- 实现和调试成本低。
- 面试时容易讲清楚。

### 2. 子 Agent 使用独立上下文

子 Agent 不应该直接继承主会话的全部历史。它应该只拿到：

- 任务说明
- 必要背景
- 可用工具说明
- 少量相关 memory
- 主 Agent 显式传入的 context

这对应 OpenAI handoff 里的 input filter 思想，但 MyAgent 可以先做轻量版本。

### 3. 增加 SubAgentProfile

可以定义几类轻量 profile：

- `researcher`：负责浏览目录、阅读文件、整理事实。
- `reviewer`：负责检查代码风险、测试缺口、文档问题。
- `interviewer`：负责面试题拆解、追问、答案结构化。

每个 profile 包含：

- name
- description
- system prompt
- allowed tools
- max iterations

### 4. 工具权限要可控

第一版最初的 SubAgent 只给本地只读工具：

- `list_dir`
- `read_file`

后续再考虑是否允许 MCP 工具、写文件工具、shell 工具。

这样做的原因是：子 Agent 是被主 Agent 委托出去的，权限越大越难解释和调试。

### 5. 防止递归委托

第一版应该禁止子 Agent 再调用 `delegate_task`。

也就是：

```text
Main Agent -> SubAgent
```

不允许：

```text
Main Agent -> SubAgent -> SubAgent
```

后续如果要支持嵌套，需要增加 max depth、trace tree、取消机制和更严格的预算控制。

### 6. Trace 需要记录子任务

SubAgent 一定要接入 Trace，否则不好调试。

建议新增事件：

- `subagent_start`
- `subagent_tool_call`
- `subagent_tool_result`
- `subagent_result`
- `subagent_error`

二期可以先只记录 start/result/error，后续再记录完整子 Agent 内部工具调用。

### 7. CLI 状态展示

当前 CLI 已经能展示工具调用状态。SubAgent 后续可以展示：

```text
正在委托子任务：researcher
正在调用工具：read_file
```

这样用户可以看见系统确实发生了委托，而不是黑盒等待。

### 8. 和 Skills 机制联动

当前 Skills 是把 skill 摘要注入 system prompt，模型根据描述自行决定是否读取。

二期可以升级为：

- 主 Agent 根据任务选择合适的 skill。
- 子 Agent 根据 profile 自动附加相关 skill。
- skill 不只是“说明文档”，还可以作为子 Agent 的任务模板。

例如：

- `interview-prep` skill 可以绑定 `interviewer` profile。
- `code-review` skill 可以绑定 `reviewer` profile。

### 9. 和 Memory 机制联动

当前 Memory 还比较简单，后续需要升级。

SubAgent 二期可以做两件事：

- 子 Agent 可以读取经过筛选的 memory。
- 子 Agent 产生的重要结论由主 Agent 决定是否写入 memory。

不要让子 Agent 自动大量写 memory，否则记忆会很快变脏。

### 10. 配置化

SubAgent 二期应该可以通过 `myagent.json` 配置：

```json
{
  "subagents": {
    "enabled": true,
    "maxDepth": 1,
    "profiles": {
      "researcher": {
        "model": "same-as-main",
        "tools": ["list_dir", "read_file"],
        "maxIterations": 4
      }
    }
  }
}
```

第一版实现时可以先内置默认 profile，配置化作为第二步。

## MyAgent 推荐路线

### 二期第一步：文档与最小设计

先完成 SubAgent 模块设计文档，明确：

- 为什么要做
- 不做什么
- 输入输出
- profile 怎么定义
- trace 怎么记录
- 如何防止递归

### 二期第二步：实现同步 delegate_task

实现一个普通工具：

```text
delegate_task
```

它内部创建子 Agent，执行任务，返回文本结果。

### 二期第三步：补 Trace 和 CLI 状态

让用户能看到：

- 什么时候开始子任务
- 用了哪个 profile
- 最终子任务结果是什么

### 二期第四步：和 Skills/Memory 做轻量联动

不是做复杂 RAG，而是让 profile 能带上相关 skill 摘要，让主 Agent 控制 memory 写入。

## 暂不实现

第一版 SubAgent 暂不做：

- 后台并发任务
- swarm
- 多 Agent 群聊
- 子 Agent 直接接管用户会话
- 子 Agent 写文件
- 子 Agent 执行 shell
- 嵌套子 Agent
- 完整 checkpoint/resume
- 复杂任务队列

这些可以作为面试里的后续扩展方向。

## 面试表达

可以这样讲：

> MyAgent 第二版准备引入 SubAgent，但不会一开始做复杂的多 Agent 群聊。我会先采用类似 OpenAI agents-as-tools 的 manager 模式：主 Agent 负责对话和最终决策，把 researcher、reviewer、interviewer 这类专门 Agent 暴露成 `delegate_task` 能力。子 Agent 使用独立上下文和受限工具集，完成任务后返回结构化结果。这样既能控制复杂度，也能保留可观测性和权限边界。后续如果业务需要，再考虑 handoff、状态图、并发任务队列和嵌套委托。

## 第一版实现记录

本次实现的是 SubAgent 的最小可运行版本，不是完整多 Agent 平台。

核心能力：

- 主 Agent 默认拥有 `delegate_task` 工具。
- `delegate_task` 会创建一个临时 SubAgentRunner。
- 子 Agent 使用独立 system prompt 和独立 user task。
- 子 Agent 只能使用只读工具：`list_dir`、`read_file`。
- 子 Agent 不会看到 `delegate_task`，因此不能递归委托。
- 子 Agent 执行完后，把结果作为工具结果返回给主 Agent。
- 最终回答仍由主 Agent 生成。

### 新增文件

```text
myagent/agent/subagent.py
tests/test_subagent.py
```

### 修改文件

```text
myagent/agent/loop.py
myagent/agent/__init__.py
```

### 关键类

#### SubAgentProfile

`SubAgentProfile` 表示一种子 Agent 角色。

第一版内置了三种 profile：

- `researcher`：负责读文件、整理事实。
- `reviewer`：负责检查风险、测试缺口、文档问题。
- `interviewer`：负责生成面试导向解释。

profile 当前是代码内置的，后续可以迁移到 `myagent.json` 配置。

#### SubAgentRunner

`SubAgentRunner` 负责真正执行子任务。

它的输入是：

- `task`
- `agent_type`
- `context`

它的运行方式和主 AgentLoop 类似，但更小：

```text
build subagent messages
  -> ask provider
  -> maybe call read-only tool
  -> append tool result
  -> ask provider again
  -> return final subagent answer
```

它没有 MessageBus，也不直接和用户对话。

#### DelegateTaskTool

`DelegateTaskTool` 是主 Agent 看到的工具。

它的 schema 是：

```text
delegate_task(task, agent_type, context)
```

当模型认为某个任务适合委托时，会调用这个工具。工具内部创建只读子工具表，然后运行 `SubAgentRunner`。

### 和 AgentLoop 的关系

`AgentLoop` 初始化时会把 `DelegateTaskTool` 注册进主 ToolRegistry：

```text
ToolRegistry
  -> list_dir
  -> read_file
  -> delegate_task
```

主 Agent 可以看到 `delegate_task`。

子 Agent 只能看到：

```text
SubAgent ToolRegistry
  -> list_dir
  -> read_file
```

这个设计保证了第一版不会出现递归 SubAgent。

### Trace 记录

`AgentLoop` 原本已经会记录普通工具事件：

- `tool_call`
- `tool_result`

本次为 `delegate_task` 额外增加：

- `subagent_start`
- `subagent_result`

第一版没有记录子 Agent 内部每一次工具调用的完整 trace。原因是当前实现仍然保持轻量，先让主流程可观测。后续如果要做完整树形 trace，可以让 `SubAgentRunner` 接收 `TraceStore`、parent turn id 和 child task id。

### 为什么没有做 handoff

第一版没有让子 Agent 接管用户会话。

原因：

- 当前 CLI 是单用户本地会话，不需要客服式分流。
- MyAgent 的主目标是学习和面试讲解，主 Agent 保持最终控制更容易解释。
- handoff 会引入上下文交接、用户状态、返回控制权等额外复杂度。

当前选择更像 OpenAI agents-as-tools，也就是“主 Agent 把子 Agent 当工具调用”。

### 为什么只给只读工具

SubAgent 是被主 Agent 委托出去的执行单元。如果一开始就允许写文件、执行 shell 或调用任意 MCP 工具，调试和权限解释都会变复杂。

第一版只给：

- `list_dir`
- `read_file`

这已经足够测试“委托子任务浏览项目并总结”的核心能力。

后续如果要开放更多工具，建议按 profile 配置白名单。

### 自动化测试

新增测试文件：

```text
tests/test_subagent.py
```

覆盖内容：

- `SubAgentRunner` 能使用只读工具完成任务。
- 子 Agent 只能看到 `list_dir` 和 `read_file`。
- `DelegateTaskTool` 会返回格式化的子任务结果。
- `AgentLoop` 默认注册并执行 `delegate_task`。
- 主 Agent 能看到 `delegate_task`，子 Agent 看不到 `delegate_task`。

相关测试命令：

```text
python -m pytest tests/test_subagent.py tests/test_agent_loop.py tests/test_agent_trace.py
```

### 手动测试方式

启动 CLI：

```text
python -m myagent
```

可以尝试：

```text
请委托一个 researcher 子 Agent 浏览 docs/modules 目录，并总结当前项目有哪些模块。
```

如果模型决定调用 `delegate_task`，终端会先看到类似状态：

```text
正在调用工具：delegate_task task=...
```

然后子 Agent 会在内部调用只读工具读取目录或文件，最后主 Agent 整合结果给用户。

注意：模型是否调用 `delegate_task` 取决于模型自己的 tool calling 决策。如果想提高触发概率，可以明确说“请委托一个 researcher 子 Agent”。

### 当前限制

第一版仍然有这些限制：

- 子 Agent 和主 Agent 共用同一个 provider。
- profile 暂时写在代码里，还不能从配置文件改。
- 子 Agent 内部工具调用没有单独展示 spinner 状态。
- 子 Agent 内部工具调用没有完整 trace tree。
- 不支持并发子任务。
- 不支持后台任务取消。
- 不支持 handoff。

这些都可以作为第二版继续扩展。

## Phase 2 Review

### 当前实现

当前 SubAgent 已经完成一个轻量、可运行的 `agents-as-tools` 版本。

主链路：

```text
Main Agent
  -> delegate_task(task, agent_type, context)
  -> DelegateTaskTool
  -> create_subagent_registry(parent_registry)
  -> SubAgentRunner
  -> read-only tool loop
  -> formatted subagent result
  -> Main Agent final answer
```

已内置三个 profile：

```text
researcher
reviewer
interviewer
```

子 Agent 工具集当前固定为只读：

```text
list_dir
read_file
```

这意味着即使主 Agent 拥有 `write_file`、`web_search`、MCP tools 或 `delegate_task`，子 Agent 默认也不能使用这些工具。

Trace 当前记录主 Agent 视角：

```text
tool_call: delegate_task
subagent_start
subagent_result
tool_result: delegate_task
```

子 Agent 内部每一次 `read_file` / `list_dir` 暂时不会作为独立 trace tree 展开。

### 和原设计的差异

二期调研里提到过更完整的能力：

- SubAgent profile 配置化
- 独立模型配置
- 子 Agent 内部工具调用展示
- trace tree
- skills 绑定 profile
- handoff / supervisor / swarm 等多 Agent 模式

当前实现选择了最小、稳定、容易解释的版本：

- 只做 `delegate_task`，不做 handoff。
- 子 Agent 和主 Agent 共用 provider。
- profile 写在代码里。
- 子 Agent 只读，不开放写文件、MCP 和 web tools。
- 子 Agent 运行是同步的，结果回到主 Agent 后再生成最终答复。

这个差异是合理取舍：当前 MyAgent 仍然是个人助理 runtime，优先保证“能跑、能测、能讲清楚”，不急着引入多 Agent 平台复杂度。

### 当前问题

1. 子 Agent 内部过程对用户不可见。

用户只能看到：

```text
正在调用工具：delegate_task ...
```

看不到子 Agent 内部是否读了哪些文件、是否遇到工具错误。

2. Trace 还不是树形。

当前 trace 可以知道发生过委托，但很难展开成：

```text
main turn
  subagent task id
    child tool call
    child tool result
    child final summary
```

3. profile 仍写在代码里。

这对第一版足够，但后续如果用户想自定义 `researcher` / `reviewer` 的行为，需要配置化。

4. 子 Agent 不能使用 skills。

`reviewer` profile 和 `code-review` skill、`interviewer` profile 和 `interview-prep` skill 之间还没有绑定关系。

5. 第一版最初的子 Agent 不能联网。

这是最初的刻意限制，但会影响 researcher 类型任务。后续实现中，部分 profile 已经拿到只读 web tools；因此这里保留的是早期复盘口径，不再代表当前真实状态。

### 二期建议

优先级 1：补可观测性，不扩大权限。

- 为 SubAgentRunner 增加可选 trace hook。
- 记录 `subagent_tool_call` / `subagent_tool_result`。
- 在 trace data 中加入 `subagent_task_id` 和 `parent_turn_id`。
- CLI 仍然保持简洁，不默认刷出所有子工具调用。

优先级 2：profile 结构变清楚。

- 把 `SubAgentProfile` 扩展为包含：
  - name
  - description
  - instructions
  - allowed_tools
  - max_iterations
  - optional skill ids
- 暂时仍可写在代码里，先把结构拉平。

优先级 3：再考虑配置化和 skill 绑定。

- `myagent.json` 可覆盖或新增 profile。
- reviewer 默认绑定 `code-review`。
- interviewer 默认绑定 `interview-prep`。
- 继续评估哪些 profile 适合继承只读 web tools，哪些仍应只保留本地只读能力。

暂不建议现在做：

- handoff
- swarm
- 并发子任务
- 子 Agent 写文件
- 子 Agent 执行 shell
- 子 Agent 调任意 MCP tools

### 暂不处理

当前不把 SubAgent 升级成完整多 Agent 编排系统。

MyAgent 现阶段的 SubAgent 目标是：

```text
把复杂任务的一小段只读分析工作委托出去，并让主 Agent 保持最终控制。
```

不是：

```text
让多个 Agent 自治协作、交接会话或并发执行长期任务。
```

### 测试计划

已有测试：

```text
tests/test_subagent.py
tests/test_agent_loop.py
tests/test_agent_trace.py
```

后续如果做 SubAgent Phase 2A，应新增：

- 子 Agent 内部 tool call trace 测试。
- subagent task id 稳定写入 trace 的测试。
- profile allowed_tools 生效测试。
- 子 Agent 不继承 `write_file`、MCP tools、`delegate_task` 的回归测试。

### 面试表达更新

可以这样解释 SubAgent 模块：

```text
MyAgent 的 SubAgent 采用 agents-as-tools 模式，而不是 handoff。
主 Agent 通过 delegate_task 把一个边界清楚的小任务交给子 Agent。
子 Agent 有独立 profile 和独立上下文，只拿到 task、context 和受限只读工具。
这样主 Agent 仍然负责用户对话和最终答案，子 Agent 负责局部分析。
第一版刻意不开放写文件和递归委托，保证安全、可测试、容易解释。
第二阶段最值得增强的是 trace tree 和 profile 结构，而不是一上来做复杂多 Agent 协作。
```
## Phase 2A Implementation Notes

This phase implements the first observability upgrade without changing the
SubAgent permission model.

Changed files:

- `myagent/agent/subagent.py`
- `myagent/agent/loop.py`
- `tests/test_subagent.py`

Runtime flow:

```text
AgentLoop receives delegate_task
  -> creates subagent_task_id
  -> records subagent_start
  -> calls DelegateTaskTool.execute_with_trace(...)
  -> SubAgentRunner records each child tool call/result through trace_hook
  -> records subagent_result
```

New trace events:

```text
subagent_tool_call
subagent_tool_result
subagent_iteration_limit
```

Each child trace event includes:

```text
subagent_task_id
parent_turn_id
parent_tool_call_id
tool_call_id
tool_name
```

What stays intentionally unchanged:

- SubAgent receives read-only tools: `list_dir`, `read_file`, `web_search`, and
  `web_fetch`.
- SubAgent still cannot call `write_file`, MCP tools, or nested `delegate_task`.
- CLI still only shows the top-level `delegate_task` status by default.
- Profiles are still code-defined for now.

Verification:

```text
python -m pytest tests/test_subagent.py tests/test_agent_loop.py tests/test_agent_trace.py
15 passed
```

The important user-visible change is not a new terminal message. The visible
change is in trace files: a delegated task now exposes which read-only tools the
child Agent used internally.
## External Research Refresh: Delegation Strategy

This section recalibrates the SubAgent design against current public framework
patterns. The key correction is that normal users should not need to say
"delegate to researcher" in everyday prompts. Explicit invocation is useful for
debugging, testing, and power users, but the product behavior should be
automatic delegation.

Sources checked:

- Claude Code subagents:
  - https://code.claude.com/docs/en/subagents
- Claude Code SDK subagents:
  - https://code.claude.com/docs/en/agent-sdk/subagents
- OpenAI Agents SDK orchestration:
  - https://openai.github.io/openai-agents-js/guides/multi-agent/
- OpenAI Agents SDK agents/tools:
  - https://openai.github.io/openai-agents-js/guides/agents/
  - https://openai.github.io/openai-agents-js/guides/tools/
- LangGraph supervisor:
  - https://reference.langchain.com/javascript/modules/_langchain_langgraph-supervisor.html
- CrewAI collaboration:
  - https://docs.crewai.com/en/concepts/collaboration
  - https://docs.crewai.com/en/learn/customizing-agents

Research conclusions:

1. Automatic delegation is normal.

Claude Code automatically delegates when the user task matches a subagent's
description and current context. Explicit prompts such as "use the code-reviewer
subagent" exist, but they are fallback or forcing mechanisms, not the desired
default UX.

OpenAI Agents SDK describes two orchestration styles: LLM-driven orchestration
and code-driven orchestration. In LLM-driven orchestration, the main agent can
autonomously plan, use tools, and delegate to sub-agents. Code-driven
orchestration is used when the product needs deterministic routing.

2. Our current `delegate_task` matches the "agents as tools" pattern, but the
prompting is incomplete.

OpenAI calls this "agents as tools": a manager agent keeps conversation control
and invokes specialist agents as tools. This is a good fit for MyAgent because
the main personal assistant should own the final answer and synthesize results.
The missing piece is not the primitive; it is the policy that tells the main
agent when to use it proactively.

3. Handoff is a different pattern and should remain deferred.

Handoff means the specialist becomes the active user-facing agent. That is
useful for customer-service-style routing or domain-specific chat ownership.
MyAgent currently wants a single personal assistant persona, so handoff is not
the next step.

4. Sync and async both exist.

Claude Code supports foreground blocking subagents and background concurrent
subagents. OpenAI's orchestration guide also describes code-driven parallel
execution for independent tasks. MyAgent's current synchronous implementation is
acceptable for Phase 2 because it is simple and traceable. Async/background
subagents should be a later UX feature once cancellation, status, and trace
inspection are better.

5. Tool permissions vary by profile.

Claude Code supports allowlists, denylists, permission modes, hooks, and
skills per subagent. Built-in Explore and Plan agents are read-only; a
general-purpose subagent can have broader tools. CrewAI agents can be given
tools such as web search, memory, and delegation, and delegation is explicitly
controlled through configuration.

For MyAgent, the right Phase 2 rule is:

- researcher: read local files and public web sources
- reviewer: read local files and possibly run safe checks later
- interviewer: mostly no tools or read/search tools depending on task
- no default write access for child agents yet
- no recursive delegation yet
- no arbitrary MCP inheritance yet

Updated design direction:

```text
User asks a normal task
  -> Main Agent decides whether it needs isolated research/review work
  -> If yes, it calls delegate_task automatically
  -> SubAgent performs bounded read-only work
  -> Main Agent synthesizes final answer for the user
```

The user should only need explicit wording when they want to force or debug a
specific agent:

```text
Use the researcher subagent to inspect this.
```

Recommended next implementation:

1. Add a protected prompt section named `# Delegation Policy`.
2. Tell the main Agent to use `delegate_task` proactively for:
   - independent research
   - codebase exploration
   - review/checking work
   - large-output operations that should not pollute the main context
3. Keep explicit invocation available for testing.
4. Add trace fields that make the automatic decision visible:
   - `delegation_reason`
   - `selected_agent_type`
   - `delegation_mode: automatic | explicit`
5. Do not build a separate deterministic router yet. Start with LLM-driven
   routing because it matches Claude Code and OpenAI Agents SDK patterns and is
   smaller to implement.

Deferred:

- Background subagents
- Parallel subagent fan-out
- Handoff where the child agent speaks directly to the user
- Configurable profile files
- Profile-specific MCP inheritance
- Child-agent write/edit permissions
## SubAgent Capability Levels

SubAgent should not be understood as one fixed "researcher tool." Public Agent
frameworks use several related but different patterns. MyAgent should keep this
space open, then implement only the levels that are useful for the current
phase.

### Level 1: Agents As Tools

The main Agent keeps control of the user conversation and calls a specialist
Agent as a tool. The child Agent does bounded work and returns a result to the
main Agent.

Examples in other frameworks:

- OpenAI Agents SDK: manager agent uses specialist agents as tools.
- Claude Code: task-matched subagents run in isolated contexts.
- CrewAI: agents can delegate work to other agents.

MyAgent current status:

- Implemented as `delegate_task`.
- Synchronous.
- Main Agent still writes the final answer.
- Child Agent uses bounded read-only tools.

This is the right Phase 2 foundation.

### Level 2: Profile-Based SubAgents

Each SubAgent has its own profile:

- name
- description
- instructions
- allowed tools
- max iterations
- optional model
- optional skills
- optional memory scope

Examples:

- `researcher`: local files + public web search/fetch.
- `reviewer`: local files + later safe checks.
- `interviewer`: explanations, questions, and answer structure.
- `planner`: break down tasks without editing.
- `executor`: later, possibly controlled write/edit permissions.

MyAgent current status:

- Partially implemented: profiles exist in code.
- Not yet configurable.
- Tool permissions are still one shared child allowlist, not profile-specific.

Recommended Phase 2 direction:

- Keep profiles code-defined for now.
- Add `allowed_tools` to `SubAgentProfile`.
- Let each profile select a different read-only tool set.
- Do not move to user config until the behavior is proven.

### Level 3: Automatic Delegation Policy

The user should not need to say "use researcher" in normal interaction. The
main Agent should decide when delegated work is useful.

Examples in other frameworks:

- Claude Code uses subagent descriptions and context to trigger automatic
  delegation.
- OpenAI Agents SDK supports LLM-driven orchestration where the manager agent
  plans and invokes agent tools.
- Supervisor-style frameworks route tasks to specialist agents.

MyAgent current status:

- Not implemented yet.
- Explicit invocation works and is useful for testing.

Recommended next implementation:

- Add a protected `Delegation Policy` section to the main Agent context.
- Make `delegate_task` description clearer.
- Trace the reason/mode when a delegation happens.

### Level 4: Background Or Parallel SubAgents

SubAgents can run in the background or in parallel, then report back when done.

Examples in other frameworks:

- Claude Code supports foreground and background subagents.
- OpenAI orchestration examples can run independent agent calls concurrently.

MyAgent current status:

- Deferred.

Why deferred:

- Needs task status.
- Needs cancellation.
- Needs trace inspection.
- Needs result merge rules.
- Needs a better CLI/user notification model.

### Level 5: Supervisor Workflow

A supervisor or state graph controls a multi-step workflow and routes between
multiple specialist agents.

Examples in other frameworks:

- LangGraph supervisor.
- CrewAI process/task orchestration.
- AutoGen teams/group chat.

MyAgent current status:

- Deferred.

Why deferred:

- Useful for bigger workflows, but too heavy before the core personal assistant
  loop is stable.

### Level 6: Handoff

The child Agent takes over the user-facing conversation.

Examples in other frameworks:

- OpenAI Agents SDK handoffs.

MyAgent current status:

- Deferred.

Why deferred:

- MyAgent should feel like one coherent personal assistant.
- Handoff is better for customer service or multi-domain chat ownership.

### Current Target

For the current Phase 2 work, MyAgent should aim for:

```text
Level 1 complete
Level 2 partially complete
Level 3 minimal implementation
```

This means:

- Keep `delegate_task`.
- Make delegation automatic through policy.
- Keep child Agents synchronous.
- Keep child Agents bounded and observable.
- Add profile-specific tool permissions before adding broader permissions.
- Defer background execution, supervisor workflows, and handoff.

This keeps the design broad enough to avoid a narrow "researcher only" trap,
while still small enough to implement and explain.

## Phase 2B Implementation Notes

Phase 2B implements the first slice of profile-based SubAgents and automatic
delegation guidance.

Changed files:

- `myagent/agent/subagent.py`
- `myagent/agent/context.py`
- `myagent/agent/loop.py`
- `tests/test_subagent.py`
- `tests/test_context_builder.py`

Implemented:

- `SubAgentProfile` now includes `allowed_tools`.
- `researcher` can use:
  - `list_dir`
  - `read_file`
  - `web_search`
  - `web_fetch`
- `reviewer` can use:
  - `list_dir`
  - `read_file`
- `interviewer` can use:
  - `web_search`
  - `web_fetch`
- `ContextBuilder` now injects a protected `Delegation Policy` section into the
  main system prompt.
- `delegate_task` accepts an optional `reason` argument.
- `subagent_start`, `subagent_result`, and child SubAgent trace events include
  `delegation_reason` when available.
- `subagent_start` includes `delegation_mode`, currently a lightweight
  `automatic` / `explicit` hint based on the user request and tool arguments.

Runtime behavior:

```text
User asks a normal task
  -> Main Agent sees Delegation Policy in the protected context
  -> Main Agent may call delegate_task without the user explicitly asking
  -> DelegateTaskTool picks the requested profile
  -> create_subagent_registry copies only that profile's allowed tools
  -> SubAgent runs synchronously and returns a result
  -> Main Agent synthesizes the final answer
```

Important boundary:

- This is still LLM-driven routing, not a deterministic code router.
- The user can still force a SubAgent for testing.
- Child Agents still cannot write files, call MCP tools, or recursively delegate.
- Background/parallel SubAgents remain deferred.

Verification:

```text
python -m pytest tests/test_subagent.py tests/test_context_builder.py tests/test_agent_trace.py tests/test_agent_loop.py
24 passed
```

## Skills Alignment Design

This section records how SubAgent should relate to Skills and Active Skills.
It is a design checkpoint only. No runtime behavior changes are required yet.

### Problem

MyAgent now has two separate capability concepts:

```text
Skill:
  a reusable workflow or instruction file loaded from SKILL.md

SubAgent:
  a bounded execution unit with its own profile, prompt, and allowed tools
```

After Skills Phase 2B, the runtime can also record:

```text
active_skill_set skill_id=... scope=turn
```

The missing design question is:

```text
If the main Agent has activated a skill in the current turn,
should a delegated SubAgent receive that skill context?
```

### Core Principle

SubAgent profile remains the authority for execution boundaries.

Skills can inform how work is done, but they must not silently expand what a
child Agent is allowed to do.

```text
SubAgentProfile decides:
  role
  instructions
  allowed tools
  max iterations

Skill decides:
  workflow guidance
  task-specific method
  output style or checklist
```

This keeps the boundary explainable:

> A Skill can shape a SubAgent's thinking, but the SubAgent profile still
> controls its permissions.

### Three Possible Link Modes

#### Mode 1: No Skill Transfer

The main Agent may use a skill, but the child Agent receives only its profile
prompt and task.

Pros:

- Very simple.
- No extra prompt budget.
- No risk of sending irrelevant skill text.

Cons:

- The child Agent may repeat work the main Agent already did.
- A reviewer or researcher may miss the workflow the main Agent selected.

Current status:

```text
Implemented behavior today.
```

#### Mode 2: Active Skill Summary Transfer

The main Agent delegates a task and the runtime includes a compact hint:

```text
Active Skill Context:
- frontend-design was active in the parent turn.
- Scope: turn.
- Reason: loaded_by_skill_get.
```

The child Agent receives the fact that a skill was active, but not necessarily
the full `SKILL.md`.

Pros:

- Cheap.
- Easy to trace.
- Keeps the child context small.
- Gives the child Agent useful alignment without forcing the whole skill body.

Cons:

- The child Agent may still need full instructions for detailed workflows.

Implemented first slice:

```text
If parent turn has active_skill_set
and main Agent calls delegate_task
then include a compact Active Skill Context block in the child prompt.
```

This remains compact-context only. The child Agent does not receive the full
`SKILL.md`, and `SubAgentProfile.allowed_tools` is unchanged.

#### Mode 3: Full Skill Inheritance

The child Agent receives the full loaded `SKILL.md` content.

Pros:

- Strongest workflow alignment.
- Useful when the child Agent is doing the main skill-heavy work.

Cons:

- More tokens.
- More conflict risk if the skill conflicts with the child profile.
- Needs a clear rule for multiple active skills.

Deferred.

### Recommended Phase 2 Rule

For Phase 2, do not automatically inherit full skills.

Use this rule instead:

```text
Active Skill can be transferred to a SubAgent only as compact context.
SubAgentProfile.allowed_tools remains unchanged.
Full SKILL.md inheritance is explicit and deferred.
```

In plain language:

> Tell the child Agent what workflow the parent was using, but do not let that
> workflow grant new powers.

### Data Flow

The current implementation follows this flow:

```text
Main Agent turn
  -> skill_get(frontend-design)
  -> runtime records active_skill_set(scope=turn)
  -> main Agent calls delegate_task(agent_type=reviewer, task=...)
  -> DelegateTaskTool reads current turn active skills
  -> SubAgentRunner receives compact active_skill_context
  -> child system prompt includes:
       # Parent Active Skills
       - frontend-design: active in parent turn, reason=loaded_by_skill_get
```

Trace should make this visible:

```text
subagent_start:
  agent_type
  delegation_reason
  inherited_active_skills: ["frontend-design"]
```

### Conflict Rules

If profile and skill disagree, profile wins.

Examples:

```text
Skill says:
  Use browser or write files.

Reviewer profile allows:
  list_dir, read_file

Result:
  Child Agent can only list/read files.
```

If multiple active skills exist:

```text
Phase 2:
  pass only compact names/reasons, not full text

Later:
  introduce scoring, explicit parent selection, or task-level skill state
```

### Relationship To Automatic SkillSelector

This design does not require automatic SkillSelector.

The current sequence remains:

```text
Model sees Available Skills
Model calls skill_get when needed
Runtime records active_skill_set
SubAgent may later receive compact active skill context
```

Automatic selection can be considered later after:

- task/run state is clearer
- multiple skill conflicts are better understood
- prompt budget pressure is visible in trace

### What Not To Build Yet

Do not implement these yet:

- SubAgent automatically calling `skill_get` before every task.
- Full `SKILL.md` injection into every SubAgent.
- Skill-defined tool permissions.
- Skill-to-profile binding config.
- Persistent active skills across sessions.
- Background SubAgent skill inheritance.

### Interview Explanation

MyAgent separates "how to do work" from "who executes work."

Skills describe reusable methods, while SubAgents are bounded workers with their
own prompts and permissions. Active Skill is the bridge between them: it records
which workflow the parent Agent actually used. In the first safe design, a
SubAgent may receive that active skill as compact context, but the SubAgent
profile still controls tools and safety boundaries. This keeps the system useful
without turning Skills into hidden permission grants.

### Implementation Note

Changed files:

- `myagent/agent/loop.py`
- `myagent/agent/subagent.py`
- `tests/test_subagent.py`

Runtime details:

- `AgentLoop` keeps a turn-local active skill list while one message is being
  processed.
- `SkillGetTool` still emits `active_skill_set` through the existing trace hook.
- `AgentLoop` records that active skill in the current turn-local list.
- When `delegate_task` runs, `AgentLoop` formats a compact `# Parent Active
  Skills` block and passes it as extra child context.
- `subagent_start` trace includes `inherited_active_skills`.
- The list is cleared after the turn, so this is not persistent memory.

Verification:

```text
python -m pytest tests/test_subagent.py tests/test_agent_skills.py tests/test_skill_tools.py
```
