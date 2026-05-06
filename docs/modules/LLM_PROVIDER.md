# LLM Provider 模块设计

## 职责

LLM Provider 负责把 MyAgent 的内部消息转换成模型 API 调用，并把模型回复转换回 AgentLoop 可使用的文本结果。

一句话版本：

```text
AgentLoop 不直接调用 OpenAI SDK，而是通过 Provider 接口生成回复。
```

## 为什么需要它

如果 AgentLoop 直接写 OpenAI SDK 调用，会有几个问题：

1. AgentLoop 会和某一个 SDK 绑定太死。
2. 后续替换模型供应商或本地模型时要改 AgentLoop。
3. 测试 AgentLoop 时必须依赖真实网络/API key。
4. EchoProvider 这种测试替身不好接入。

引入 Provider 层后：

```text
AgentLoop -> Provider -> Model API
```

AgentLoop 只依赖统一接口，不关心底层是 EchoProvider、OpenAI-compatible API，还是以后其他模型。

## 参考资料

本模块参考 OpenAI 官方文档：

- Chat Completions API 支持 `messages`、`tools`、`tool_choice` 等参数。
- 当前官方模型页建议复杂推理/编码使用 `gpt-5.5`，低延迟低成本场景可选较小模型如 `gpt-5.4-mini`。

MyAgent 第一阶段选择 `gpt-5.4-mini` 作为默认模型，理由是它更适合本项目的本地演示和成本控制。用户可以通过环境变量覆盖。

## 第一阶段定位

第一阶段只做文本回复闭环。

实现：

- `BaseProvider`
- `EchoProvider`
- `OpenAICompatibleProvider`
- `Settings`
- CLI 自动选择 provider

暂不实现：

- tool calling 解析
- streaming
- multimodal
- provider registry
- OAuth provider
- LiteLLM
- 复杂 retry/backoff
- token usage 统计

## 所属架构层

LLM Provider 属于 `Intelligence Layer`。

它位于：

```text
AgentLoop
  ↓
LLM Provider
  ↓
Model API
```

对应数据流：

```text
Messages
  ↓
AgentLoop
  ↓ provider.generate()
OpenAICompatibleProvider
  ↓
OpenAI-compatible API
  ↓
assistant text
  ↓
OutboundMessage
```

## Provider 接口

第一阶段统一接口：

```text
generate(messages: list[dict[str, str]]) -> str
```

这个接口很薄，刚好满足当前 AgentLoop 和 ContextBuilder。

后续接入 tools 后，会升级为：

```text
generate(messages, tools=None) -> ProviderResponse
```

第一阶段先不提前设计复杂 response 对象。

## EchoProvider

EchoProvider 是无网络测试替身。

用途：

- 默认兜底。
- 没有 API key 也能运行。
- 测试 AgentLoop 不需要真实模型。

行为：

```text
Echo: <用户输入>
```

## OpenAICompatibleProvider

OpenAICompatibleProvider 使用 `openai` Python SDK 的 `AsyncOpenAI`。

第一阶段调用 Chat Completions：

```text
client.chat.completions.create(
    model=model,
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": message.content},
    ],
)
```

选择 Chat Completions 的原因：

- OpenAI 官方仍提供该 API。
- 对 OpenAI-compatible 第三方服务最常见。
- 后续 tool calling 也可以从这里继续扩展。

## 配置设计

第一阶段配置支持两种来源：

1. 配置文件
2. 环境变量覆盖

默认配置文件：

```text
myagent.json
```

也可以通过环境变量指定：

```text
MYAGENT_CONFIG=path/to/myagent.json
```

优先级：

```text
环境变量 > 配置文件 > 默认值
```

这样日常使用可以写配置文件，临时测试可以用环境变量覆盖。

配置文件示例：

```json
{
  "provider": {
    "mode": "auto",
    "apiKey": "",
    "baseUrl": "",
    "model": "gpt-5.4-mini",
    "systemPrompt": "You are MyAgent, a concise and helpful assistant.",
    "retries": 2
  }
}
```

实际密钥文件 `myagent.json` 不提交到 Git，只提交 `myagent.example.json` 模板。

环境变量：

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

### MYAGENT_PROVIDER

可选值：

```text
auto
echo
openai
```

默认：

```text
auto
```

规则：

- `echo`：强制使用 EchoProvider。
- `openai`：强制使用 OpenAICompatibleProvider，没有 API key 就报错。
- `auto`：有 API key 用 OpenAICompatibleProvider，没有 API key 用 EchoProvider。

### API key

优先级：

```text
MYAGENT_API_KEY -> OPENAI_API_KEY
```

这样既支持 MyAgent 自己的命名，也兼容 OpenAI 常见环境变量。

### MYAGENT_BASE_URL

可选。

如果设置，就传给 `AsyncOpenAI(base_url=...)`。

用于兼容：

- OpenAI 官方 API 代理
- OpenAI-compatible 第三方服务
- 本地兼容服务

### MYAGENT_MODEL

默认：

```text
gpt-5.4-mini
```

用户可以覆盖：

```text
MYAGENT_MODEL=gpt-5.5
```

或第三方模型名。

### MYAGENT_SYSTEM_PROMPT

第一阶段的简单 system prompt。

默认：

```text
You are MyAgent, a concise and helpful assistant.
```

后续 ContextBuilder 会接管 system prompt 组装。

## 与其他模块的关系

### AgentLoop

AgentLoop 依赖 provider 接口：

```text
await provider.generate(messages)
```

AgentLoop 不直接依赖 OpenAI SDK。

### CLI Channel

CLI Channel 不直接依赖 provider。

但 CLI 启动本地运行时的时候，会通过 provider factory 选择 Echo 或 OpenAI provider。

### ContextBuilder

当前 provider 直接构造最小 messages。

后续 ContextBuilder 出现后，会由 ContextBuilder 生成 messages，Provider 只负责发送。

### ToolRegistry

当前不接 tools。

后续 tool schema 会通过 Provider 传给模型。

## 第一阶段范围

第一阶段只实现：

- 配置文件 + 环境变量 Settings
- provider 选择逻辑
- EchoProvider 保留
- OpenAI-compatible 文本生成
- 简单 retry
- 基础测试

## 暂不实现

第一阶段暂不实现：

- streaming
- tool calling
- JSON schema response
- usage 统计
- provider registry
- 多模型配置
- summary/subagent 模型
- OAuth 登录
- 复杂错误分类

## 最小测试点

建议测试文件：

```text
tests/test_llm_provider.py
```

测试点：

1. `test_settings_reads_myagent_api_key`
   - 能从环境变量读取 API key。

2. `test_settings_falls_back_to_openai_api_key`
   - 未设置 `MYAGENT_API_KEY` 时使用 `OPENAI_API_KEY`。

3. `test_create_provider_auto_without_key_returns_echo`
   - auto 模式无 key 使用 EchoProvider。

4. `test_create_provider_auto_with_key_returns_openai_provider`
   - auto 模式有 key 使用 OpenAICompatibleProvider。

5. `test_openai_provider_generates_text_from_fake_client`
   - 使用 fake client 测试 provider 能接收 messages 并提取 assistant content。

6. `test_openai_provider_retries_then_succeeds`
   - 第一次失败、第二次成功时能返回结果。

## 面试表达

可以这样讲：

> 我没有让 AgentLoop 直接依赖 OpenAI SDK，而是抽了一层 Provider。这样 EchoProvider 可以作为本地测试替身，OpenAICompatibleProvider 可以作为真实模型接入，后续如果要接本地模型或其他供应商，也不需要改 AgentLoop。

如果面试官问“为什么默认还能 Echo”，可以回答：

> 因为这个项目强调可教学和可演示。没有 API key 时系统仍然能跑通主链路；有 API key 时再切到真实模型。这样可以把框架正确性和外部服务可用性分开。

如果面试官问“为什么先用 Chat Completions”，可以回答：

> 第一阶段只需要文本回复，而且 Chat Completions 在 OpenAI-compatible 生态里支持最广。后续如果要做更完整的 agentic workflow，可以再评估 Responses API 或更高层的 Agents SDK。

## 后续扩展方向

后续可以增强：

- ProviderResponse 数据结构
- tool calling 解析
- stream 输出
- usage/token 统计
- summary model / subagent model 配置
- provider registry
- LiteLLM 兼容层
- Responses API provider
- 模型能力检测
- 更完整 retry/backoff
- 错误类型标准化

## 第一阶段实现说明

本次已经完成 LLM Provider 的第一阶段实现。

实现目标：

```text
没有 API key 时继续 Echo；有 API key 时自动切换到 OpenAI-compatible Provider。
```

相关文件：

```text
myagent/config/__init__.py
myagent/config/settings.py
myagent/providers/base.py
myagent/providers/echo.py
myagent/providers/openai_compatible.py
myagent/providers/__init__.py
myagent/agent/loop.py
myagent/cli/commands.py
tests/test_llm_provider.py
```

### config/settings.py

`Settings` 是第一阶段的轻量配置对象。

它从配置文件和环境变量读取。

默认会尝试读取：

```text
myagent.json
```

也可以通过：

```text
MYAGENT_CONFIG
```

指定配置文件路径。

配置文件格式：

```json
{
  "provider": {
    "mode": "auto",
    "apiKey": "",
    "baseUrl": "",
    "model": "gpt-5.4-mini",
    "systemPrompt": "You are MyAgent, a concise and helpful assistant.",
    "retries": 2
  }
}
```

环境变量：

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

默认模型：

```text
gpt-5.4-mini
```

默认 provider 模式：

```text
auto
```

`api_key` 读取优先级：

```text
MYAGENT_API_KEY -> OPENAI_API_KEY -> myagent.json
```

这个设计让 MyAgent 既能长期使用配置文件，也能临时用环境变量覆盖。

### providers/base.py

`BaseProvider` 是一个 `Protocol`。

它规定第一阶段 provider 只需要实现：

```text
generate(messages: list[Message]) -> str
```

AgentLoop 只依赖这个接口。

### providers/openai_compatible.py

`OpenAICompatibleProvider` 使用：

```text
openai.AsyncOpenAI
```

构造时需要：

```text
Settings(api_key=...)
```

如果没有 API key，会抛出 `ValueError`。

生成回复时调用：

```text
client.chat.completions.create(...)
```

messages 第一阶段只有两条：

```text
system: settings.system_prompt
user: message.content
```

然后取：

```text
completion.choices[0].message.content
```

作为返回文本。

### 简单 retry

`OpenAICompatibleProvider.generate` 会按：

```text
settings.provider_retries
```

重试。

第一阶段只是简单重试，没有指数退避、错误分类、限流处理。

这样做是为了先满足演示和本地开发，不提前引入复杂工程化。

### providers/__init__.py

这里提供：

```text
create_provider(settings)
```

选择规则：

```text
provider = "echo"   -> EchoProvider
provider = "openai" -> OpenAICompatibleProvider
provider = "auto"   -> 有 API key 用 OpenAI，否则 Echo
```

如果传入未知 provider mode，会抛出 `ValueError`。

### AgentLoop 更新

`AgentLoop` 现在依赖 `BaseProvider`，默认通过：

```text
create_provider()
```

创建 provider。

这意味着：

- 没配置 API key：仍然 Echo。
- 配置 API key：自动真实模型。

### CLI 更新

CLI 的 `run_local_chat` 会读取：

```text
Settings.from_env()
```

然后调用：

```text
create_provider(settings)
```

所以终端运行时不需要改代码，只要设置环境变量即可切换 provider。

## 如何手动测试

### 默认 Echo 模式

不设置 API key，运行：

```text
python -m myagent
```

输入：

```text
hello
/stop
```

会得到：

```text
MyAgent: Echo: hello
```

### OpenAI-compatible 模式

PowerShell 示例：

```powershell
Copy-Item myagent.example.json myagent.json
# 编辑 myagent.json，填入 provider.apiKey
python -m myagent
```

如果使用兼容接口：

```powershell
# 在 myagent.json 里设置 provider.baseUrl 和 provider.model
python -m myagent
```

如果想强制 Echo：

```powershell
$env:MYAGENT_PROVIDER="echo"
python -m myagent
```

如果想强制 OpenAI provider：

```powershell
$env:MYAGENT_PROVIDER="openai"
python -m myagent
```

强制 `openai` 但没有 API key 时会报错，这是预期行为。

也可以指定配置文件路径：

```powershell
$env:MYAGENT_CONFIG="configs/dev.json"
python -m myagent
```

## tests/test_llm_provider.py

测试覆盖：

1. `MYAGENT_API_KEY` 优先级高于 `OPENAI_API_KEY`。
2. 未设置 `MYAGENT_API_KEY` 时回退到 `OPENAI_API_KEY`。
3. 能从 JSON 配置文件读取 provider 配置。
4. 环境变量优先级高于配置文件。
5. auto 模式无 key 返回 EchoProvider。
6. auto 模式有 key 返回 OpenAICompatibleProvider。
7. openai 模式无 key 会报错。
8. 未知 provider mode 会报错。
9. fake client 能验证 OpenAI provider 接收 messages 并提取 assistant content。
10. fake client 能验证简单 retry。

测试没有调用真实网络。

## 本次验证结果

已执行：

```text
python -m pytest
```

结果：

```text
29 passed
```

也执行了默认 Echo smoke test：

```text
"hello`n/stop`n" | python -m myagent
```

结果：

```text
MyAgent CLI is ready. Type /help for commands.
You: MyAgent: Echo: hello
You: Stopping MyAgent CLI.
```

## 如何阅读这部分代码

建议按这个顺序读：

1. `myagent/config/settings.py`
2. `myagent/providers/base.py`
3. `myagent/providers/echo.py`
4. `myagent/providers/openai_compatible.py`
5. `myagent/providers/__init__.py`
6. `myagent/agent/loop.py`
7. `tests/test_llm_provider.py`

读代码时抓住主线：

```text
Settings -> create_provider -> AgentLoop.provider.generate()
```

这就是模型接入层的核心。

## 当前代码的边界

当前已经能接真实 OpenAI-compatible 文本模型。

但还没有：

- conversation history
- ContextBuilder
- tool calling
- streaming
- Trace
- Memory

下一步建议做 ContextBuilder，让 provider 不再只收到单条用户消息，而是收到结构化上下文。
