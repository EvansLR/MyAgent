# Phase 1 实现计划

## 当前状态

Phase 1 已完成。这份文档现在作为 Phase 1 的历史计划和验收记录保留，不再代表当前待办清单。

如果要继续开发，请优先阅读：

- `docs/NEXT_STEPS.md`
- `docs/PHASE2_REVIEW_PLAN.md`
- `MYAGENT_ROADMAP.md`

当前项目已经进入 Phase 2：模块复盘与重点升级。Phase 2 的第一步是校准 Project Docs / Roadmap，然后按模块复盘 Config、CLI Channel、Memory、Skills、SubAgent 等能力。

## 阶段目标

Phase 1 的目标是让 MyAgent 跑通一个最小但完整的 Agent 闭环：

```text
CLI 输入 -> MessageBus -> AgentLoop -> LLM Provider -> ToolRegistry -> 输出
```

这不是生产级版本，而是面试可讲、演示可跑、后续可扩展的核心骨架。

该目标已经达成。当前主链路为：

```text
CLI Channel
  -> MessageBus
  -> AgentLoop
  -> ContextBuilder
  -> LLM Provider
  -> ToolRegistry
  -> CLI Channel
```

已完成能力包括 EchoProvider、OpenAI-compatible provider、只读文件工具、JSONL trace、文件型 memory、skills 扫描、MCP 接入和 SubAgent 同步委托。

## 模块顺序

### 1. 项目骨架

建立 Python 项目基础结构：

- `pyproject.toml`
- `myagent/`
- `tests/`
- `docs/`

最小依赖建议：

- `typer`
- `openai`
- `pydantic`
- `pytest`
- `pytest-asyncio`

状态：已完成。

### 2. MessageBus

职责：解耦 Channel 和 AgentLoop。

设计：

- `InboundMessage`
- `OutboundMessage`
- 两个 `asyncio.Queue`
- `publish_inbound`
- `consume_inbound`
- `publish_outbound`
- `consume_outbound`

面试重点：通道只负责收发消息，AgentLoop 只负责处理消息，二者通过队列解耦。

状态：已完成。

### 3. CLI Channel

职责：提供最小交互入口。

功能：

- 普通文本输入
- `/new`
- `/stop`
- `/help`

第一阶段只支持单用户、本地命令行。

状态：已完成，并补充了 Rich 状态展示和 Markdown 渲染。

### 4. AgentLoop

职责：执行 ReAct 主循环。

设计：

- 全局 `asyncio.Lock` 串行处理
- 最大迭代次数限制
- 支持 LLM 回复
- 支持工具调用
- 工具结果回灌给 LLM

第一阶段不做复杂并发调度。

状态：已完成，并接入 trace、memory、skills、MCP、SubAgent 等扩展能力。

### 5. LLM Provider

职责：封装 OpenAI 兼容接口。

功能：

- 主模型配置
- 简单重试
- tool calling 结果适配

第一阶段只做一个 OpenAI-compatible provider，不做多 provider registry。

状态：已完成 OpenAI-compatible provider，并保留 EchoProvider 用于测试。

### 6. ToolRegistry

职责：注册和调用工具。

功能：

- 工具名称
- 工具描述
- JSON Schema 参数
- 参数校验
- 调用函数

内置工具优先级：

1. `list_dir`
2. `read_file`
3. `write_file`
4. `edit_file`
5. `exec`
6. `web_search`

状态：ToolRegistry 已完成。第一版实际只实现 `list_dir` 和 `read_file` 两个只读工具。

`write_file`、`edit_file`、`exec`、`web_search` 不属于 Phase 1 已完成范围。它们被后置到 Phase 2 复盘，由 ToolRegistry 模块决定是否需要确认机制、白名单、超时和网络边界。

### 7. ContextBuilder

职责：统一组装发给 LLM 的上下文。

第一阶段 section：

- Identity
- Memory
- Skills
- Tools
- Conversation

先不实现完整 token budget，但 section 结构要为后续 tier/budget 留扩展点。

状态：已完成分区式上下文构建。budget-aware composer 后置。

### 8. Trace

职责：记录 Agent 运行过程。

第一阶段：

- JSONL append-only
- 基础事件类型
- 能记录 user input、llm request、tool call、tool result、final answer

状态：已完成 JSONL 基础 trace，并记录 memory、skills、MCP、SubAgent 相关事件。高级 trace inspect、summary、correlation id 和树形 trace 后置。

### 9. Memory

职责：保留跨轮次信息。

第一阶段参考 NanoBot 思路做轻量版本：

- 文件型存储
- 简单召回
- 后续再做 active memory 或压缩

状态：已完成文件型存储和简单召回。Memory 是 Phase 2 重点复盘模块，后续需要升级到更值得讲的召回和整理机制。

### 10. Skills

职责：让 Agent 能读取可插拔能力说明。

第一阶段：

- 扫描 `skills/*/SKILL.md`
- 提取摘要
- 按需加载全文

状态：已完成扫描、摘要提取和上下文注入。自动读取全文、模型主动选择 skill、skill 与 SubAgent profile 绑定后置到 Phase 2 复盘。

### 11. MCP

职责：接入外部 MCP 工具。

第一阶段目标：

- stdio MCP 动态注册工具
- SSE MCP 作为同阶段或后续扩展，视前面进度决定

状态：已完成 stdio 和 HTTP/SSE 风格 MCP 接入。真实 server 体验、错误提示、超时、重试和禁用配置后置到 Phase 2 复盘。

### 12. SubAgent

职责：提供同步委托能力。

第一阶段：

- `delegate_task`
- 只读工具集
- 独立模型配置接口

状态：已完成 `delegate_task`、只读工具集和内置 profile。当前使用独立 prompt，但与主 Agent 共用 provider；独立模型配置接口后置到 Phase 2 复盘。

## 第一批建议实施

第一批只做：

1. 项目骨架
2. MessageBus
3. CLI Channel
4. 一个假 Provider 或 Echo Provider

这样可以先验证消息流和 CLI 体验，再接真实 LLM 和工具。

状态：已完成。这部分现在只作为历史开发节奏记录。
