# MyAgent 项目开发手册

## 这份文档解决什么问题

从零开发一个项目时，最容易乱的是顺序：

- 先写代码还是先设计？
- 一个模块要设计到多细？
- 什么时候写测试？
- 什么时候提交 Git？
- 遇到方向变化怎么办？

MyAgent 的开发手册用来固定一套轻量但稳定的工作法。后续每次开新模块，都先看这份文档，再看总体架构和模块文档。

## 核心工作法

MyAgent 的开发顺序是：

```text
目标 -> 文档 -> 最小实现 -> 验证 -> 用户确认 -> Git 提交
```

这套顺序背后的原因很简单：

- 先有目标，避免写着写着偏航。
- 先写文档，逼自己讲清楚模块边界。
- 先做最小实现，让系统尽快跑起来。
- 先验证，再扩展。
- 用户确认后再提交，方便按模块回退。

## 一个模块怎么从零开始

每个模块都按 7 步推进。

### 1. 定义模块目标

先用一句话说明这个模块解决什么问题。

例子：

```text
MessageBus 用两个异步队列解耦输入通道和 AgentLoop。
```

如果一句话说不清，说明模块边界还不清楚，需要先拆小。

### 2. 确认它在总体架构里的位置

查阅：

- `docs/ARCHITECTURE.md`
- `docs/PHASE1_PLAN.md`
- `docs/DECISIONS.md`

明确这个模块属于哪一层、依赖谁、被谁调用。

### 3. 写模块设计文档

每个模块实现前必须有独立文档，放在：

```text
docs/modules/
```

推荐模板：

```text
# 模块名

## 职责
## 为什么需要它
## 输入输出
## 核心接口
## 数据结构
## 与其他模块的关系
## 第一阶段范围
## 暂不实现
## 测试点
## 面试表达
```

模块文档不要求长，但必须能指导代码。

### 4. 做最小实现

第一版代码只实现文档里的第一阶段范围。

判断标准：

- 能跑通主流程
- 能被测试验证
- 能在面试中解释
- 不引入当前不需要的复杂抽象

### 5. 写最小测试

测试不追求覆盖率好看，重点验证核心行为。

例子：

- MessageBus：发布 inbound 后能消费到同一条消息。
- ToolRegistry：注册工具后可以按名称调用。
- ContextBuilder：能按 section 组装 system prompt。

如果某个模块暂时不好写自动化测试，至少要有手动验证步骤写进文档或最终说明。

### 6. 让用户确认

模块实现后先不提交。

需要先给用户说明：

- 改了哪些文件
- 怎么验证
- 当前还有哪些暂不处理的问题

等用户确认后，再进入 Git 提交。

### 7. 模块级提交

提交粒度以模块为单位。

推荐提交信息：

```text
docs: design message bus
feat: add message bus
feat: add cli channel
feat: add agent loop skeleton
```

如果某个模块文档和实现很小，可以在用户同意后一起提交；如果模块较复杂，先提交设计文档，再提交实现。

## 文档分层

MyAgent 的文档分 4 类。

### 1. Roadmap

文件：

```text
MYAGENT_ROADMAP.md
```

作用：说明项目长期方向、阶段划分和取舍。

### 2. Architecture

文件：

```text
docs/ARCHITECTURE.md
```

作用：说明整体架构、模块分层、数据流和目录结构。

### 3. Decisions

文件：

```text
docs/DECISIONS.md
```

作用：记录已经确认的技术决策和设计口径。

如果之后某个决策变化，先更新这里。

### 4. Module Docs

目录：

```text
docs/modules/
```

作用：每个模块单独设计。

例子：

```text
docs/modules/MESSAGE_BUS.md
docs/modules/CLI_CHANNEL.md
docs/modules/AGENT_LOOP.md
docs/modules/MEMORY.md
```

## 第一阶段推荐开发顺序

MyAgent 第一阶段按“先跑通消息，再接入智能”的顺序推进。

### Milestone 0：文档和项目骨架

目标：

- 总体架构清楚
- 开发手册清楚
- 项目结构建立

产出：

- `docs/ARCHITECTURE.md`
- `docs/PROJECT_PLAYBOOK.md`
- `pyproject.toml`
- `myagent/`
- `tests/`

### Milestone 1：消息流闭环

目标：

```text
CLI -> MessageBus -> AgentLoop -> EchoProvider -> MessageBus -> CLI
```

这里先不用真实 LLM。

原因：

- 先验证框架通路
- 降低第一步难度
- 出错时容易定位

### Milestone 2：真实 LLM 回复

目标：

- 接 OpenAI-compatible provider
- 能用真实模型回答
- ContextBuilder 开始接入

### Milestone 3：工具调用

目标：

- ToolRegistry
- 内置文件工具
- shell 工具
- LLM tool calling 闭环

### Milestone 4：Trace 和 Memory

目标：

- JSONL trace
- 简单 memory 存储和召回

### Milestone 5：Skills、MCP、SubAgent

目标：

- Skills 扫描和按需加载
- MCP 工具注册
- SubAgent 同步委托

## 如何判断一个设计够不够

一个模块设计如果能回答下面 5 个问题，就够第一阶段使用：

1. 它解决什么问题？
2. 它的输入和输出是什么？
3. 它暴露哪些核心接口？
4. 它和上下游模块怎么连接？
5. 第一阶段明确不做什么？

不要为了“看起来高级”增加抽象。MyAgent 的目标是轻量、可教学、可面试。

## 如何参考 NanoBot

参考 NanoBot 时只看三件事：

1. 它为什么需要这个模块？
2. 它的模块边界是什么？
3. MyAgent 可以删掉哪些复杂度？

不直接照搬：

- 多通道复杂适配
- 生产级配置迁移
- 重型安全策略
- 大量 provider registry
- 完整后台任务系统

MyAgent 要保留的是设计思想，不是完整工程体量。

## 如何写测试

测试优先覆盖“行为”，不是覆盖实现细节。

好的测试名称像一句需求：

```text
test_message_bus_delivers_inbound_message
test_tool_registry_rejects_unknown_tool
test_context_builder_includes_memory_section
```

第一阶段测试文件和模块基本一一对应：

```text
tests/test_message_bus.py
tests/test_cli_channel.py
tests/test_agent_loop.py
tests/test_tool_registry.py
```

## 如何提交 Git

提交前检查：

```text
git status --short
```

提交节奏：

- 文档基线可以单独提交。
- 模块设计可以单独提交。
- 模块实现等用户确认后提交。
- 不把多个无关模块塞进一次提交。

提交信息格式：

```text
docs: design message bus
feat: add message bus
test: cover message bus
```

## 遇到设计变化怎么办

如果实现时发现原设计不合适：

1. 停下来。
2. 更新对应文档。
3. 再改代码。
4. 最终说明为什么变更。

这叫“文档校准航向”，不是拖慢进度。对面试项目来说，这反而是亮点。

## 下一步

当前建议下一步：

1. 确认并提交 `docs/ARCHITECTURE.md` 和 `docs/PROJECT_PLAYBOOK.md`。
2. 创建 `docs/modules/MESSAGE_BUS.md`。
3. 创建项目骨架。
4. 实现 MessageBus。
5. 写 `tests/test_message_bus.py`。
6. 用户测试确认后提交 MessageBus 模块。
