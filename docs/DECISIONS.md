# MyAgent 决策记录

## 项目身份

MyAgent 是一个参考 NanoBot 架构理念重新实现的轻量异步 ReAct Agent runtime。

目标不是复刻 NanoBot 的全部功能，而是提炼一个适合学习、展示和面试讲解的版本。

## 已确认决策

### 1. 命名

项目名：MyAgent

建议 Python 包名：`myagent`

理由：项目命名直接表达这是用户自己的 Agent 实现，避免和 NanoBot 混淆。

### 2. Context 设计

方向：模仿 NanoBot 的分区式 context 设计。

第一阶段采用轻量实现：

- Identity
- Memory
- Skills
- Tools
- Conversation history

暂不做完整 token budget 管理，但保留 section/tier 的抽象空间，方便后续升级为 budget-aware composer。

### 3. Memory

方向：参考 NanoBot 的 memory 思路。

第一阶段优先做能演示的版本，不追求完整长期记忆系统。Memory 可以先围绕文件型存储和简单召回实现，后续再扩展压缩、活跃记忆、SQLite 或向量检索。

### 4. Skills

方向：扫描摘要 + 按需加载全文。

启动时扫描 `skills/` 目录下的 `SKILL.md`，提取名称和摘要注入 context。真正需要某个 skill 时，再读取完整 `SKILL.md`。

### 5. MCP

目标：stdio + SSE 都可支持。

实现顺序建议：

1. 先实现 stdio MCP，跑通动态工具注册。
2. 再实现 SSE MCP，作为扩展能力。

## 面试表达口径

MyAgent 的核心取舍是：用最少模块展示 Agent runtime 的关键机制。

关键机制包括：

- MessageBus 解耦输入通道和 AgentLoop
- AgentLoop 串行执行 ReAct 循环
- ContextBuilder 统一组装模型上下文
- ToolRegistry 管理工具描述、校验和调用
- Memory 提供跨轮次信息保留
- Trace 记录运行过程，方便调试和讲解
- Skills 和 MCP 提供扩展能力

## 待确认问题

1. 第一阶段是否先从 MessageBus + CLI Channel 开始？
2. 是否现在初始化 Git 仓库？
3. 是否需要为每个模块补独立设计文档？
