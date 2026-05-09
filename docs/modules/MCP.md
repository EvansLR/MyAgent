# MCP 模块设计

## 职责

MCP 负责把外部 MCP server 暴露的工具接入 MyAgent。

一句话版本：

```text
MCP 模块连接外部 MCP server，读取它提供的 tools，并把这些 tools 动态注册到 ToolRegistry。
```

它属于 `Capability Layer`。

## 为什么需要它

现在 MyAgent 已经有本地 ToolRegistry，也能让 LLM 调用：

```text
list_dir
read_file
```

但这些工具都是 MyAgent 自己实现的。

如果后续想接入外部能力，比如：

```text
filesystem MCP
git MCP
browser MCP
database MCP
notion MCP
github MCP
```

就不应该每个工具都在 MyAgent 里重新写一遍。

MCP 的价值是提供一个统一协议：

```text
外部 server 提供工具
MyAgent 动态发现工具
LLM 像调用普通 Tool 一样调用它们
```

## 第一阶段定位

第一阶段只做：

```text
stdio MCP
```

暂不做：

- SSE MCP
- HTTP streaming
- OAuth / token 管理
- 多租户
- MCP resource
- MCP prompt
- MCP sampling
- server 自动安装
- 复杂生命周期管理
- 工具权限 UI

原因：

- stdio 是最容易本地测试的 MCP 模式。
- MyAgent 当前重点是面试展示，不需要一开始做完整 MCP client。
- 先跑通 “MCP tool -> ToolRegistry -> LLM tool calling” 这条链路最重要。

## MCP 和 ToolRegistry 的关系

ToolRegistry 是 MyAgent 内部统一工具入口。

MCP tools 不应该绕过 ToolRegistry。

目标结构：

```text
MCP Server
  -> list_tools
  -> McpToolAdapter
  -> ToolRegistry.register(...)
  -> AgentLoop
  -> LLM tool calling
```

这样 AgentLoop 不需要区分：

```text
本地 read_file 工具
MCP github_search_issues 工具
MCP database_query 工具
```

对 AgentLoop 来说，它们都是：

```text
Tool
```

## 第一版配置

建议先在 `myagent.json` 里增加：

```json
{
  "mcpServers": {
    "example": {
      "command": "python",
      "args": ["path/to/server.py"]
    }
  }
}
```

第一版字段：

```text
mcpServers: dict
  name: str
  command: str
  args: list[str]
  env: dict[str, str] | optional
```

暂不支持：

- cwd
- timeout 配置
- disabled/enabled
- headers
- SSE url
- secret 管理

后续可以扩展。

## 数据结构

建议新增：

```text
myagent/mcp/
  __init__.py
  config.py
  client.py
  adapter.py
  registry.py
```

### McpServerConfig

字段：

```text
name: str
command: str
args: list[str]
env: dict[str, str]
```

### McpClient

负责和一个 MCP server 通信。

第一版接口：

```text
connect()
list_tools() -> list[McpToolDefinition]
call_tool(name, arguments) -> str
close()
```

### McpToolDefinition

从 MCP server 获取到的工具描述。

字段：

```text
name
description
input_schema
```

### McpToolAdapter

把 MCP tool 包装成 MyAgent `Tool`。

字段/行为：

```text
name -> 加 server prefix，避免冲突
description -> 来自 MCP tool
parameters -> input_schema
execute(**kwargs) -> client.call_tool(...)
```

命名建议：

```text
mcp_<server>_<tool>
```

例如：

```text
mcp_github_search_issues
mcp_filesystem_read_file
```

这样能避免和本地工具重名。

## MCP 工具命名策略

为什么要加前缀？

因为不同 server 可能都有：

```text
read_file
search
query
```

如果直接注册，会和本地工具或其他 MCP server 冲突。

第一版统一：

```text
mcp_{server_name}_{tool_name}
```

要求：

- 全部转成小写
- 非字母数字下划线转换成 `_`
- 连续 `_` 合并

## 与 AgentLoop 的关系

AgentLoop 不直接依赖 MCP。

推荐流程：

```text
create_default_registry()
  -> register local tools
  -> register MCP tools
AgentLoop(tool_registry=registry)
```

这样 AgentLoop 仍然只依赖 ToolRegistry。

## 与配置系统的关系

Settings 负责读取 `myagent.json` 的 `mcpServers`。

但第一版可以先做最小：

```text
parse_mcp_servers(config data)
```

不急着把所有 MCP 细节塞进 Settings。

实现时可以先让 `create_provider` 保持不变，AgentLoop 初始化或 CLI 启动阶段单独创建 registry。

## 与 Skills 的关系

Skills 是提示词能力说明。

MCP 是外部可执行工具。

它们可以组合，但第一版不强行联动。

后续可能出现：

```text
github skill
  -> 指导模型如何查 issue / PR
github MCP
  -> 提供实际 search_issues / get_pr 工具
```

第一版只让 MCP tools 进入 ToolRegistry。

## Trace 事件

MCP 接入后，已有的：

```text
tool_call
tool_result
```

仍然适用。

可以额外记录：

```text
mcp_server_connected
mcp_tool_registered
mcp_server_error
```

第一版建议至少记录：

- `mcp_tool_registered`
- `mcp_server_error`

## 第一阶段范围

第一阶段实现：

- `docs/modules/MCP.md`
- `McpServerConfig`
- 读取 JSON config 中的 `mcpServers`
- stdio MCP client 最小封装
- MCP tools 转 MyAgent Tool
- 注册到 ToolRegistry
- 工具命名加 server prefix
- 测试使用 fake MCP client，不依赖真实外部 server

如果真实 MCP SDK 接入成本较高，可以先做接口和 fake client，把外部协议实现留到第二步。

## 暂不实现

第一阶段暂不实现：

- SSE MCP
- MCP resources
- MCP prompts
- MCP sampling
- OAuth
- server install
- server health check
- long-running lifecycle manager
- permission UI
- sandbox policy
- 多进程 MCP
- streaming result

## 测试点

建议新增：

```text
tests/test_mcp_config.py
tests/test_mcp_adapter.py
tests/test_mcp_registry.py
```

测试内容：

1. 能从 JSON dict 解析 `mcpServers`。
2. server name / tool name 会安全化。
3. McpToolAdapter 能暴露 Tool schema。
4. McpToolAdapter execute 会调用 fake client。
5. MCP tools 能注册进 ToolRegistry。
6. 工具名冲突时 prefix 能避免覆盖。
7. MCP server 失败时不会影响本地工具注册。

## 手动测试方式

第一版如果接入真实 stdio MCP server，可以测试：

```json
{
  "mcpServers": {
    "demo": {
      "command": "python",
      "args": ["demo_mcp_server.py"]
    }
  }
}
```

运行：

```text
python -m myagent
```

然后问：

```text
你现在有哪些工具？请列出 MCP 工具。
```

预期能看到类似：

```text
mcp_demo_xxx
```

然后让模型调用对应工具。

## 面试表达

可以这样讲：

> 我没有让 AgentLoop 直接调用 MCP，而是把 MCP tools 适配成 MyAgent 内部统一的 Tool，再注册进 ToolRegistry。这样本地工具和外部 MCP 工具在 AgentLoop 看来是同一种抽象，LLM tool calling 的流程不用改。第一版先支持 stdio MCP，跑通动态工具注册；SSE、认证和复杂生命周期作为后续扩展。

如果面试官问“为什么工具名要加 server 前缀”，可以回答：

> 因为不同 MCP server 可能暴露同名工具，比如 search、query、read_file。用 `mcp_{server}_{tool}` 可以避免命名冲突，也方便 trace 和调试时定位工具来源。

## 后续扩展方向

后续可以增强：

- SSE MCP
- MCP resources
- MCP prompts
- server lifecycle manager
- server health check
- tool permission policy
- MCP tool trace summary
- skill + MCP 联动
- MCP config validation
- MCP CLI 子命令
- MCP server marketplace

## 第一阶段试验实现记录

本阶段先实现 MCP adapter 骨架，没有接真实 MCP stdio 协议。

目的：

```text
先验证 MCP tool 能被包装成 MyAgent Tool，并注册进 ToolRegistry。
```

新增文件：

```text
myagent/mcp/__init__.py
myagent/mcp/config.py
myagent/mcp/types.py
myagent/mcp/adapter.py
myagent/mcp/registry.py
tests/test_mcp_config.py
tests/test_mcp_adapter.py
tests/test_mcp_registry.py
```

### 已实现内容

#### McpServerConfig

用于表示一个 stdio MCP server 配置：

```text
name
command
args
env
```

`parse_mcp_servers(...)` 可以从 JSON dict 中解析：

```json
{
  "mcpServers": {
    "demo": {
      "command": "python",
      "args": ["server.py"]
    }
  }
}
```

#### McpToolDefinition

表示 MCP server 暴露的一个工具：

```text
name
description
input_schema
```

#### McpToolClient

当前是一个 Protocol，只要求：

```text
call_tool(name, arguments) -> str
```

测试里用 fake client 实现它。

#### McpToolAdapter

把 MCP tool 包装成 MyAgent `Tool`。

行为：

```text
name -> mcp_{server}_{tool}
description -> MCP description
parameters -> MCP input_schema
execute -> client.call_tool(original_tool_name, kwargs)
```

#### register_mcp_tools

把一组 MCP tool definitions 注册到 ToolRegistry。

### 当前能验证什么

现在已经能验证：

- MCP server 配置可以解析。
- MCP tool name 会被安全化和加前缀。
- McpToolAdapter 能输出 OpenAI-compatible schema。
- ToolRegistry 能注册 MCP tool。
- ToolRegistry.execute(...) 能执行 fake MCP client。

### 当前还不能做什么

当前已经补上最小 `StdioMcpClient`，可以连接实现 JSON-RPC over stdio 的 MCP server。

但仍然是轻量实现，还缺更完整的生命周期和协议覆盖。

## Stdio MCP 实现设计补充

根据 MCP 官方协议，stdio MCP 第一版需要支持这些 JSON-RPC 消息：

### initialize

连接 server 后，client 首先发送：

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2025-03-26",
    "capabilities": {},
    "clientInfo": {
      "name": "MyAgent",
      "version": "0.1.0"
    }
  }
}
```

收到响应后，再发送 initialized notification：

```json
{
  "jsonrpc": "2.0",
  "method": "notifications/initialized"
}
```

### tools/list

工具发现：

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/list",
  "params": {}
}
```

返回：

```json
{
  "result": {
    "tools": [
      {
        "name": "echo",
        "description": "Echo text",
        "inputSchema": {
          "type": "object",
          "properties": {
            "text": {"type": "string"}
          },
          "required": ["text"]
        }
      }
    ]
  }
}
```

### tools/call

工具调用：

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "echo",
    "arguments": {"text": "hello"}
  }
}
```

第一版只把 text content 合并成字符串返回给 MyAgent。

### 第一版实现策略

不引入 MCP SDK，先实现一个最小 `StdioMcpClient`：

```text
connect()
  -> create subprocess
  -> initialize
  -> notifications/initialized
list_tools()
  -> tools/list
call_tool()
  -> tools/call
close()
  -> terminate subprocess
```

通信方式：

```text
每个 JSON-RPC message 一行 JSON
stdin 写入
stdout 读取
```

第一版限制：

- 不处理 server 发来的 requests。
- 忽略 notifications。
- 不读取 resources/prompts。
- stderr 不进入 trace。
- 超时先用简单 asyncio wait_for。

### CLI 接入策略

`myagent.json` 增加：

```json
{
  "mcpServers": {
    "demo": {
      "command": "python",
      "args": ["demo_mcp_server.py"]
    }
  }
}
```

启动 CLI 时：

```text
Settings.from_sources()
  -> mcp_servers
run_local_chat()
  -> create_default_registry()
  -> connect configured MCP servers
  -> register MCP tools
  -> AgentLoop(tool_registry=registry)
```

退出 CLI 时：

```text
close MCP clients
```

### 验证结果

```text
python -m pytest
72 passed
```

## Stdio MCP 最小实现记录

本阶段继续补上了真实 stdio client 和 CLI 配置接入。

新增/修改文件：

```text
myagent/mcp/stdio.py
myagent/mcp/__init__.py
myagent/config/settings.py
myagent/cli/commands.py
tests/test_mcp_stdio.py
tests/test_llm_provider.py
```

### StdioMcpClient

`StdioMcpClient` 支持：

```text
connect()
list_tools()
call_tool(name, arguments)
close()
```

连接流程：

```text
create subprocess
-> initialize
-> notifications/initialized
```

工具流程：

```text
tools/list
tools/call
```

工具返回结果里只提取 `type=text` 的 content，并合并为字符串。

### Settings 接入

`Settings.from_sources(...)` 现在会读取：

```json
{
  "mcpServers": {
    "demo": {
      "command": "python",
      "args": ["server.py"],
      "env": {"TOKEN": "abc"}
    }
  }
}
```

并解析成：

```text
settings.mcp_servers
```

### CLI 接入

`run_local_chat(...)` 现在会：

```text
create_default_registry()
-> connect configured MCP servers
-> list_tools
-> register_mcp_tools
-> AgentLoop(tool_registry=registry)
```

退出时会关闭 MCP clients。

如果某个 MCP server 连接失败，CLI 会打印错误，但不会阻止 MyAgent 启动，本地工具仍然可用。

### 测试说明

新增测试：

```text
tests/test_mcp_stdio.py
```

它会创建一个本地 Python demo MCP server，验证：

```text
initialize
notifications/initialized
tools/list
tools/call
```

当前开发沙箱在 Windows 下可能禁止 asyncio subprocess pipe，遇到 `WinError 5` 时该测试会 skip。

验证结果：

```text
python -m pytest
73 passed, 1 skipped
```

## URL / Streamable HTTP MCP 实现记录

本阶段补充支持 URL 型 MCP server。

适用配置：

```json
{
  "mcpServers": {
    "didi-mcp": {
      "url": "https://mcp.example.com/mcp-servers?key=${MCP_KEY}"
    }
  }
}
```

注意：

```text
真实 key 只能放本地 myagent.json 或环境变量，不能提交到 Git。
```

新增/修改文件：

```text
myagent/mcp/http.py
myagent/mcp/config.py
myagent/mcp/__init__.py
myagent/cli/commands.py
pyproject.toml
tests/test_mcp_http.py
tests/test_mcp_config.py
```

### HttpMcpClient

`HttpMcpClient` 支持：

```text
connect()
list_tools()
call_tool(name, arguments)
close()
```

HTTP 请求使用：

```text
POST <url>
Accept: application/json, text/event-stream
Content-Type: application/json
```

支持两类响应：

```text
application/json
text/event-stream
```

如果返回 SSE，第一版会解析 `data:` 行里的 JSON-RPC response。

### CLI 自动选择 client

CLI 启动时：

```text
如果 config 有 url -> HttpMcpClient
否则使用 command -> StdioMcpClient
```

然后统一：

```text
list_tools
register_mcp_tools
AgentLoop(tool_registry=registry)
```

### 当前限制

当前 HTTP MCP 是最小实现：

- 不处理复杂 session id。
- 不处理 server 主动发起的 request。
- 不处理长连接事件流。
- 不处理 OAuth。
- 不做重连。
- 不做 secret placeholder 展开。

如果远程 server 要求额外 header、session 管理或认证流程，需要后续扩展。

### 测试说明

`tests/test_mcp_http.py` 使用 `httpx.MockTransport`，不会真实联网。

覆盖：

- JSON response 的 initialize / tools/list / tools/call
- SSE response 的解析

验证结果：

```text
python -m pytest
76 passed, 1 skipped
```

## Phase 2 External Research

本轮 MCP 复盘先参考外部资料，再决定 MyAgent 要做什么。

### 参考来源

- MCP 官方规范：`modelcontextprotocol.io`
- OpenAI Agents SDK MCP 文档：`openai.github.io/openai-agents-python/mcp/`

### 外部做法摘要

MCP 官方规范把 MCP 设计成 client 和 server 之间的 JSON-RPC 协议。对 MyAgent 最相关的是：

- 工具能力使用 `tools/list` 发现，使用 `tools/call` 调用。
- server 还可以提供 resources 和 prompts，但 MyAgent 当前只接 tools。
- 官方传输层重点包括 stdio 和 Streamable HTTP。
- 老式 HTTP+SSE transport 在新规范里属于旧方案，后续应避免继续围绕它做复杂增强。
- client/server 初始化后有 capabilities 协商，后续如果要支持 resources/prompts/sampling，需要从 capabilities 边界开始设计。

OpenAI Agents SDK 的 MCP 支持给 MyAgent 的启发更直接：

- Agent 可以挂多个 MCP server，server 暴露的 tools 会并入 Agent tools。
- tool 名称需要避免冲突。SDK 有 server name prefix 这类机制。
- tool list 可能需要 cache，因为每次 list tools 都有延迟和成本。
- MCP server 调用需要能进入 tracing，方便知道模型为什么调用某个外部工具。
- 实际项目需要 tool filtering，避免把过多、不该用的工具暴露给模型。
- MCP 连接生命周期最好由一个 manager/context 管理，避免进程或 HTTP client 泄漏。
- MCP 工具调用失败时，不应该让整个 Agent 崩掉；应把错误以可理解方式返回给模型和用户。

## Phase 2 Review

### 当前实现

MyAgent 当前 MCP 已经支持两类接入：

```text
StdioMcpClient
HttpMcpClient
```

stdio 流程：

```text
create subprocess
-> initialize
-> notifications/initialized
-> tools/list
-> tools/call
```

HTTP 流程：

```text
POST <url>
Accept: application/json, text/event-stream
Content-Type: application/json
-> initialize
-> tools/list
-> tools/call
```

工具接入方式：

```text
McpToolDefinition
-> McpToolAdapter
-> ToolRegistry.register(...)
-> AgentLoop 使用统一 ToolRegistry
```

命名策略已经有：

```text
mcp_{server_name}_{tool_name}
```

这点和外部框架的实践一致：需要 prefix 避免不同 server、不同本地工具之间冲突。

### 和原设计的差异

原设计第一阶段只计划做 stdio MCP。

当前实现已经额外支持了 URL 型 HTTP MCP，这是实际测试需要推动出来的能力。它是有价值的，但文档口径要明确：当前 HTTP 支持仍是最小实现，不等于完整生产级 Streamable HTTP client。

另外，早期文档把 SSE 放在“暂不做”里，但当前 HTTP client 已经能解析 `text/event-stream` response。这个能力应描述为兼容部分 SSE response，而不是完整长连接 SSE transport。

### 当前问题

1. 缺少 MCP server 状态可观测性。

当前 CLI 只会显示连接成功或失败：

```text
Connected MCP server didi-mcp with 13 tools.
```

但没有更细的 inspect 能力，例如：

```text
server name
transport
tool count
registered tool names
last error
```

2. 缺少 tool filtering。

现在一个 MCP server 暴露多少工具，MyAgent 就注册多少。随着外部 server 增多，模型上下文里的 tool schema 会膨胀，也会增加误调用概率。

3. HTTP MCP 仍是最小实现。

当前不处理：

- session id
- auth / OAuth
- headers 配置
- reconnect
- server 主动 request
- 长连接事件流

4. MCP tool result 只压成文本。

当前 `_content_to_text(...)` 只保留 text 或 JSON 字符串化，足够第一版使用，但还不适合处理 image/resource link/structured content。

5. trace 里没有 MCP 专属视角。

工具调用 trace 能看到 tool name，但没有单独记录：

```text
mcp server
original tool name
transport
```

排查“为什么调用了这个 MCP 工具”时还不够直观。

### 二期建议

短期建议优先做文档和轻量可观测性，而不是继续扩展协议面。

优先级 1：

- 增加 MCP connection summary：启动时记录每个 server 的 transport、tool count、registered tool names。
- 把 MCP register 结果写入 trace，便于复盘工具列表。
- 在 `McpToolAdapter` 的 description 里补充 server 来源，帮助模型区分本地工具和外部工具。

优先级 2：

- 配置层支持 `enabled` / `disabled`。
- 配置层支持简单 `include_tools` / `exclude_tools`。
- 避免所有 MCP tools 无条件暴露给模型。

优先级 3：

- HTTP config 支持 headers。
- 为 HTTP MCP 增加更清楚的错误提示。
- 如果真实 server 需要 session id，再设计 session manager。

暂时不建议马上做：

- OAuth
- resource / prompt / sampling
- 完整长连接 SSE
- MCP server 自动安装
- 图形化权限 UI

这些属于生产级复杂度，不是当前个人助理第二轮最优先的瓶颈。

### 暂不处理

当前先不把 MCP 做成完整平台。

MyAgent 的定位仍然是个人助理 runtime。MCP 在这里的目标是：

```text
让外部工具稳定、安全、可观察地进入 Agent 工具层。
```

不是：

```text
实现完整 MCP host 的全部规范能力。
```

### 测试计划

继续保留当前测试：

```text
tests/test_mcp_stdio.py
tests/test_mcp_http.py
tests/test_mcp_config.py
tests/test_mcp_adapter.py
tests/test_mcp_registry.py
```

如果后续做 MCP Phase 2A，建议新增：

- register summary 测试
- include/exclude tools 配置测试
- adapter description 包含 server 来源测试
- MCP 连接失败不会阻塞 CLI 启动测试

### 面试表达更新

可以这样解释 MCP 模块：

```text
MyAgent 没有把所有外部能力都硬编码成本地工具，而是通过 MCP 接入外部 server。
MCP client 负责 initialize、tools/list 和 tools/call。
每个 MCP tool 会被 McpToolAdapter 包装成统一 ToolRegistry 里的 Tool。
AgentLoop 不需要知道工具来自本地还是 MCP，所有工具都走同一套 schema、参数校验和执行流程。
为了避免命名冲突，MCP tool 会加 server 前缀。
第二阶段我重点关注可观测性和工具过滤，因为 MCP server 一多，最先出现的问题不是协议不够全，而是工具太多、来源不清楚、失败不好排查。
```

## MCP Phase 2A Implementation Note

本阶段先落地最小可观测性，不扩展 MCP 协议面。

新增：

```text
McpRegistrationSummary
register_mcp_tools_with_summary(...)
```

summary 字段：

```text
server_name
transport
tool_count
registered_tool_names
```

`register_mcp_tools(...)` 保留原行为，继续返回 registered tool names，避免破坏已有调用方。

CLI 连接 MCP server 成功后，现在会打印：

```text
MyAgent: Connected MCP server didi-mcp (http) with 13 tools: mcp_didi_xxx, ...
```

`McpToolAdapter.description` 也会带上 server 来源：

```text
Search repository issues. (MCP server: github.)
```

这样模型和调试者都能更容易区分本地工具与外部 MCP 工具。

当前还没有把 summary 写入 trace。原因是 MCP server 连接发生在 `AgentLoop` 启动前，而当前 trace 是 session/turn 维度。后续如果要记录启动期 trace，应先设计 runtime-level trace 或 startup diagnostics。

## MCP Phase 2B Implementation Note

本阶段继续补齐 MCP 工具过滤和启动期持久记录。

### 配置字段

`McpServerConfig` 新增：

```text
enabled: bool = true
include_tools: tuple[str, ...] = ()
exclude_tools: tuple[str, ...] = ()
```

JSON 支持 camelCase 和 snake_case：

```json
{
  "mcpServers": {
    "demo": {
      "enabled": true,
      "command": "python",
      "args": ["server.py"],
      "includeTools": ["search", "mcp_demo_read"],
      "excludeTools": ["delete"]
    }
  }
}
```

规则：

- `enabled: false` 的 server 不会连接。
- `includeTools` 非空时，只注册命中的工具。
- `excludeTools` 会排除命中的工具。
- 匹配既支持 MCP 原始工具名，也支持 MyAgent 注册后的安全工具名。

### 注册摘要

`McpRegistrationSummary` 现在记录：

```text
server_name
transport
discovered_tool_count
tool_count
registered_tool_names
skipped_tool_names
```

CLI 输出会显示：

```text
Connected MCP server demo (stdio) with 1/2 tools. Details saved to startup trace.
```

其中 `1/2` 表示注册 1 个、发现 2 个。
交互层不展开完整工具名，避免个人 Agent 启动时刷屏。完整 registered / skipped 工具列表保存在 startup trace 里。

### 启动期 trace

MCP 连接发生在普通对话 turn 之前，因此本轮采用 runtime startup trace：

```text
session_key = runtime:startup
turn_id = startup
event = mcp_server_registered
event = mcp_server_connect_failed
```

默认写入：

```text
data/traces/runtime_startup.jsonl
```

这让用户可以在不进入具体聊天 session 的情况下，复盘启动时 MCP server 连接和工具注册情况。
