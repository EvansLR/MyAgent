# CLI Channel 模块设计

## 职责

CLI Channel 是 MyAgent 第一阶段的用户入口。

一句话版本：

```text
CLI Channel 把用户在命令行输入的文本转换成 InboundMessage，并把 OutboundMessage 打印回终端。
```

它只负责“收消息”和“发消息”，不负责 LLM、不负责工具调用、不负责 Agent 决策。

## 当前状态速览

这份文档前半部分保留了 CLI Channel 第一阶段的设计口径，用来解释它为什么从
最轻量的本地命令行入口开始。

但当前真实实现已经进入 Phase 2 的交互增强阶段，CLI 已经不只是简单打印文本：

- 继续支持 `/help`、`/new`、`/stop`。
- 未知 slash command 不再进入模型，而是直接提示 `/help`。
- 会消费 `metadata.kind = "status"` 的中间状态消息。
- 使用 Rich spinner 展示工具调用状态。
- 使用 Rich Markdown 渲染最终回答。
- 当文件工具触及工作区外变更路径时，会展示审批请求并收集 Yes/No。

当前边界：

- 仍然是单用户本地 CLI。
- 不做复杂 TUI。
- 不做多通道统一命令层。
- 不把子 Agent 内部所有工具调用默认刷到终端。

## 为什么需要它

MyAgent 需要一个最简单的交互入口来验证 Agent runtime 是否能跑起来。

第一阶段选择 CLI，而不是 Web UI 或 IM 通道，原因是：

- CLI 开发成本低。
- 本地测试方便。
- 不需要账号、token、回调地址。
- 面试演示时可以直接运行。
- 足够验证 MessageBus、AgentLoop、Provider、Tools 的主链路。

## 参考 NanoBot 的取舍

NanoBot 的 CLI 功能比较完整：

- `typer` 子命令
- `prompt_toolkit` 输入体验
- `rich` Markdown 渲染
- 配置初始化
- provider 登录
- trace 命令
- gateway 命令
- channel/plugin 管理

MyAgent 第一阶段只保留核心交互能力：

- `typer` 提供命令入口。
- 普通输入循环读取用户文本。
- 支持 `/new`、`/stop`、`/help`。
- 把普通文本封装成 `InboundMessage`。
- 从 MessageBus 消费 `OutboundMessage` 并打印。
- 使用 Rich 展示工具调用状态和 Markdown 最终回答。

暂不引入 `prompt_toolkit`、多子命令和复杂配置。

## 所属架构层

CLI Channel 属于 `Interface Layer`。

它位于：

```text
User
  ↓
Interface Layer: CLI Channel
  ↓
Message Layer: MessageBus
```

对应数据流：

```text
用户输入
  ↓
CLI Channel
  ↓ publish_inbound(InboundMessage)
MessageBus
  ↓
AgentLoop
  ↓
MessageBus
  ↓ consume_outbound()
CLI Channel
  ↓
终端输出
```

## 输入输出

### 输入

CLI Channel 接收两类输入：

1. 普通文本
2. slash command

普通文本示例：

```text
你好，帮我总结一下当前项目结构
```

slash command 示例：

```text
/help
/new
/stop
```

### 输出

CLI Channel 输出两类内容：

1. Agent 回复
2. CLI 自己处理的命令提示

Agent 回复来自：

```text
OutboundMessage.content
```

CLI 自己处理的命令提示比如：

```text
Started a new session: cli:session-20260505-001
```

## 命令设计

第一阶段支持三个命令。

### /help

显示可用命令。

不进入 AgentLoop。

### /new

创建新的本地会话。

行为：

- 更新当前 `chat_id`
- 后续普通输入使用新的 `session_key`

第一阶段不做持久化 session，只在当前进程内切换。

### /stop

停止 CLI 输入循环。

行为：

- 退出当前 chat loop
- 结束程序

注意：

- 第一阶段 `/stop` 只停止 CLI。
- 后续如果 AgentLoop 支持任务取消，再扩展为取消正在运行的 turn。

## 核心接口

第一阶段建议拆成两层，方便测试。

### 纯逻辑函数

```text
parse_cli_command(raw: str) -> CliCommand
make_inbound_message(content: str, state: CliState) -> InboundMessage
make_help_text() -> str
```

这些函数不直接读写终端，适合单元测试。

### 运行时函数

```text
run_chat(bus: MessageBus) -> None
```

职责：

- 循环读取用户输入
- 处理 slash command
- 发布普通消息到 MessageBus
- 等待 outbound 消息并打印

后续和 AgentLoop 集成时，可能会变成：

```text
async run_chat(bus: MessageBus) -> None
```

## 数据结构

### CliState

CLI 需要保存当前本地状态。

建议字段：

```text
sender_id: str
chat_id: str
session_index: int
running: bool
```

第一阶段默认值：

```text
sender_id = "local-user"
chat_id = "default"
session_index = 0
running = True
```

### CliCommand

表示解析后的命令。

建议字段：

```text
name: str
raw: str
```

或者第一阶段更简单，直接用字符串枚举：

```text
"help"
"new"
"stop"
"message"
```

为了保持轻量，第一阶段可以不引入复杂 command class。

## 与其他模块的关系

### MessageBus

CLI Channel 直接依赖 MessageBus。

普通输入会变成：

```text
InboundMessage(
    channel="cli",
    sender_id="local-user",
    chat_id=current_chat_id,
    content=user_text,
)
```

Agent 输出会从：

```text
bus.consume_outbound()
```

取得。

### AgentLoop

CLI Channel 不直接依赖 AgentLoop。

正确关系是：

```text
CLI Channel -> MessageBus <- AgentLoop
```

这样未来换成 Web UI 或 IM Channel 时，不需要改 AgentLoop。

### Session

CLI Channel 不直接管理 Session。

它只负责生成不同的 `chat_id`。真正的 session history 后续由 AgentLoop/SessionManager 管。

## 第一阶段范围

第一阶段只实现：

- Typer 应用入口
- `python -m myagent` 进入 CLI
- 普通文本输入
- `/help`
- `/new`
- `/stop`
- 将普通输入封装成 `InboundMessage`
- 打印 `OutboundMessage.content`

但需要注意：如果还没有 AgentLoop，CLI 不能真正得到模型回复。

因此实现可以分两步：

1. 先实现可测试的 CLI 逻辑函数。
2. 等最小 AgentLoop/EchoProvider 出现后，再把完整 chat loop 跑通。

## 暂不实现

第一阶段暂不实现：

- 输入历史
- 自动补全
- 多行输入
- Markdown 渲染
- 彩色 UI
- 配置初始化向导
- provider 登录
- trace 子命令
- shell 命令模式
- IM 通道适配
- 后台任务取消

这些功能都可以后续从 NanoBot 借鉴，但当前会干扰第一阶段主链路。

## 最小测试点

建议测试文件：

```text
tests/test_cli_channel.py
```

测试点：

1. `test_parse_help_command`
   - 输入 `/help` 识别为 help。

2. `test_parse_new_command`
   - 输入 `/new` 识别为 new。

3. `test_parse_stop_command`
   - 输入 `/stop` 识别为 stop。

4. `test_parse_plain_text_as_message`
   - 输入普通文本识别为 message。

5. `test_make_inbound_message_uses_current_cli_state`
   - 当前 `chat_id` 会进入 `InboundMessage`。

6. `test_new_session_changes_chat_id`
   - 执行 `/new` 后，`chat_id` 从 `default` 变成新 session。

7. `test_help_text_mentions_supported_commands`
   - help 文本包含 `/new`、`/stop`、`/help`。

如果实现了完整 chat loop，可以再加集成测试；第一阶段先保证纯逻辑可测。

## 面试表达

可以这样讲：

> 我把 CLI 设计成一个 Channel，而不是让它直接调用 AgentLoop。CLI 只负责把用户输入转换成统一的 `InboundMessage`，再从 MessageBus 取 `OutboundMessage` 打印。这样 AgentLoop 不需要知道消息来自命令行、Web UI 还是 IM 通道，后续扩展其他入口时成本更低。

如果面试官问“为什么不用 Web UI”，可以回答：

> 第一阶段目标是验证 Agent runtime 的核心链路。CLI 的开发成本最低，也最适合本地演示。Web UI 会引入前端、服务端、状态同步等额外复杂度，当前不是核心问题。

如果面试官问“为什么不用 prompt_toolkit/rich”，可以回答：

> 这些库能改善体验，但不影响 Agent runtime 的核心设计。MyAgent 当前强调可教学和可面试，所以先保留最小 CLI，后续可以再逐步增强输入体验和输出渲染。

## 后续扩展方向

后续可以增强：

- 使用 `prompt_toolkit` 支持输入历史、多行粘贴、快捷键。
- 使用 `rich` 渲染 Markdown。
- 增加 `myagent chat`、`myagent trace`、`myagent memory` 子命令。
- 支持 `/trace` 查看当前 turn trace。
- 支持 `/memory` 查看或写入 memory。
- 支持 `/model` 临时切换模型。
- 支持 `/cancel` 取消正在运行的任务。
- 支持从 CLI 切换 workspace。

这些都属于体验增强，不影响第一阶段核心闭环。

## 第一阶段实现说明

本次已经完成 CLI Channel 的第一阶段逻辑实现。

实现目标：

```text
先建立可测试的 CLI 输入解析、会话状态和消息转换逻辑。
```

相关文件：

```text
myagent/__main__.py
myagent/cli/__init__.py
myagent/cli/commands.py
tests/test_cli_channel.py
```

### __main__.py

`myagent/__main__.py` 是模块入口。

当执行：

```text
python -m myagent
```

它会调用：

```text
myagent.cli.commands.app
```

也就是 Typer CLI 应用。

当前输出：

```text
MyAgent CLI is ready.
MyAgent commands:
  /help  Show this help message.
  /new   Start a new local session.
  /stop  Exit the CLI.
```

注意：当前已经接入最小 chat loop，但回复来自临时 EchoProvider，不是真实 LLM。

### commands.py

`myagent/cli/commands.py` 是 CLI Channel 的核心代码。

它现在分成三类内容：

1. CLI 状态
2. 纯逻辑函数
3. Typer 入口

### CliState

`CliState` 保存 CLI 当前会话状态。

字段：

```text
sender_id
chat_id
session_index
running
```

默认值：

```text
sender_id = "local-user"
chat_id = "default"
session_index = 0
running = True
```

它有一个方法：

```text
start_new_session()
```

调用后：

```text
session_index += 1
chat_id = f"session-{session_index}"
```

所以第一次 `/new` 后：

```text
chat_id = "session-1"
session_key = "cli:session-1"
```

### parse_cli_command

`parse_cli_command(raw: str) -> str` 用来识别用户输入。

规则：

- `/help` -> `"help"`
- `/new` -> `"new"`
- `/stop` -> `"stop"`
- 其他输入 -> `"message"`

第一阶段曾经把未知 slash command 也当成普通 message。

Phase 2 复盘后改为直接提示：

```text
Unknown command. Type /help for supported commands.
```

原因是 `/unknown` 更像用户输入了 CLI 控制命令，而不是想问模型的问题。直接提示能减少手动测试时的困惑。

### make_inbound_message

`make_inbound_message(content, state)` 把用户文本转换为 MessageBus 能理解的格式。

它创建：

```text
InboundMessage(
    channel="cli",
    sender_id=state.sender_id,
    chat_id=state.chat_id,
    content=content,
)
```

这一步很关键，因为它把 CLI 输入和 AgentLoop 解耦。

AgentLoop 后续只需要处理 `InboundMessage`，不用关心这条消息是不是来自命令行。

### make_help_text

`make_help_text()` 返回内置帮助文本。

当前包含：

```text
/help
/new
/stop
```

### handle_cli_command

`handle_cli_command(command, state)` 负责执行 CLI 自己能处理的命令。

目前支持：

- `help`：返回帮助文本。
- `new`：调用 `state.start_new_session()`。
- `stop`：把 `state.running` 设置为 `False`。

这类命令不进入 AgentLoop。

原因是它们是 CLI 控制命令，不是用户要问模型的问题。

### Typer app

当前 Typer app 定义在：

```text
app = typer.Typer(...)
```

入口函数：

```text
@app.callback(invoke_without_command=True)
def main() -> None:
```

第一阶段它会启动本地 Echo chat。

后续接入真实 LLM Provider 后，这里仍然可以作为同一个 CLI 入口。

## 为什么先做纯逻辑，再接完整聊天

完整聊天需要至少三个模块一起工作：

```text
CLI Channel -> MessageBus -> AgentLoop/EchoProvider -> MessageBus -> CLI Channel
```

第一版 CLI 只有 MessageBus 和 CLI Channel，所以先实现可测试的纯逻辑。

现在 AgentLoop/EchoProvider 已经做好，CLI 的 runtime loop 也已经接起来。

这种拆法有两个好处：

- 每一步都能测试。
- 出问题时容易定位是 CLI、MessageBus 还是 AgentLoop 的问题。

## tests/test_cli_channel.py

测试文件验证了 11 个行为：

1. `/help` 能解析为 `help`。
2. `/new` 能解析为 `new`。
3. `/stop` 能解析为 `stop`。
4. 普通文本解析为 `message`。
5. 未知 slash command 解析为 `unknown`。
6. `make_inbound_message` 会使用当前 `CliState`。
7. `/new` 会改变 `chat_id`。
8. `/stop` 会让 `running = False`。
9. help 文本包含 `/help`、`/new`、`/stop`。
10. 未知 slash command 会直接提示 `/help`。
11. 未知内部 command 会抛出 `ValueError`。

### 本次验证结果

已执行：

```text
python -m pytest
```

结果：

```text
21 passed
```

也执行了：

```text
python -m myagent
```

现在会进入交互式 CLI。

也可以用管道验证：

```text
"hello`n/stop`n" | python -m myagent
```

结果类似：

```text
MyAgent CLI is ready. Type /help for commands.
You: MyAgent: Echo: hello
You: Stopping MyAgent CLI.
```

## 如何阅读这部分代码

建议按这个顺序读：

1. 先读 `tests/test_cli_channel.py`，看 CLI 应该支持哪些行为。
2. 再读 `myagent/cli/commands.py` 里的 `CliState`。
3. 然后读 `parse_cli_command` 和 `handle_cli_command`。
4. 最后读 `make_inbound_message`，理解 CLI 怎么和 MessageBus 对接。

读代码时抓住一条主线：

```text
用户输入 -> 解析命令/普通消息 -> 普通消息转 InboundMessage
```

现在已经完成：

```text
等待 OutboundMessage -> 打印 Agent 回复
```

只是当前回复来自 EchoProvider。

## 当前代码的边界

当前 CLI Channel 已经完成：

- 命令解析
- 本地会话状态
- 普通输入转 `InboundMessage`
- Typer 入口
- 交互式输入循环
- 等待 `OutboundMessage`
- 打印 Agent 回复

但暂时还没有：

- 输入历史
- 多行输入
- trace / memory 查看命令
- 子 Agent 内部工具调用展开显示

OpenAI-compatible Provider、ContextBuilder、ToolRegistry、MCP 和 SubAgent 都已经接入。CLI Channel 的下一步重点不是继续扩大入口能力，而是保持本地体验清楚、稳定、可测试。

## Rich Spinner 状态展示设计

工具调用状态已经可以通过 `metadata.kind = "status"` 从 AgentLoop 发到 CLI。第一版实现是直接打印：

```text
MyAgent: 正在调用工具：read_file path=pyproject.toml
```

为了让交互体验更自然，CLI 使用 Rich 的 `Console.status()` 展示 spinner：

```text
MyAgent: Thinking
MyAgent: 正在调用工具：list_dir path=docs/modules
MyAgent: 正在调用工具：read_file path=docs/modules/TOOL_REGISTRY.md
```

设计原则：

- 引入 `rich`，但只用于 CLI 展示层。
- 只在真实交互终端启用 spinner。
- 测试、管道输出、非 TTY 环境仍然使用普通逐行输出。
- 收到最终回答前，status 只更新同一行。
- 收到最终回答后，清掉 spinner 行，再打印正式回答。

这样能改善体验，但不会影响 MessageBus、AgentLoop、ToolRegistry 的核心逻辑。

选择 Rich 的原因：

- Typer 生态里经常和 Rich 一起使用。
- `Console.status()` 已经处理了终端刷新、清行和 spinner 动画。
- 比自己维护 `\r` 刷新逻辑更稳定，也更容易继续扩展成 Markdown 或彩色输出。

## Markdown 渲染设计

真实模型经常会返回 Markdown，例如：

````text
## 标题
- 列表
```python
print("hello")
```
````

如果 CLI 直接按纯文本输出，用户会看到很多 Markdown 符号。既然已经引入 Rich，最终回答可以使用 Rich Markdown 渲染。

设计原则：

- 只渲染最终回答。
- 工具状态行仍然保持普通短文本。
- 只在真实交互终端启用 Markdown 渲染。
- 测试、管道输出、非 TTY 环境仍然输出原始文本，方便重定向和自动化测试。

CLI 输出形态：

```text
MyAgent:
<Rich Markdown rendered answer>
```

这样后续模型返回标题、列表、代码块时，终端里会更接近正常阅读体验。

## Phase 2 Review

### 当前实现

当前 CLI Channel 已经实现：

- Typer 入口：`python -m myagent` 和 `myagent`。
- `--config/-c` 指定本地 JSON 配置。
- `/help`、`/new`、`/stop`。
- 未知 slash command 的直接提示。
- 普通输入转 `InboundMessage`。
- 等待并打印 `OutboundMessage`。
- Rich spinner 展示 `metadata.kind = "status"` 的工具调用状态。
- Rich Markdown 渲染最终回答。
- 启动时连接配置中的 MCP server，并把工具注册到 ToolRegistry。
- MCP 连接失败时打印错误但不阻止本地 CLI 启动。
- MCP 连接成功时打印 server 名称和注册工具数量。

### 和原设计的差异

早期文档说第一阶段暂不引入 Rich 和 Markdown 渲染；实际后续已经引入并完成。

早期未知 slash command 会当作普通消息进入 AgentLoop；Phase 2 复盘后改为 CLI 直接提示，避免用户把拼错的命令发给模型。

早期 CLI 只负责 MessageBus 输入输出；实际现在也承担了运行时装配工作：

```text
Settings -> create_default_registry -> connect MCP servers -> create provider -> AgentLoop
```

这仍然可以接受，因为当前项目只有一个本地入口；后续如果入口变多，再考虑抽出 runtime bootstrap。

### 当前问题

- CLI 启动时的 MCP 成功/失败提示仍然比较基础。
- 子 Agent 内部工具调用不会逐条显示到 CLI；目前只能看到主 Agent 调用 `delegate_task`。
- 没有 `/trace`、`/memory` 等查看命令。
- 没有输入历史、多行输入和快捷键。
- CLI 错误提示还没有统一的错误类型或颜色规范。

### 二期建议

当前建议只做小体验增强：

- 未知 slash command 直接提示 `/help`。
- MCP 连接成功时显示注册工具数量，方便手动确认远程能力是否接入。
- 保留 Rich spinner 和 Markdown 渲染，不继续扩展复杂 TUI。
- 暂不展示 SubAgent 内部工具调用，等 SubAgent trace tree 设计清楚后再做。

### 暂不处理

暂不实现：

- `prompt_toolkit` 输入历史和多行编辑。
- `/trace`、`/memory`、`/model` 子命令。
- 复杂配置初始化向导。
- provider 登录。
- 后台任务取消。
- SubAgent 内部工具调用实时展开。
- Web UI 或 IM Channel。

### 测试计划

已有测试覆盖：

- slash command 解析。
- 未知 slash command 提示。
- `CliState` 会话切换。
- `make_inbound_message` 生成正确 `InboundMessage`。
- `run_chat` 能处理 help/stop。
- `run_chat` 能发布普通消息并打印最终回复。
- status 消息会在最终回复前打印。

本轮建议验证：

```text
python -m pytest tests/test_cli_channel.py
python -m pytest
```

本轮已执行，结果：

```text
14 passed
81 passed, 1 skipped
```

跳过项仍是当前 Windows 环境下的 `tests/test_mcp_stdio.py`。

手动验证：

```text
python -m myagent
/unknown
/help
/stop
```

预期 `/unknown` 不进入模型，而是提示：

```text
Unknown command. Type /help for supported commands.
```

### 面试表达更新

可以这样讲：

> CLI Channel 仍然是一个很薄的本地入口：普通消息通过 MessageBus 交给 AgentLoop，CLI 自己只处理控制命令和展示状态。Phase 2 做的体验增强也很克制，只让未知命令更清楚、MCP 连接状态更可见，而没有把 CLI 做成复杂 TUI。

如果被问到为什么不展示 SubAgent 内部工具调用，可以回答：

> 现在主 Agent 会显示 `delegate_task`，但子 Agent 内部工具调用还没有展示。原因是这需要 trace tree 或嵌套状态事件支持；如果直接在 CLI 里临时打印，容易破坏模块边界。等 SubAgent 复盘时先设计 trace tree，再决定 CLI 怎么展开展示。
