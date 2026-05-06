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
80 passed, 1 skipped
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

1. 按 `docs/PHASE2_REVIEW_PLAN.md` 进入第二版模块复盘。
2. 第一轮先校准 Project Docs / Roadmap，避免旧文档误导后续开发。
3. 之后按 Config、MessageBus、CLI Channel、AgentLoop、LLM Provider、ContextBuilder、ToolRegistry、Trace、Memory、Skills、MCP、SubAgent 依次复盘。
4. 如果用户继续测试 SubAgent 并发现问题，先回到 `docs/modules/SUBAGENT.md` 校准设计，再修代码。

可选后续方向：

- 改进 Skills：让 skill 从“提示词摘要”升级为更明确的可激活能力。
- 改进 Memory：从简单关键词召回升级为更可展示的记忆机制。
- 改进 SubAgent：profile 配置化、子 Agent trace tree、CLI 展示子 Agent 内部工具调用。
- 改进 ContextBuilder：增加 budget-aware context composer。

## 开放问题

- SubAgent profile 是否需要放进 `myagent.json` 配置？
- 子 Agent 内部工具调用是否要在 CLI spinner 中显示？
- Skills 是否要和 SubAgent profile 绑定？
- Memory 下一版是否需要从关键词召回升级为更可靠的检索策略？
