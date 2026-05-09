# ToolRegistry 模块设计

## 职责

ToolRegistry 负责管理 Agent 可用工具。

一句话版本：

```text
ToolRegistry 注册工具、暴露工具 schema、校验参数，并按名称执行工具。
```

第一阶段只做工具层本身，不急着接 LLM tool calling。

## 为什么需要它

现在 MyAgent 已经能聊天，也能保留对话历史，但它还不能“行动”。

没有工具层，Agent 只能回答文本：

```text
User -> LLM -> Text
```

有了工具层后，后续可以升级为：

```text
User -> LLM -> Tool Call -> Tool Result -> LLM -> Text
```

ToolRegistry 是这个 ReAct 闭环的基础。

## 参考 NanoBot 的取舍

NanoBot 的工具层主要包括：

- `Tool` 抽象类
- JSON Schema 参数定义
- 参数类型转换
- 参数校验
- ToolRegistry 注册和执行
- 文件工具
- shell 工具
- web 工具
- MCP 工具

MyAgent 第一阶段保留：

- `Tool` 抽象
- JSON Schema 参数
- 参数类型转换
- 参数校验
- `ToolRegistry`
- `list_dir`
- `read_file`

第一阶段暂不做：

- `write_file`
- `edit_file`
- `exec`
- `web_search`
- MCP 动态工具
- LLM tool calling

理由：

- 只读文件工具风险低。
- 可以先验证工具抽象。
- 写文件/执行命令涉及安全边界，后续单独设计更稳。

## 所属架构层

ToolRegistry 属于 `Capability Layer`。

它位于：

```text
AgentLoop
  ↓
ToolRegistry
  ↓
Tool
```

后续接入 LLM tool calling 后，数据流会变成：

```text
Provider response
  ↓ tool calls
AgentLoop
  ↓ registry.execute(name, args)
ToolRegistry
  ↓ tool.execute(...)
Tool result
  ↓
AgentLoop
```

第一阶段只实现工具层，不接 AgentLoop。

## 核心概念

### Tool

Tool 是所有工具的基础接口。

第一阶段字段：

```text
name: str
description: str
parameters: dict
execute(**kwargs) -> str
```

其中 `parameters` 是 JSON Schema。

### ToolRegistry

ToolRegistry 管理工具集合。

核心能力：

```text
register(tool)
unregister(name)
get(name)
has(name)
get_definitions()
execute(name, params)
tool_names
```

### JSON Schema

工具参数使用 JSON Schema 描述。

例子：

```json
{
  "type": "object",
  "properties": {
    "path": {"type": "string"}
  },
  "required": ["path"]
}
```

好处：

- 后续可以直接转换成 OpenAI tool schema。
- 参数约束和工具实现分离。
- 测试时可以验证缺参、类型错误。

## 第一阶段内置工具

### list_dir

功能：列出目录内容。

参数：

```text
path: str
recursive: bool = False
max_entries: int = 200
```

行为：

- 非递归时列出当前目录直接子项。
- 递归时列出相对路径。
- 忽略常见噪音目录，比如 `.git`、`__pycache__`、`.venv`。
- 超过 `max_entries` 时截断并提示。

### read_file

功能：读取文本文件内容。

参数：

```text
path: str
offset: int = 1
limit: int = 2000
```

行为：

- 按行读取。
- 返回带行号的文本。
- 支持 offset/limit 分页。
- 空文件返回空文件提示。
- 不存在或不是文件时返回错误文本。

## 路径策略

第一阶段工具只允许访问 workspace 下的路径。

默认 workspace：

```text
当前项目根目录
```

路径处理规则：

- 相对路径：相对 workspace 解析。
- 绝对路径：必须位于 workspace 下。
- 越界路径：返回错误。

这样做的原因：

- 降低工具误读系统文件的风险。
- 面试时可以讲清楚安全边界。
- 后续 write/exec 工具也能复用同一套路径策略。

## 第一阶段范围

第一阶段只实现：

- `Tool`
- `ToolRegistry`
- 参数类型转换
- 参数校验
- OpenAI function schema 输出
- workspace path 解析
- `list_dir`
- `read_file`
- 测试覆盖

## 暂不实现

第一阶段暂不实现：

- LLM 自动工具调用
- write_file
- edit_file
- exec
- web_search
- MCP
- ask_user 安全确认
- 复杂权限策略
- 文件编码自动探测
- 二进制文件读取

## 最小测试点

建议测试文件：

```text
tests/test_tool_registry.py
tests/test_filesystem_tools.py
```

测试点：

1. `test_registry_registers_and_finds_tool`
2. `test_registry_rejects_unknown_tool`
3. `test_registry_validates_required_params`
4. `test_registry_casts_basic_param_types`
5. `test_registry_returns_openai_tool_definitions`
6. `test_list_dir_lists_workspace_files`
7. `test_read_file_returns_numbered_lines`
8. `test_read_file_supports_offset_and_limit`
9. `test_filesystem_tool_blocks_path_escape`

## 面试表达

可以这样讲：

> 我把工具层抽成 Tool 和 ToolRegistry。每个工具自己声明 name、description 和 JSON Schema 参数，Registry 负责注册、校验和执行。这样 AgentLoop 后续只需要按工具名调用 registry，不需要知道每个工具的实现细节。

如果面试官问“为什么第一阶段只做读工具”，可以回答：

> 因为读取目录和文件可以验证工具抽象，但风险低。写文件、编辑文件、执行命令都涉及安全边界和确认机制，后续单独设计更合适。

如果面试官问“为什么用 JSON Schema”，可以回答：

> LLM tool calling 本身就使用 JSON Schema 描述工具参数。提前用 JSON Schema 做工具定义，后续接 OpenAI-compatible tool calling 时可以直接复用。

## 后续扩展方向

后续可以增强：

- 接入 AgentLoop 的 tool calling
- `write_file`
- `edit_file`
- `exec`
- `web_search`
- MCP 工具动态注册
- 工具调用 trace
- 工具超时
- 工具风险等级
- `ask_user` 安全确认
- workspace allowlist
- 更完整 JSON Schema 校验

## 实现记录

本阶段已经完成 ToolRegistry 的第一版代码，实现范围和上面的设计保持一致：先把工具抽象、注册表、参数校验、只读文件工具跑通，暂时不接入 LLM 自动 tool calling。

新增代码文件：

```text
myagent/tools/__init__.py
myagent/tools/base.py
myagent/tools/registry.py
myagent/tools/filesystem.py
tests/test_tool_registry.py
tests/test_filesystem_tools.py
```

### 代码阅读顺序

建议按这个顺序看：

1. `myagent/tools/base.py`
2. `myagent/tools/registry.py`
3. `myagent/tools/filesystem.py`
4. `myagent/tools/__init__.py`
5. `tests/test_tool_registry.py`
6. `tests/test_filesystem_tools.py`

原因是：`base.py` 定义所有工具要遵守的接口，`registry.py` 负责管理和调用工具，`filesystem.py` 是第一批具体工具，`__init__.py` 提供默认工具注册入口，测试文件则对应验证这些行为。

### Tool 抽象做了什么

`Tool` 是所有工具的基类。

每个工具需要提供：

```text
name
description
parameters
execute(...)
```

其中 `parameters` 使用一个简化版 JSON Schema。现在支持的重点是：

- 必填参数检查
- 基础类型检查和转换
- 输出 OpenAI-compatible tool schema

举个例子，调用工具时如果传入：

```json
{"a": "2", "b": "3"}
```

而 schema 里声明 `a` 和 `b` 是 integer，当前实现会尝试把字符串转换成整数。这样做是为了兼容 LLM 输出参数时常见的轻微类型偏差。

### ToolRegistry 做了什么

`ToolRegistry` 是工具的统一入口。

它负责：

- `register(tool)`：注册工具
- `unregister(name)`：取消注册
- `get(name)`：按名字获取工具
- `has(name)`：判断工具是否存在
- `get_definitions()`：输出给 LLM 用的工具定义
- `execute(name, params)`：校验参数并执行工具

设计重点是让 `AgentLoop` 后续不需要知道具体工具类。它只需要拿到模型返回的工具名和参数，然后调用：

```python
await registry.execute(tool_name, arguments)
```

这样后续新增 `web_search`、`exec`、MCP 工具时，AgentLoop 的改动会比较小。

### 文件工具做了什么

当前内置两个只读工具：

```text
list_dir
read_file
```

`list_dir` 用来列目录，支持普通列举和递归列举。

`read_file` 用来读取 UTF-8 文本文件，返回内容时会带行号，并支持 `offset` 和 `limit`，方便后续模型分段读取长文件。

这两个工具都继承 `FilesystemTool`，共享同一个路径策略：

- 相对路径会相对于 workspace 解析
- 绝对路径必须仍然在 workspace 里面
- 超出 workspace 的路径会被拒绝

这个策略很重要，因为工具一旦接入 LLM，模型可能会尝试读取各种路径。第一版先把边界卡住，后面再做写文件和执行命令时可以复用这套思路。

### 默认注册入口

`create_default_registry(workspace=None)` 会创建一个默认 registry，并注册：

```text
list_dir
read_file
```

如果没有传 workspace，就默认使用当前运行目录。后续 AgentLoop 接入工具调用时，可以先从这个函数拿到默认工具集合。

### 测试说明

本阶段新增了两组测试：

```text
tests/test_tool_registry.py
tests/test_filesystem_tools.py
```

覆盖内容包括：

- 工具注册和查询
- 未知工具报错
- 缺少必填参数报错
- 基础参数类型转换
- OpenAI-compatible tool schema 输出
- 列目录
- 递归列目录
- 读文件带行号
- offset/limit 分页读取
- 阻止 workspace 外路径访问
- 默认 registry 包含只读文件工具

因为本机 Windows 临时目录存在权限问题，文件工具测试没有使用 pytest 默认的系统临时目录，而是使用项目内的 `.test-workspaces/`。这个目录已经在 `.gitignore` 中忽略，只作为本地测试工作区。

验证结果：

```text
python -m pytest
45 passed
```

### 当前边界

现在工具层已经能独立运行，但还没有被 AgentLoop 使用。

也就是说：

- 代码里可以手动调用 `registry.execute(...)`
- LLM 还不会自动选择和调用工具
- CLI 聊天时暂时还不能让模型直接读取文件

下一步如果继续做工具方向，应该设计并实现 `LLM tool calling -> AgentLoop -> ToolRegistry -> Tool result -> LLM final answer` 这一段闭环。

## Tool Calling 接入设计

为了让用户可以在 CLI 里直接让 LLM 浏览本地目录、查看文件，本阶段把 ToolRegistry 接入 AgentLoop。

目标链路：

```text
User
  -> AgentLoop builds messages
  -> Provider receives tools
  -> LLM returns tool_calls
  -> AgentLoop executes ToolRegistry
  -> Tool result is appended as tool message
  -> Provider generates final answer
  -> CLI prints answer
```

### Provider 响应升级

原来的 provider 只返回字符串：

```python
await provider.generate(messages) -> str
```

为了兼容工具调用，新增一个更结构化的响应：

```text
ProviderResponse
  content: str
  tool_calls: list[ToolCall]
```

但 `generate()` 会保留，继续返回字符串。这样之前的 EchoProvider、旧测试和简单调用方式都不需要大改。

### AgentLoop 的工具循环

AgentLoop 新增一个轻量工具循环：

```text
最多执行 max_tool_iterations 轮
每轮调用 provider.generate_response(messages, tools)
如果没有 tool_calls，返回 content
如果有 tool_calls，逐个执行 registry.execute(...)
把工具结果作为 role=tool 的消息放回 messages
继续请求模型生成最终回答
```

第一版默认 `max_tool_iterations = 8`。这个限制是为了避免模型反复调用工具导致死循环，同时给真实模型浏览目录、读取多个文件留下足够空间。

### 当前支持的工具

CLI 默认启用：

```text
list_dir
read_file
```

所以用户可以尝试这样问：

```text
帮我看看当前目录下有哪些文件
读取 pyproject.toml 看看项目依赖
帮我浏览 docs/modules 目录
```

注意：工具只允许访问当前项目 workspace 内的路径，不能读取 workspace 外的文件。

### 暂时不做的事

本阶段暂时不做：

- write/edit/exec 工具
- 工具调用 trace
- 用户确认机制
- MCP 工具
- 复杂权限配置
- streaming tool calling

这些后续可以独立设计。

## Tool Calling 接入实现记录

本阶段已经把只读工具接入 AgentLoop。现在真实 LLM 在支持 OpenAI-compatible tool calling 的情况下，可以在 CLI 对话中调用：

```text
list_dir
read_file
```

### 修改的代码

```text
myagent/agent/context.py
myagent/agent/loop.py
myagent/providers/base.py
myagent/providers/echo.py
myagent/providers/openai_compatible.py
tests/test_agent_loop.py
tests/test_llm_provider.py
```

### ProviderResponse

`myagent/providers/base.py` 新增：

```text
ToolCall
ProviderResponse
```

`ToolCall` 表示模型请求的一次工具调用：

```text
id
name
arguments
```

`ProviderResponse` 表示一次模型响应：

```text
content
tool_calls
```

这样 provider 不再只能表达“模型说了一段话”，也能表达“模型想调用一个工具”。

### OpenAICompatibleProvider

`OpenAICompatibleProvider.generate()` 仍然保留，继续返回字符串，避免影响之前的调用方式。

新增：

```python
generate_response(messages, tools=None) -> ProviderResponse
```

当 AgentLoop 传入 `tools` 时，它会调用 OpenAI-compatible Chat Completions：

```text
tools=<ToolRegistry.get_definitions()>
tool_choice="auto"
```

如果模型返回 `tool_calls`，provider 会把 SDK 对象解析成 MyAgent 内部的 `ToolCall`。

### AgentLoop 工具循环

`AgentLoop` 现在默认创建：

```python
create_default_registry()
```

也就是默认启用只读文件工具。

核心流程在 `_generate_with_tools()`：

```text
构造 messages
调用 provider.generate_response(messages, tools)
如果没有 tool_calls，直接返回 content
如果有 tool_calls：
  把 assistant tool_call 消息加入 messages
  执行 ToolRegistry.execute(name, arguments)
  把工具结果作为 role=tool 消息加入 messages
  再调用 provider.generate_response(...)
```

为了避免无限循环，默认最多执行：

```text
MAX_TOOL_ITERATIONS = 3
```

如果模型连续三轮都只调用工具、不生成最终答案，AgentLoop 会返回一条限制提示。

### CLI 现在怎么测试

你可以直接运行：

```text
python -m myagent
```

然后试：

```text
帮我看看当前目录下有哪些文件
读取 pyproject.toml，告诉我这个项目用了哪些依赖
浏览 docs/modules 目录，然后总结一下目前做了哪些模块
```

如果当前配置使用的是 EchoProvider，它不会调用工具，只会 echo。要测试这个能力，需要 `myagent.json` 里是 OpenAI-compatible provider，并且模型本身支持 tool calling。

### 测试覆盖

新增测试点：

- AgentLoop 收到 provider 返回的 `ToolCall` 后，会执行本地工具
- 工具结果会作为 `role=tool` 消息回填给 provider
- OpenAICompatibleProvider 会把 SDK 的 tool_calls 解析成 MyAgent 内部结构
- 旧的 `generate()` 字符串接口仍然可用

验证结果：

```text
python -m pytest
47 passed
```

### 当前边界

现在已经可以让支持 tool calling 的真实 LLM 浏览本地目录和读取文件。

但当前仍然只支持只读工具：

- 能列目录
- 能读 UTF-8 文本文件
- 不能写文件
- 不能编辑文件
- 不能执行命令
- 不能访问 workspace 外路径

## Tool Calling 兼容性修正

真实测试时遇到一个 OpenAI-compatible 后端差异：

```text
The `reasoning_content` in the thinking mode must be passed back to the API.
```

原因是某些 reasoning/thinking 模型在返回 tool_calls 时，assistant message 里不仅有 `tool_calls`，还会有 `reasoning_content`。下一轮把工具结果发回 API 时，需要把上一条 assistant message 的 `reasoning_content` 一起带回去。

修正策略：

- `ProviderResponse` 增加 `extra_message_fields`
- `OpenAICompatibleProvider` 读取 SDK message 上的 `reasoning_content`
- AgentLoop 构造 assistant tool_call message 时，把这些额外字段原样放回消息
- AgentLoop 捕获 provider/tool loop 异常，返回错误文本，不再让 CLI 直接打印完整 traceback

这个修正保持轻量，不把具体模型厂商写死到 AgentLoop，只由 provider 层把兼容字段放进结构化响应。

## 工具调用状态展示设计

为了让 CLI 用户知道 Agent 当前正在做什么，工具调用阶段增加轻量状态消息。

设计目标：

```text
User asks question
  -> MyAgent: 正在调用工具：list_dir path=docs/modules
  -> MyAgent: 正在调用工具：read_file path=docs/modules/xxx.md
  -> MyAgent: final answer
```

实现方式：

- AgentLoop 在执行每个工具前发布一个 `OutboundMessage`
- 状态消息使用 `metadata["kind"] = "status"`
- 最终回答使用普通 `OutboundMessage`
- CLI 收到 `kind=status` 时立即打印，但继续等待下一条消息
- CLI 收到非 status 消息时，认为这是本轮最终回答

这样不需要引入 streaming，也不需要改 MessageBus 的基础结构。它只是把“中间状态”也当成一种 outbound message。

第一版只展示：

- 工具名
- 关键参数

暂时不展示：

- 完整工具返回内容
- token 流式输出
- 模型内部 reasoning

### 工具状态展示实现记录

本阶段已经完成状态展示。

修改文件：

```text
myagent/agent/loop.py
myagent/cli/commands.py
tests/test_agent_loop.py
tests/test_cli_channel.py
```

AgentLoop 在执行每个工具前会发布状态消息：

```text
metadata.kind = "status"
content = "正在调用工具：read_file path=pyproject.toml"
```

CLI 收到状态消息后会立即打印，但不会结束本轮等待；它会继续消费 outbound queue，直到收到非 status 消息，也就是最终回答。

用户现在会看到类似：

```text
MyAgent: 正在调用工具：list_dir path=docs/modules
MyAgent: 正在调用工具：read_file path=docs/modules/TOOL_REGISTRY.md
MyAgent: 目前已经完成了这些模块：...
```

验证结果：

```text
python -m pytest
50 passed
```

## Write File Tool Implementation Note

本地测试发现：当用户要求“设计一个前端 HTML 网页，保存下来”时，Agent 回复“无法直接写文件到磁盘”。

排查结论：

- 不是模型没有理解“保存下来”。
- 默认工具 registry 只有 `list_dir` 和 `read_file`。
- MyAgent 当时确实没有提供 `write_file` 工具，所以模型没有可调用的保存能力。

已修复：

- 新增 `WriteFileTool`。
- `create_default_registry(...)` 默认注册：
  - `list_dir`
  - `read_file`
  - `write_file`
- `write_file` 只能写入当前 workspace 内路径。
- 父目录不存在时会自动创建。
- 如果目标文件已存在，默认拒绝覆盖；只有传 `overwrite=true` 才会替换。
- `delegate_task` 子 Agent 仍然只继承 `list_dir` / `read_file`，保持子 Agent 默认只读。

建议本地验证：

```text
python -m myagent
```

然后输入：

```text
帮我设计一个可以用于社团宣传的前端html网页，保存为 club-promotion.html
```

预期应该看到类似：

```text
正在调用工具：write_file path=club-promotion.html ...
```

自动测试：

```text
python -m pytest tests/test_filesystem_tools.py tests/test_agent_loop.py tests/test_agent_trace.py tests/test_subagent.py
25 passed
```

## Web Search Tool Implementation Note

用户在本地使用过程中发现 MyAgent 缺少 web search 能力。对于个人助理型 Agent，这属于高价值能力：当本地文件、memory 和 MCP tools 不够时，Agent 应该能查询公开网页信息。

本阶段新增内置工具：

```text
web_search
web_fetch
```

默认注册位置：

```text
create_default_registry(...)
```

参数：

```text
query: str
max_results: int = 5
```

第一版实现：

- 使用 `httpx` 访问公开搜索页面。
- 解析标题、URL、摘要。
- 返回紧凑文本结果，适合继续交给 LLM 总结。
- `web_fetch` 可以打开 `web_search` 返回的 URL，并提取可读正文。
- 自动测试使用 fake HTTP response，不依赖真实网络。

当前边界：

- 不做浏览器渲染。
- 不做搜索供应商账号/API key 配置。
- 搜索页 HTML 结构可能变化，后续如果要稳定生产使用，可以替换为正式 search API 或 MCP search server。

本地天气测试暴露了一个重要边界：`web_search` 成功返回了天气站点结果，但模型需要更具体的页面内容时只能反复换关键词搜索，最后触发工具调用上限。因此补充 `web_fetch`，让通用 web 能力形成：

```text
web_search -> web_fetch -> final answer
```

这不是天气专用工具，而是通用网页读取能力。

测试：

```text
tests/test_web_tool.py
tests/test_tool_registry.py
```
