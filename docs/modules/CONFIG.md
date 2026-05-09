# Config 模块设计

## 职责

Config 负责把本地 JSON 配置和环境变量统一转换成 MyAgent 运行时可用的 `Settings`。

一句话版本：

```text
Settings 是 CLI 启动运行时时读取 provider 和 MCP 配置的入口。
```

## 为什么需要它

MyAgent 需要在不同场景下切换运行方式：

- 没有 API key 时，用 EchoProvider 跑通本地演示。
- 有 API key 时，用 OpenAI-compatible provider 调真实模型。
- 使用第三方兼容服务时，配置 `baseUrl` 和 `model`。
- 接入 MCP server 时，从配置文件读取 `mcpServers`。
- 临时测试时，用环境变量覆盖本地配置文件。

如果这些逻辑散落在 CLI、Provider、MCP 模块里，后续会很难解释和测试。`Settings` 把配置读取集中起来，保持运行入口清楚。

## 输入输出

输入：

- 默认配置文件：`myagent.json`
- 显式配置路径：`MYAGENT_CONFIG` 或 CLI `--config`
- 环境变量覆盖

输出：

- `Settings.provider`
- `Settings.api_key`
- `Settings.base_url`
- `Settings.model`
- `Settings.system_prompt`
- `Settings.provider_retries`
- `Settings.mcp_servers`

## 配置文件格式

可提交模板是：

```text
myagent.example.json
```

真实本地配置是：

```text
myagent.json
```

`myagent.json` 已在 `.gitignore` 中忽略，不能提交真实 API key、MCP key 或私有 URL。

当前支持的 JSON 结构：

```json
{
  "provider": {
    "mode": "auto",
    "apiKey": "",
    "baseUrl": "",
    "model": "gpt-5.4-mini",
    "systemPrompt": "You are MyAgent, a concise and helpful assistant.",
    "retries": 2
  },
  "mcpServers": {}
}
```

MCP stdio 示例：

```json
{
  "mcpServers": {
    "demo": {
      "command": "python",
      "args": ["server.py"],
      "env": {"TOKEN": "replace-me"}
    }
  }
}
```

MCP HTTP/SSE 风格示例：

```json
{
  "mcpServers": {
    "remote-demo": {
      "url": "https://example.test/mcp"
    }
  }
}
```

真实 token 应放在本地 `myagent.json` 或环境变量里，不能写进可提交模板。

## 环境变量

当前支持：

```text
MYAGENT_CONFIG
MYAGENT_PROVIDER
MYAGENT_API_KEY
OPENAI_API_KEY
MYAGENT_BASE_URL
MYAGENT_MODEL
MYAGENT_SYSTEM_PROMPT
MYAGENT_PROVIDER_RETRIES
```

优先级：

```text
环境变量 > 配置文件 > 默认值
```

API key 优先级：

```text
MYAGENT_API_KEY -> OPENAI_API_KEY -> myagent.json
```

## 核心接口

主要入口：

```python
Settings.from_sources(config_path=None)
Settings.from_env()
```

`Settings.from_sources(...)` 会：

1. 解析配置路径。
2. 读取 JSON 配置。
3. 解析 provider 配置。
4. 解析 `mcpServers`。
5. 应用环境变量覆盖。
6. 返回不可变 `Settings` 对象。

## 与其他模块的关系

### CLI Channel

CLI 启动时调用：

```text
Settings.from_sources(config_path)
```

然后创建 provider 和 MCP clients。

### LLM Provider

`create_provider(settings)` 根据：

```text
settings.provider
settings.api_key
```

选择 EchoProvider 或 OpenAICompatibleProvider。

### MCP

`Settings.mcp_servers` 由 `parse_mcp_servers(...)` 生成。

CLI 根据每个 server 配置选择：

```text
url     -> HttpMcpClient
command -> StdioMcpClient
```

### SubAgent

当前 SubAgent 不读取独立配置。

第一版行为：

- profile 写在代码里。
- 子 Agent 使用独立 prompt。
- 子 Agent 与主 Agent 共用 provider。

是否把 SubAgent profile、默认工具集、独立模型配置放进 `myagent.json`，属于 Phase 2 后续决策。

## Phase 2 Review

### 当前实现

当前实现集中在：

```text
myagent/config/settings.py
myagent/mcp/config.py
myagent/providers/base.py
myagent/providers/echo.py
myagent/providers/openai_compatible.py
myagent.example.json
tests/test_llm_provider.py
tests/test_mcp_config.py
```

已支持：

- 默认读取 `myagent.json`。
- 支持 `MYAGENT_CONFIG` 和 CLI `--config` 指定配置文件。
- 支持 provider 的 `mode`、`apiKey`、`baseUrl`、`model`、`systemPrompt`、`retries`。
- 支持环境变量覆盖 provider 配置。
- 支持 `mcpServers`，包括 stdio `command/args/env` 和 HTTP `url`。
- `myagent.json` 已被 `.gitignore` 忽略。

本轮复盘时还修复了一个 provider 导入环：

```text
providers.base / echo / openai_compatible
```

这些 provider 模块之前为了类型标注导入 `myagent.agent.context.Message`，在测试单独导入 provider 包时会触发 `agent.__init__ -> AgentLoop -> providers` 的循环导入。现在 provider 层在 `providers.base` 内部定义自己的 `Message` 类型别名，不再依赖 agent 包初始化。

### 和原设计的差异

早期架构文档提到过：

```text
MYAGENT_MAX_ITERATIONS
MYAGENT_WORKSPACE
```

当前 `Settings` 尚未支持这两个字段。实际运行中最大迭代次数和 workspace 仍由其他模块默认值或调用方处理，不属于当前配置文件能力。

早期 SubAgent 文档提到“独立模型配置”，但当前 SubAgent 仍与主 Agent 共用 provider。

### 当前问题

- `myagent.example.json` 之前没有体现 `mcpServers`，容易让人误以为 MCP 配置没有纳入 Settings。
- Config 没有独立模块文档，配置行为散落在 LLM Provider、MCP 和 Phase 2 计划里。
- 真实 `myagent.json` 可能包含 API key 或 MCP key，必须持续保持未跟踪状态。
- SubAgent profile 是否配置化尚未决策。
- 暂无配置 schema 校验；非法字段大多会被忽略或回落到默认值。

### 二期建议

当前建议先做轻量增强：

- 保持 `Settings` 简单，不急着引入复杂配置框架。
- 给 Config 建立独立模块文档，作为 provider / MCP / SubAgent 配置口径的统一入口。
- 在 `myagent.example.json` 增加空的 `mcpServers` 字段，提示用户 MCP 配置位置。
- 先不把 SubAgent profile 配置化，等 SubAgent 复盘时再决定。
- 后续如果加入写文件、exec、web_search，再统一设计权限和确认配置。

### 暂不处理

暂不实现：

- 配置迁移系统。
- 多环境配置目录。
- 完整 JSON Schema 校验。
- secret manager。
- provider registry。
- SubAgent 独立模型配置。
- workspace / max_iterations 的配置化迁移。

### 测试计划

已有测试覆盖：

- 从 JSON 读取 provider 配置。
- 环境变量覆盖 JSON。
- `MYAGENT_API_KEY` 优先于 `OPENAI_API_KEY`。
- `OPENAI_API_KEY` 兜底。
- auto/openai/echo provider 选择。
- 从 JSON 读取 stdio MCP server。
- 解析 URL 型 MCP server。

本轮已执行：

```text
python -m json.tool myagent.example.json
python -m pytest tests/test_llm_provider.py tests/test_mcp_config.py
python -m pytest
```

结果：

```text
15 passed
80 passed, 1 skipped
```

跳过项仍是 Windows 环境下可能受限的 `tests/test_mcp_stdio.py`。

如果后续扩展 Config，应补测试：

- 示例配置里的 `mcpServers` 空对象不会注册 server。
- SubAgent profile 配置解析。
- 配置校验错误提示。
- secret placeholder 展开策略。

### MCP Phase 2B 配置更新

MCP server 配置已支持轻量开关和工具过滤：

```json
{
  "mcpServers": {
    "demo": {
      "enabled": true,
      "command": "python",
      "args": ["server.py"],
      "includeTools": ["search"],
      "excludeTools": ["delete"]
    }
  }
}
```

字段说明：

- `enabled: false`：跳过该 MCP server，不连接、不注册工具。
- `includeTools` / `include_tools`：只注册指定工具。
- `excludeTools` / `exclude_tools`：排除指定工具。
- 工具过滤支持匹配 MCP 原始工具名，也支持匹配 MyAgent 注册后的 `mcp_{server}_{tool}` 名。

这属于 MCP 工具面控制，不是安全权限系统。真正的工具安全仍应由具体 MCP server 和 MyAgent 工具边界共同保证。

### 面试表达更新

可以这样讲：

> MyAgent 的配置层故意保持很薄。Settings 只负责把 JSON 和环境变量合并成运行时需要的字段，Provider 和 MCP 再各自消费这些字段。这样既能支持真实模型和 MCP server，又不会为了第一版演示引入复杂配置系统。

如果被问到为什么不做完整配置 schema，可以回答：

> 当前项目目标是轻量、可教学、可面试。第一版配置字段少，单元测试已经覆盖主要路径。完整 schema、迁移和 secret manager 更像生产级需求，后续等配置面扩大后再加更合适。
