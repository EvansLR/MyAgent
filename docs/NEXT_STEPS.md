# MyAgent 当前状态与下一步

这份文档用于跨对话续接。新对话开始时，先读这里，再看代码和模块文档。

## 当前项目目标

MyAgent 是一个面向学习、面试讲解和本地演示的轻量 ReAct Agent runtime。

当前阶段目标不是生产级 Agent 平台，而是保证：

- 系统能跑起来。
- 核心架构能讲清楚。
- 每个模块有文档、有测试、有明确边界。
- 后续扩展方向有记录，但不提前过度实现。

## 当前已完成模块

已经实现并提交过的主要能力：

- MessageBus：输入/输出消息队列。
- CLI Channel：本地命令行对话入口。
- AgentLoop：ReAct 主循环和工具调用。
- LLM Provider：OpenAI-compatible provider 和 EchoProvider。
- ContextBuilder：Identity、Memory、Skills 等上下文组装。
- ToolRegistry：工具注册、schema、参数校验和执行。
- Read-only filesystem tools：`list_dir`、`read_file`。
- Trace：JSONL 运行轨迹。
- Memory：文件型 memory 和显式记忆保存/召回。
- Skills：本地 `skills/*/SKILL.md` 扫描和上下文注入。
- MCP：stdio 和 HTTP/SSE 风格 MCP 工具接入。

## 最近完成的工作

最近一组完成的文档校准主题是 Project Docs / Roadmap。

校准内容：

- `MYAGENT_ROADMAP.md`：从“设计草案”调整为当前 roadmap，明确 Phase 1 已完成、Phase 2 是当前阶段，并把未实现的写文件、编辑、exec、web_search、高级 trace、独立 SubAgent 模型配置等放入 Phase 2 或后续扩展。
- `docs/PHASE1_PLAN.md`：标记为 Phase 1 历史计划和验收记录，不再作为当前待办清单。
- `docs/PROJECT_PLAYBOOK.md`：补充当前使用方式，说明新对话应先读 `NEXT_STEPS` 和 `PHASE2_REVIEW_PLAN`。

本轮只校准文档，没有修改运行代码。

随后进入 Config 复盘，并完成第一轮文档化：

- 新增 `docs/modules/CONFIG.md`：集中说明 `Settings`、`myagent.json`、环境变量覆盖、`mcpServers`、SubAgent 配置暂缓项和 Phase 2 Review。
- 更新 `myagent.example.json`：增加空的 `mcpServers` 字段，提示 MCP 配置入口。
- 更新 `docs/ARCHITECTURE.md`：把配置设计从早期环境变量口径校准为当前 JSON + 环境变量模式。
- 修复 provider 类型导入环：`providers.base`、`providers.echo`、`providers.openai_compatible` 不再为了类型标注导入 `myagent.agent.context.Message`。

本轮发现：本地 `myagent.json` 包含真实 provider/MCP key，但该文件未被 Git 跟踪，并且已在 `.gitignore` 中忽略。后续不能提交该文件。

本轮验证：

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

随后进入 CLI Channel 体验复盘，并完成第一轮小升级：

- 更新 `docs/modules/CLI_CHANNEL.md`：补充 Phase 2 Review，校准 Rich spinner、Markdown、MCP 启动提示和未知命令行为。
- 更新 `myagent/cli/commands.py`：未知 slash command 不再进入模型，改为提示 `/help`；MCP server 连接成功时显示注册工具数量。
- 更新 `tests/test_cli_channel.py`：覆盖未知 slash command 的新行为。

本轮验证：

```text
python -m pytest tests/test_cli_channel.py
python -m pytest
```

结果：

```text
14 passed
81 passed, 1 skipped
```

最近一组完成的变更主题是 SubAgent 和开发规范沉淀。

新增/修改内容：

- `AGENTS.md`：当前项目的 AI 协作规范。
- `docs/CODE_STANDARDS.md`：MyAgent 代码与协作规范。
- `docs/modules/SUBAGENT.md`：SubAgent 调研、设计和实现说明。
- `docs/NEXT_STEPS.md`：当前跨对话续接文档。
- `myagent/agent/subagent.py`：SubAgent 核心实现。
- `myagent/agent/loop.py`：注册 `delegate_task`，并记录 SubAgent trace。
- `myagent/agent/__init__.py`：导出 SubAgent 相关类型。
- `tests/test_subagent.py`：SubAgent 自动化测试。

## SubAgent 当前能力

第一版 SubAgent 采用 manager / agents-as-tools 思路。

主 Agent 默认可以看到：

```text
delegate_task
```

当模型调用 `delegate_task` 时，系统会创建一个临时子 Agent 执行任务。

子 Agent 目前只能使用：

```text
list_dir
read_file
```

它不会看到 `delegate_task`，因此不会递归委托。

当前内置 profile：

- `researcher`
- `reviewer`
- `interviewer`

## 当前验证状态

最近一次全量测试结果：

```text
python -m pytest
81 passed, 1 skipped
```

跳过的测试是 `tests/test_mcp_stdio.py`，原因是当前 Windows 开发沙箱可能禁止 asyncio subprocess pipe。这个是已知旧情况，不是 SubAgent 引入的新问题。

## 手动测试建议

启动 CLI：

```text
python -m myagent
```

推荐测试：

```text
请委托一个 researcher 子 Agent 浏览 docs/modules 目录，并总结当前项目有哪些模块。
```

如果模型触发成功，终端应显示类似：

```text
正在调用工具：delegate_task ...
```

注意：是否调用工具由模型自己决定。为了提高触发概率，测试时明确说“请委托一个 researcher 子 Agent”。

## 用户偏好和约束

开发时必须遵守：

- 任何重要代码实现前，先整理文档。
- 每个核心模块要有独立模块文档。
- 每次实现后，要回到模块文档补充实现说明。
- 做完一部分后，先让用户测试确认，再提交 Git。
- 提交以模块为单位，不为每个小改动提交。
- 提交后同步推送到远程 GitHub。
- 不提交真实配置、密钥、memory、trace、cache、本地测试目录。
- 项目服务学习和面试场景，优先保证能跑、能讲清楚，不做过度工程化。

## 下一步建议

当前最直接的下一步是：

1. 按 `docs/PHASE2_REVIEW_PLAN.md` 继续第二版模块复盘。
2. Project Docs / Roadmap 已完成第一轮校准。
3. Config 已完成第一轮文档复盘。
4. CLI Channel 已完成第一轮体验复盘和小升级。
5. 下一步建议进入 Memory 复盘，重点把 memory 从“简单可演示”升级为“值得讲”。
6. Memory 之后建议按 Skills、SubAgent 继续推进。
7. 如果用户继续测试 SubAgent 并发现问题，先回到 `docs/modules/SUBAGENT.md` 校准设计，再修代码。

可选后续方向：

- 改进 Skills：让 skill 从“提示词摘要”升级为更明确的可激活能力。
- 改进 Memory：从简单关键词召回升级为更可展示的记忆机制。
- 改进 SubAgent：profile 配置化、子 Agent trace tree、CLI 展示子 Agent 内部工具调用。
- 改进 ContextBuilder：增加 budget-aware context composer。
- 后续 IM Channel：暂时不做微信；如果以后扩展，优先考虑 QQ，并建议通过 OneBot 兼容协议接入，让 MyAgent 只负责 Channel 适配，不直接处理 QQ 登录和协议细节。

## 开放问题

- SubAgent profile 是否需要放进 `myagent.json` 配置？
- 子 Agent 内部工具调用是否要在 CLI spinner 中显示？
- Skills 是否要和 SubAgent profile 绑定？
- Memory 下一版是否需要从关键词召回升级为更可靠的检索策略？
- QQ Channel 是否在 Agent 主体跑顺之后作为独立模块设计？第一版是否只支持私聊，群聊是否需要命令前缀？
