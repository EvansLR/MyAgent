# Phase 2 模块复盘与升级计划

## 目标

Phase 1 已经完成了一个能跑通的轻量 ReAct Agent runtime。

Phase 2 不急着堆新功能，而是按模块逐个复盘：

- 当前实现是否和文档一致
- 当前能力是否足够稳定
- 哪些地方影响演示和面试表达
- 哪些地方需要升级
- 哪些增强应该继续后置

Phase 2 的核心标准是：

```text
能跑 -> 能测 -> 能讲 -> 能逐步增强
```

## Phase 1 实际完成情况

当前已经完成并可运行的主链路：

```text
CLI Channel
  -> MessageBus
  -> AgentLoop
  -> ContextBuilder
  -> LLM Provider
  -> ToolRegistry
  -> tool result
  -> AgentLoop
  -> CLI Channel
```

已实现的扩展能力：

- JSON 配置文件
- Rich CLI 状态展示
- Markdown 渲染
- JSONL Trace
- 文件型 Memory
- Skills 扫描和上下文注入
- MCP stdio / HTTP-SSE 风格接入
- SubAgent 同步委托
- 主 Agent 默认文件工具：`list_dir`、`read_file`、`write_file`、`edit_file`、`copy_file`、`move_file`
- 主 Agent 默认 web 工具：`web_search`、`web_fetch`

最近一次全量测试：

```text
python -m pytest
80 passed, 1 skipped
```

`tests/test_mcp_stdio.py` 在当前 Windows 沙箱下可能因 subprocess pipe 权限被 skip，这是已知环境限制。

## Phase 1 与文档不完全一致的地方

这些不是错误，而是第一版为了轻量和安全做过取舍。Phase 2 要先把口径校准清楚。

### ToolRegistry

早期文档提到的工具包括：

- `list_dir`
- `read_file`
- `write_file`
- `edit_file`
- `copy_file`
- `move_file`
- `exec`
- `web_search`
- `web_fetch`

实际第一版最初只做了：

- `list_dir`
- `read_file`

原因：

- 当前项目以学习和面试演示为主。
- 只读工具更安全。
- 先验证 LLM tool calling 闭环。

当前真实状态已经进入 Phase 2 的后续实现：

- 主 Agent 默认已支持 `write_file`、`edit_file`、`copy_file`、`move_file`
- 主 Agent 默认已支持 `web_search`、`web_fetch`
- 工作区外变更型文件操作通过当前 Channel 走审批流程
- `exec` 仍未实现

因此 ToolRegistry 这条线在 Phase 2 的重点已经不再是“是否要不要加这些工具”，
而是：

- 文档是否和真实默认工具集合一致
- 审批边界是否清楚
- 主 Agent 和 SubAgent 的工具权限是否讲得明白

### SubAgent

早期文档提到“独立模型配置”。

实际第一版最初：

- 子 Agent 使用独立 prompt。
- 子 Agent 使用受限只读工具集。
- 子 Agent 和主 Agent 共用 provider。

当前真实状态已经继续演进：

- 子 Agent 按 profile 使用受限只读工具集
- 部分 profile 已可使用 `web_search` / `web_fetch`
- 子 Agent 仍不继承写文件工具、MCP tools 或递归 `delegate_task`

因此 Phase 2 的重点已经转为：

- profile 权限边界是否清楚
- 是否需要独立模型配置
- 是否要继续增强 trace tree / CLI 展示

### Trace

早期文档提到更完整的 trace 能力，例如事件枚举、correlation id、损坏容忍和清理。

实际第一版：

- JSONL append-only 已完成。
- 基础 turn、LLM、tool、memory、subagent 事件已完成。
- 高级 trace 诊断和树形 trace 仍未做。

当前真实状态已经继续演进：

- 已有 `trace latest`
- 已有 `trace show`
- 已有 `trace skills`
- 已有 `trace startup`
- 已有 `trace context`
- 已有 `trace report`
- 已有 `trace viewer`

因此 Trace 在 Phase 2 的重点已不再是“要不要做 inspect 命令”，
而是是否还需要继续做少量、对面试表达有帮助的可观察性收口。

### Memory

实际第一版已经有文件型保存和简单召回。

但用户已经明确指出：当前 memory 太简单，后续一定要升级，否则不够拿得出手。

Phase 2 应该重点复盘 Memory。

### Skills

实际第一版是：

- 扫描 `skills/*/SKILL.md`
- 提取摘要
- 注入 system prompt

但还没有稳定实现：

- 模型主动选择 skill
- 自动读取 skill 全文
- 按 skill 输出结构执行
- skill 与 SubAgent profile 绑定

Phase 2 应该重点复盘 Skills。

## 模块复盘顺序

Phase 2 建议按下面顺序推进。

### 1. Project Docs / Roadmap

目标：

- 校准 `MYAGENT_ROADMAP.md`
- 校准 `docs/PHASE1_PLAN.md`
- 明确哪些内容属于已完成、二期增强、后续扩展

判断标准：

- 新对话读文档不会误判当前进度
- 文档不再把“未来增强”写得像“当前必须完成”

### 2. Config

目标：

- 复盘 `myagent.json`、`myagent.example.json`、环境变量覆盖逻辑
- 明确 provider、MCP、后续 SubAgent 是否都走配置文件

重点问题：

- 配置结构是否容易理解
- 是否需要加入 SubAgent profile 配置
- 是否需要更清楚的配置文档

### 3. MessageBus

目标：

- 判断当前内存队列是否足够
- 记录 Redis / RabbitMQ 作为后续扩展，不急着实现

重点问题：

- 当前本地 CLI 是否需要复杂消息队列
- 如果未来多通道或后台任务，MessageBus 怎么升级

### 4. CLI Channel

目标：

- 检查当前交互体验是否够清楚
- 复盘 Rich spinner、Markdown 渲染、状态消息

重点问题：

- 子 Agent 内部工具调用是否要展示
- 是否需要 trace 查看命令
- 是否需要更清楚的错误提示

### 5. AgentLoop

目标：

- 复盘 ReAct 主循环、工具迭代上限、错误处理
- 检查是否需要拆出更清楚的 run/session 抽象

重点问题：

- 当前 `AgentLoop` 是否开始承担过多职责
- memory 保存、trace、tool loop、subagent 是否需要进一步分层

### 6. LLM Provider

目标：

- 检查 OpenAI-compatible provider 的兼容性
- 复盘 `reasoning_content` 等 provider 特殊字段处理

重点问题：

- 是否需要 provider registry
- 是否需要为 DeepSeek、OpenAI、本地模型分别写适配文档
- 是否需要模型能力检测

### 7. ContextBuilder

目标：

- 复盘 system prompt 分区
- 判断是否进入 budget-aware context composer

重点问题：

- Memory、Skills、Tools、Conversation 是否需要优先级
- 是否要加入 token budget
- 是否要记录每次上下文组成到 trace

### 8. ToolRegistry

目标：

- 检查工具 schema、参数校验、错误信息
- 校准默认工具集合、审批边界和主/子 Agent 工具差异

重点问题：

- 写工具是否需要确认机制
- exec 是否需要白名单和超时
- web 工具是否已经足够，还是仍然过重

### 9. Trace

目标：

- 复盘 trace 是否足够帮助调试
- 判断是否需要 trace summary / inspect 命令

重点问题：

- 是否需要 correlation id
- 是否需要记录完整 tool arguments/result
- 是否需要隐藏敏感信息

### 10. Memory

目标：

- 把 memory 从“简单可演示”升级为“值得讲”

重点问题：

- 是否继续文件型
- 是否加入重要性、时间、来源字段
- 是否做更可靠的 recall
- 是否需要 memory review / consolidation

### 11. Skills

目标：

- 从“摘要注入”升级为更明确的“可激活能力”

重点问题：

- 模型如何知道有哪些 skill
- 模型如何读取 skill 全文
- skill 是否应该暴露成工具
- skill 是否和 SubAgent profile 绑定

### 12. MCP

目标：

- 复盘 stdio 和 HTTP/SSE 客户端
- 检查真实 MCP server 接入体验

重点问题：

- 错误提示是否清楚
- 工具命名是否稳定
- 是否需要超时、重试、禁用配置

### 13. SubAgent

目标：

- 复盘 `delegate_task`
- 判断是否继续增强 profile、trace、配置、CLI 展示

重点问题：

- 是否需要独立模型配置
- 子 Agent 内部工具调用是否要展示
- 是否需要 reviewer/researcher/interviewer 的不同默认 skill
- 是否需要禁止或允许嵌套委托

## 每个模块的复盘模板

每个模块复盘时，都按下面模板写进对应模块文档。

```text
## Phase 2 Review

### 当前实现

### 和原设计的差异

### 当前问题

### 二期建议

### 暂不处理

### 测试计划

### 面试表达更新
```

如果某个模块需要改代码，先更新模块文档，再实现。

## Phase 2 优先级判断

优先做满足下面条件的内容：

- 会影响当前系统能否稳定运行
- 用户手动测试时容易遇到
- 文档和代码明显不一致
- 面试时很容易被问到
- 改动范围可控

暂时不做满足下面条件的内容：

- 主要是生产级复杂度
- 依赖大量外部服务
- 会破坏当前轻量定位
- 当前没有明确测试场景
- 需要大规模重构才能完成

## 初步建议

Phase 2 第一轮建议先做：

1. Project Docs / Roadmap 校准
2. Config 复盘
3. CLI Channel 体验复盘
4. Memory 复盘
5. Skills 复盘
6. SubAgent 复盘

其中 Memory 和 Skills 是第二版最值得重点提升的两个模块。

原因：

- Memory 当前太简单，用户已经明确提出后续必须升级。
- Skills 当前还停留在摘要提示层，和真正“能力调用”还有距离。
- SubAgent 刚完成第一版，适合先观察测试效果，再决定是否配置化。
