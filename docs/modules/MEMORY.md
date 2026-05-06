# Memory 模块设计

## 职责

Memory 负责保存跨轮次、跨会话仍然有价值的信息，并在构建上下文时召回。

一句话版本：

```text
Memory 把用户明确告诉 MyAgent 的长期信息保存到文件里，并在后续对话中注入 ContextBuilder。
```

它属于 `Intelligence Layer`。

## 为什么需要它

当前 MyAgent 已经有 session history。

Session history 能让模型记住当前会话前几轮聊过什么，但它有几个限制：

1. 只在内存里，程序退出就没了。
2. 历史越长，上下文越膨胀。
3. 它不区分“普通聊天内容”和“长期重要信息”。
4. `/new` 后会换 session，不适合保存长期偏好。

Memory 要解决的是：

```text
哪些信息应该被 MyAgent 长期记住？
下次对话时怎么把这些信息带回来？
```

例如：

```text
用户说：记住，我正在准备 Java 后端面试。
后续问：帮我复习一下项目亮点。
MyAgent 应该知道：用户正在准备 Java 后端面试。
```

## 参考 NanoBot 的取舍

NanoBot 的 memory 思路更完整，通常会涉及：

- partner/user memory
- active memory
- summary
- retrieved memory
- 分层上下文预算
- 持久化存储

MyAgent 第一阶段只保留最小可讲、可跑版本：

- 文件型 memory
- JSONL append-only
- 显式写入
- 简单关键词召回
- 注入 ContextBuilder 的 Memory section

暂不实现：

- active memory
- 自动总结
- 向量检索
- SQLite
- embedding
- 复杂 memory 分类
- 自动判断每句话是否要记住

这样既保留 NanoBot 的“长期信息进入上下文”思想，又不会把项目拖进复杂 RAG。

## Memory 和 Session History 的区别

### Session History

Session history 是短期对话上下文。

特点：

- 保存在 AgentLoop 内存里
- 按 session_key 区分
- 每轮自动追加 user/assistant
- 程序退出后丢失
- 适合当前连续对话

### Memory

Memory 是长期事实或偏好。

特点：

- 保存在 `data/memory/`
- 可跨进程、跨会话保留
- 只保存重要信息
- 通过 ContextBuilder 召回
- 适合用户画像、学习目标、偏好、项目背景

一句话区分：

```text
Session History 记住刚才聊了什么；Memory 记住以后也有用的事。
```

## 第一阶段写入策略

第一阶段建议使用 **显式写入**。

也就是说，只有用户明确表达“记住”时，MyAgent 才保存 memory。

触发示例：

```text
记住：我现在主要准备 Java 后端面试。
请记住，我的项目叫 MyAgent。
帮我记一下：我更喜欢先写文档再写代码。
```

第一版可以做一个简单规则：

```text
如果用户输入包含：
- 记住
- 记一下
- 帮我记

就把这句话作为 memory 保存。
```

这样做的好处：

- 不需要额外 LLM 判断。
- 行为容易解释。
- 用户可控，避免乱记。
- 测试简单。

后续可以扩展为 LLM memory extraction：

```text
User message -> extractor prompt -> Memory facts
```

## 数据存储

默认目录：

```text
data/memory/
```

第一版文件：

```text
data/memory/facts.jsonl
```

每一行是一条 memory。

示例：

```json
{"id":"...","ts":"2026-05-06T10:00:00.000000","content":"我现在主要准备 Java 后端面试。","source":"user_explicit","session_key":"cli:default"}
```

字段：

```text
id: str
ts: str
content: str
source: str
session_key: str
metadata: dict
```

第一版 `source` 固定为：

```text
user_explicit
```

## 核心接口

建议新增：

```text
myagent/memory/
  __init__.py
  entries.py
  store.py
  recall.py
```

### MemoryEntry

字段：

```text
id
ts
content
source
session_key
metadata
```

### JsonlMemoryStore

负责文件读写：

```text
add(content, session_key, source="user_explicit", metadata=None) -> MemoryEntry
list_entries(limit=None) -> list[MemoryEntry]
```

第一版 append-only，不做删除和更新。

### MemoryRecall

负责简单召回：

```text
recall(query, limit=5) -> list[MemoryEntry]
```

第一版召回策略：

1. 读取所有 memory。
2. 用非常简单的关键词重叠打分。
3. 如果没有命中，就返回最近几条。
4. 默认最多返回 5 条。

这不是高级检索，但足够演示 Memory 接入 ContextBuilder。

## 与 ContextBuilder 的关系

ContextBuilder 增加一个可选 memory_recall。

构建 messages 时：

```text
current user message
  -> memory_recall.recall(current content)
  -> Memory section
  -> system prompt
```

Memory section 示例：

```text
# Memory

- 我现在主要准备 Java 后端面试。
- 我更喜欢先写文档再写代码。
```

如果没有召回到 memory，就不注入 Memory section，避免噪音。

## 与 AgentLoop 的关系

AgentLoop 负责在每轮用户输入时检查是否需要保存 memory。

流程：

```text
process_message
  -> maybe_save_memory(inbound.content)
  -> context_builder.build_messages(...)
  -> provider
```

注意顺序：

```text
先保存，再构建上下文
```

这样用户刚说“记住：我叫 Lin”，同一轮回答时模型就可以知道它已经被保存。

## 与 Trace 的关系

Trace 可以记录 memory 事件。

第一版建议新增：

```text
memory_saved
memory_recalled
```

但如果实现时想保持更小，也可以先只在 ContextBuilder 里通过 `context_built` 的 message_count 间接观察。

推荐第一版记录：

- `memory_saved`
- `memory_recalled`

这样更容易调试 memory 是否生效。

## 第一阶段范围

第一阶段实现：

- `MemoryEntry`
- `JsonlMemoryStore`
- 显式记忆规则
- 简单关键词召回
- ContextBuilder 注入 Memory section
- AgentLoop 保存显式 memory
- Trace 记录 memory_saved / memory_recalled
- 测试覆盖

## 暂不实现

第一阶段暂不实现：

- 自动抽取 memory
- LLM 判断是否应该记忆
- 删除 memory
- 更新 memory
- memory 分类
- memory 权重
- active memory
- summary memory
- embedding / vector search
- SQLite
- 用户确认机制
- CLI memory 子命令
- `/memory`

## 测试点

建议新增：

```text
tests/test_memory_store.py
tests/test_memory_recall.py
tests/test_agent_memory.py
tests/test_context_builder.py
```

测试内容：

1. `JsonlMemoryStore` 能 append memory。
2. `list_entries` 能按写入顺序读取。
3. recall 能按关键词命中。
4. 没有关键词命中时返回最近 memory。
5. ContextBuilder 能注入 Memory section。
6. AgentLoop 遇到“记住”会保存 memory。
7. 保存后同一轮 context 里能包含 memory。
8. Trace 会记录 memory_saved / memory_recalled。

## 手动测试方式

运行：

```text
python -m myagent
```

输入：

```text
记住：我现在主要准备 Java 后端面试。
```

然后问：

```text
我现在准备什么方向的面试？
```

预期：

```text
MyAgent 能回答和 Java 后端面试相关。
```

也可以检查文件：

```text
data/memory/facts.jsonl
```

## 面试表达

可以这样讲：

> 我把 Memory 和 session history 区分开。Session history 是短期上下文，只服务当前会话；Memory 是长期事实，保存到 JSONL 文件里。第一版只做显式记忆，用户说“记住”时才写入，召回时用简单关键词匹配，并把结果注入 ContextBuilder 的 Memory section。这样实现轻量，但已经能展示 Agent 如何跨会话保留重要信息。

如果面试官问“为什么不用向量数据库”，可以回答：

> 向量检索适合大规模语义召回，但第一阶段 memory 数量很小，核心目标是跑通长期记忆链路。先用 JSONL 和关键词召回，能降低复杂度，也方便解释。后续 memory 规模变大时，可以把 recall 层替换成 embedding 或向量数据库，store 和 ContextBuilder 的边界不用推翻。

## 后续扩展方向

后续可以增强：

- LLM memory extraction
- memory delete/update
- memory categories
- memory confidence
- active memory
- summary memory
- embedding recall
- SQLite store
- `/memory` CLI
- `myagent memory` 子命令
- memory trace summary
- 用户确认后再保存

## 第一阶段实现记录

本阶段已经完成轻量文件型 Memory。

新增/修改文件：

```text
myagent/memory/__init__.py
myagent/memory/entries.py
myagent/memory/store.py
myagent/memory/recall.py
myagent/agent/context.py
myagent/agent/loop.py
tests/test_memory_store.py
tests/test_memory_recall.py
tests/test_context_builder.py
tests/test_agent_memory.py
```

### 代码阅读顺序

建议按这个顺序看：

1. `myagent/memory/entries.py`
2. `myagent/memory/store.py`
3. `myagent/memory/recall.py`
4. `myagent/agent/context.py`
5. `myagent/agent/loop.py`
6. `tests/test_agent_memory.py`

`entries.py` 定义 memory 数据结构，`store.py` 负责 JSONL 文件读写，`recall.py` 负责简单召回，ContextBuilder 负责把 memory 注入 system prompt，AgentLoop 负责显式保存。

### MemoryEntry

一条 memory 包含：

```text
id
ts
content
source
session_key
metadata
```

当前 `source` 默认是：

```text
user_explicit
```

表示这条 memory 来自用户明确要求保存。

### JsonlMemoryStore

默认路径：

```text
data/memory/facts.jsonl
```

核心接口：

```text
add(...)
list_entries(...)
```

当前是 append-only：

- 可以新增
- 可以读取
- 暂时不能删除
- 暂时不能更新

### MemoryRecall

第一版使用简单关键词重叠召回。

规则：

1. 从 JSONL 读取所有 memory。
2. 对用户 query 和 memory content 提取粗粒度词。
3. 按重叠数量排序。
4. 如果没有命中，返回最近几条。

这不是高级语义检索，但足够跑通长期记忆链路。

### ContextBuilder 接入

ContextBuilder 新增可选参数：

```python
memory_recall=MemoryRecall(...)
```

构建 messages 时会召回 memory，并注入：

```text
# Memory

- ...
```

如果没有 memory，就不输出 Memory section，避免噪音。

### AgentLoop 接入

AgentLoop 默认创建：

```python
JsonlMemoryStore()
MemoryRecall(memory_store)
ContextBuilder(memory_recall=...)
```

每轮处理用户消息时，会先检查显式记忆触发词：

```text
记住
记一下
帮我记
```

如果命中，会提取冒号后的内容并保存。

例如：

```text
记住：我正在准备 Java 后端面试。
```

会保存：

```text
我正在准备 Java 后端面试。
```

保存发生在构建上下文前，所以同一轮里 memory 就可以进入 system prompt。

### Trace 接入

Memory 相关事件：

```text
memory_saved
memory_recalled
```

这样可以在：

```text
data/traces/cli_default.jsonl
```

里看到 memory 是否保存和召回。

### 手动测试

运行：

```text
python -m myagent
```

输入：

```text
记住：我正在准备 Java 后端面试。
```

然后再问：

```text
我现在主要在准备什么？
```

可以检查：

```text
data/memory/facts.jsonl
data/traces/cli_default.jsonl
```

### 测试说明

新增/更新测试覆盖：

```text
tests/test_memory_store.py
tests/test_memory_recall.py
tests/test_context_builder.py
tests/test_agent_memory.py
```

覆盖内容：

- memory JSONL 写入
- memory 按顺序读取
- limit 读取最近 memory
- 关键词召回
- 无命中时返回最近 memory
- ContextBuilder 注入 Memory section
- AgentLoop 显式保存 memory
- 同一轮上下文包含刚保存的 memory
- Trace 记录 memory_saved / memory_recalled

验证结果：

```text
python -m pytest
61 passed
```

### 当前边界

当前 Memory 已经能保存和召回长期信息，但仍然很轻量：

- 只能显式保存
- 不能删除
- 不能更新
- 没有分类
- 没有权重
- 没有向量检索
- 没有自动总结
- 没有 CLI memory 子命令

这些后续可以按需要逐步补。

### 必须升级的方向

当前显式关键词 memory 只能作为 MVP。

它的价值是跑通：

```text
保存 -> 召回 -> 注入 ContextBuilder -> Trace
```

但这个能力本身不够智能，后续必须升级为：

```text
用户自然表达
  -> MemoryExtractor 判断是否值得记
  -> 抽取结构化事实
  -> 去重 / 合并
  -> 写入长期 memory
  -> ContextBuilder 相关召回
```

例如用户说：

```text
我最近主要在准备 Java 后端面试，八股文和项目都要复习。
```

后续应该自动抽取：

```text
用户正在准备 Java 后端面试。
用户需要复习八股文和项目经历。
```

而不是要求用户必须说“记住”。

这个升级可以作为 Memory 第二阶段单独设计，建议命名为：

```text
MemoryExtractor
```
