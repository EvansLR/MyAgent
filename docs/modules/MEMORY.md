# Memory 模块设计

## 职责

Memory 负责保存跨轮次、跨会话仍然有价值的信息，并在构建上下文时召回。

一句话版本：

```text
Memory 把用户明确告诉 MyAgent 的长期信息保存到文件里，并在后续对话中注入 ContextBuilder。
```

它属于 `Intelligence Layer`。

## 当前状态速览

这份文档前半部分保留了 Memory 第一阶段的设计口径，用来解释它最初为什么从
显式写入 + JSONL append-only 开始。

但当前真实实现已经进入 Memory v2 的最小闭环阶段，主路径不再是早期的
`facts.jsonl` + 简单关键词召回，而是 Markdown-backed memory workspace：

- `MEMORY.md`
- `MEMORY_PROPOSALS.md`
- `daily/YYYY-MM-DD.md`

当前主线能力：

- ContextBuilder 默认组装 `MEMORY.md` 中的高信号 section。
- Agent 可用 memory tools：
  - `memory_append_daily`
  - `memory_propose_long_term`
  - `memory_search`
  - `memory_get`
  - `memory_forget`
- `MemoryExtractor` 在 final answer 后运行，但默认只写 daily candidate 或 proposal。
- 自动提取不会直接污染长期 `MEMORY.md`。

当前边界：

- 不上向量库。
- 不上 SQLite。
- 不做 knowledge graph。
- 不让模型随意直接改长期 memory。

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

MyAgent 第一阶段最初只保留最小可讲、可跑版本：

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

这段描述的是最初设计口径；当前真实主路径已经演进到 Markdown-backed memory workspace，见本文顶部“当前状态速览”。

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

## Phase 2 Review

### 当前实现

当前 Memory 已经完成第一版闭环：

```text
显式保存 -> JSONL 存储 -> 简单召回 -> ContextBuilder 注入 -> Trace 记录
```

已实现能力：

- `MemoryEntry`：保存 `id`、`ts`、`content`、`source`、`session_key`、`metadata`。
- `JsonlMemoryStore`：append-only 写入 `data/memory/facts.jsonl`。
- `MemoryRecall`：用关键词重叠召回，没命中时返回最近 memory。
- `AgentLoop`：识别“记住 / 记一下 / 帮我记”并保存。
- `ContextBuilder`：把召回结果注入 `# Memory` section。
- `Trace`：记录 `memory_saved` 和 `memory_recalled`。

### 外部调研结论

详细调研见：

```text
docs/modules/MEMORY_PHASE2_RESEARCH.md
```

本项目定位需要先说清楚：

```text
MyAgent 是用户个人助理型 Agent，类似 OpenClaw 这类 local-first personal agent。
```

因此 Memory 的主目标不是服务代码仓库自动化，也不是简单复刻 Codex / Claude Code 的项目指令机制，而是维护用户个人助理的长期工作状态。

参考对象包括：

- OpenClaw memory
- OpenAI ChatGPT Memory
- OpenAI Agents SDK context personalization cookbook
- OpenAI Codex / `AGENTS.md`
- Claude Code memory
- Letta / MemGPT
- LangGraph / Deep Agents
- Zep

这些系统的共识是：

```text
Memory 不是简单把历史聊天塞回 prompt。
Memory 是分层、可管理、可检索、可审查的状态系统。
```

对 MyAgent 最值得采纳的经验：

- 优先参考 OpenClaw 的 local-first personal memory 思路。
- 区分 short-term session history 和 personal long-term memory。
- 区分 memory scope：`profile`、`project`、`working`。
- 区分 memory kind：`preference`、`fact`、`decision`、`task`、`insight`。
- 让用户能查看、删除、关闭 memory。
- 长期 memory 应该是整理后的 durable facts，不应直接堆原始对话。
- 召回应可解释：为什么召回这条、命中了什么、分数是多少。
- 保持 local-first，人类可读、可测试。
- 向量检索、knowledge graph、后台 dreaming 可以后置。

### 和原设计的差异

第一版设计只区分：

```text
session history
memory
```

Phase 2 需要进一步区分：

```text
Session History
Memory Inbox / Candidate Memory
Long-term Memory
```

第一版 `MemoryEntry.metadata` 是开放 dict，但没有明确字段。Phase 2 应把常用字段提升为正式字段，降低后续维护成本。

第一版 recall 返回 `list[MemoryEntry]`，没有分数和命中原因。Phase 2 应新增结构化 recall result，以便 trace 和调试。

### 当前问题

- memory 只能显式保存，用户必须说“记住”。
- memory entry 没有 `kind`、`scope`、`importance`、`tags`、`updated_at`。
- recall 只做关键词重叠，不考虑 tag、重要性、时间。
- trace 只记录召回数量和 memory id，没有记录召回原因。
- memory 只能 append，不能删除、归档或标记失效。
- ContextBuilder 只有一个扁平 Memory section，无法区分 profile 和 relevant memories。
- 没有 `/memory` 或 `myagent memory` 管理入口。

### Phase 2 目标

第二版目标不是生产级 memory 平台，而是：

```text
从“显式关键词记忆”升级为“面向个人助理的轻量长期状态系统”。
```

验收标准：

- 仍然本地文件型存储。
- 旧 JSONL memory 能兼容读取。
- memory 有明确类型和作用域。
- recall 有可解释分数。
- 用户至少可以通过 API 删除或隐藏 memory。
- trace 能说明 memory 为什么被召回。
- 不引入向量库、SQLite、后台任务或真实模型依赖。

### Phase 2 最小实现范围

Phase 2 的 Memory 不应该只做“结构字段 + 更好 recall”。那会变成一个被动存储模块，仍然不像个人助理。

参考 OpenClaw、Claude Code、OpenAI Agents SDK 后，MyAgent Memory v2 应采用三条路径：

```text
Live path
  主 Agent 在当前 turn 中通过 memory tools 主动写入或提出记忆。

Post-turn path
  每轮结束后由 MemoryExtractor 后处理 transcript，补漏候选记忆。

Consolidation path
  定期或手动 review daily notes / candidates，晋升到 MEMORY.md。
```

这三条路径分工：

- Live path 类似 OpenClaw / Claude：agent 在工作中主动记忆。
- Post-turn path 类似 OpenAI Agents SDK：run/session 后抽取和总结。
- Consolidation path 类似 OpenClaw Dreaming：筛选、去重、评分、promotion。

#### 触发机制

1. Live path：memory tools

给主 Agent 暴露受控 memory tools：

```text
memory_append_daily
memory_propose_long_term
memory_search
memory_get
```

用途：

- 用户显式说“记住”“以后按这个”“这个很重要”。
- 模型判断当前 turn 中出现了长期偏好、长期目标、重要决策。
- 模型需要查历史记忆来完成当前任务。

第一版建议：

- `memory_append_daily` 写入 `memory/YYYY-MM-DD.md` 或对应 daily store。
- `memory_propose_long_term` 生成长期记忆 proposal，不让模型随意直接改 `MEMORY.md`。
- `memory_search` / `memory_get` 用于按需查 memory，避免把全部 memory 注入 prompt。

2. Post-turn path：MemoryExtractor

每轮最终回答后运行：

```text
user message + assistant answer + trace summary
  -> MemoryExtractor
  -> memory candidates
  -> daily notes / inbox
```

这不是为了省 token 的可选机制。MyAgent 是个人助理项目，默认应该每轮运行，后续再加配置开关。

MemoryExtractor 只负责补漏和候选，不直接写 `MEMORY.md`。

3. Consolidation path：Dreaming / Review

定期或手动读取：

```text
daily notes
memory candidates
recent trace summaries
existing MEMORY.md
```

然后做：

- 去重。
- 合并相似记忆。
- 发现冲突。
- 判断是否 durable。
- 生成 promotion proposal。

只有通过 review 的内容才写入 `MEMORY.md`。

第一版可以先做文档和接口，不急着实现完整后台 dreaming。

#### 文件层设计

更贴近 OpenClaw 的文件结构：

```text
data/memory/
  MEMORY.md
  MEMORY_PROPOSALS.md
  daily/
    2026-05-07.md
```

含义：

- `MEMORY.md`：精炼、稳定、长期有效的记忆。
- `daily/YYYY-MM-DD.md`：每轮自动观察、候选记忆、近期计划。
- `MEMORY_PROPOSALS.md`：临时候选区；定时 consolidation 会尝试合并、归档并清空，避免长期堆积。

`profile / project / working` 不再作为三个文件，而是作为记忆 section / scope：

```text
MEMORY.md
  ## Core Memory
  ## User Profile
  ## Preferences
  ## Long-term Goals
  ## Active Projects
  ## Decisions

daily/YYYY-MM-DD.md
  ## Observations
  ## Candidates
  ## Open Loops
```

#### Core Memory 与 Searchable Memory

参考 Letta / MemGPT 的 Core Memory / Archival Memory 分层，以及 OpenClaw / Claude Code 默认加载高信号 memory 文件的做法，MyAgent 使用两个概念：

```text
Core Memory
  默认组装进 system prompt 的高信号长期记忆。

Searchable Memory
  不默认组装，通过 memory_search / memory_get 按需检索。
```

Core Memory 不是单独文件，而是 `MEMORY.md` 里的默认注入 section，例如：

```text
## Core Memory
## User Profile
## Active Goals
```

`memory_search` 搜索的是：

- `MEMORY.md` 里没有默认注入的 section，例如 Decisions、Reference Notes、Archived Details。
- `daily/YYYY-MM-DD.md`。
- `MEMORY_PROPOSALS.md` 中的 proposal / review 记录。

这样可以保证个人助理每轮都知道核心偏好和长期目标，同时避免把所有历史细节都塞进 prompt。

#### Phase 2A 最小实现建议

建议第一轮做这些：

1. 扩展 `MemoryEntry`

新增字段：

```text
scope: profile | project | working
kind: preference | fact | decision | task | insight
importance: int
tags: list[str]
updated_at: str
status: active | candidate | archived | forgotten
```

默认值保持兼容：

```text
scope = profile
kind = fact
importance = 1
tags = []
status = active
```

2. 增加 memory tools

最小工具：

```text
memory_append_daily(note, tags=None, importance=1)
memory_propose_long_term(content, section, tags=None, importance=3)
memory_search(query)
memory_get(memory_id)
```

先不让模型直接写 `MEMORY.md`，而是写 proposal。

3. 增加 `MemoryExtractor`

每轮后运行，输出 candidate entries。

第一版可以用同一个 OpenAI-compatible provider，后续再配置 summary/memory model。

4. 增加 `MemoryRecallResult`

字段：

```text
entry
score
matched_terms
matched_tags
```

`MemoryRecall.recall(...)` 仍然可以返回 entries，或者新增：

```text
recall_with_scores(...)
```

为了减少破坏，建议先新增 `recall_with_scores(...)`，保留原 `recall(...)`。

5. 升级召回打分

建议轻量公式：

```text
score =
  keyword_overlap * 3
  + tag_overlap * 4
  + importance
  + recency_bonus
```

其中 `recency_bonus` 第一版可以非常简单，例如最近 7 天 +1，或者先不实现。

6. 增加 memory 管理 API

优先做：

```text
forget(memory_id) -> bool
```

实现方式不物理删除，而是重写 JSONL 或追加 tombstone 都可以。

为保持简单，Phase 2A 建议先重写 JSONL，把目标 entry 标记为：

```text
status = forgotten
```

recall 默认忽略 forgotten memory。

7. 增强 trace

新增事件：

```text
memory_tool_call
memory_candidate_saved
memory_proposal_created
memory_recalled
```

`memory_recalled` 记录：

```text
memory_id
score
matched_terms
matched_tags
```

### 暂不处理

暂不实现：

- embedding / vector search。
- SQLite。
- knowledge graph。
- 自动全量 chat history 建模。
- 后台 dreaming / cron consolidation。
- 复杂 MemoryExtractor 自动写入长期 memory。
- 让模型直接任意改 `MEMORY.md`。
- `/memory` CLI 交互命令。
- 多用户云同步。
- 复杂隐私设置页。

这些方向保留在 `MEMORY_PHASE2_RESEARCH.md`，等基础结构稳定后再选。

### 测试计划

新增或更新测试：

- 旧格式 JSONL 仍能读成新 `MemoryEntry`。
- 新字段能写入和读取。
- forgotten memory 默认不被 recall。
- `forget(id)` 能标记 memory。
- tag 命中会提高 recall 分数。
- importance 会影响排序。
- `recall_with_scores(...)` 返回分数和命中原因。
- ContextBuilder 仍能注入 Memory section。
- AgentLoop 的 `memory_recalled` trace 包含 score 和 matched 信息。

推荐先跑：

```text
python -m pytest tests/test_memory_store.py tests/test_memory_recall.py tests/test_agent_memory.py tests/test_context_builder.py
```

最终跑：

```text
python -m pytest
```

### 面试表达更新

可以这样讲：

> MyAgent 第一版 Memory 只做显式保存和关键词召回，用来跑通长期记忆链路。第二版我参考了 ChatGPT Memory、Claude Code、OpenClaw、Letta 和 LangGraph，没有直接上向量库，而是先把 memory lifecycle 做清楚：区分 session history 和 long-term memory，给 memory 增加 scope、kind、importance、tags，并让 recall 输出可解释分数。这样既比第一版更像真实 Agent memory，又保持本地文件型、可测试、可讲清楚。

更贴近项目定位的表达是：

> MyAgent 是个人助理型 Agent，Memory 是它的长期工作状态，不是聊天记录缓存。第二版会把 memory 分成 profile、project、working 三层：profile 记用户偏好和目标，project 记当前项目状态和决策，working 记最近阶段的候选信息和观察。这样它更接近 OpenClaw 这类 local-first personal agent，而不是只服务一次性代码任务。

如果被问到为什么暂时不做自动记忆：

> 自动记忆最大的问题不是抽取，而是误记和难管理。所以 MyAgent 第二版先增强显式记忆和可管理能力，自动抽取先进入候选区或后续 MemoryExtractor，不直接写长期 memory。

如果被问到为什么不用向量库：

> 当前 memory 数量很小，向量库不是瓶颈。更关键的是建立清楚的数据结构、召回解释和用户控制。等 memory 规模变大，recall 层可以替换成 hybrid search，而 store、ContextBuilder 和 trace 的边界不用推翻。

## Phase 2 推荐实施顺序

1. 升级 `MemoryEntry` 数据结构，并保持旧 JSONL 兼容。
2. 给 `JsonlMemoryStore` 增加 `forget(id)` 和 active 过滤。
3. 新增 `MemoryRecallResult` 和 `recall_with_scores(...)`。
4. 用关键词、tags、importance 做可解释 recall。
5. 更新 ContextBuilder / AgentLoop，让 trace 记录 recall score。
6. 跑 focused memory tests 和全量测试。
7. 再考虑 `/memory` CLI 或 MemoryExtractor 设计。

## Phase 2A Implementation Notes

本轮已经完成 Memory v2 的最小闭环实现，目标是让 MyAgent 从“关键词触发 JSONL 记忆”升级到“个人助理式 Markdown memory workspace”。

重要更新：

```text
旧 MemoryRecall / JSONL 关键词召回已经彻底退出主链路。
```

当前设计中：

- `MEMORY.md` 的 Core Memory / User Profile / Active Goals 默认进入 ContextBuilder。
- `daily/` 和 `MEMORY_PROPOSALS.md` 不默认进入上下文。
- 额外记忆只能通过 `memory_search` / `memory_get` 工具按需查询。
- 遗忘通过 `memory_forget` 执行。
- `myagent/memory/recall.py` 和 `tests/test_memory_recall.py` 已删除。

文档中早期关于 `MemoryRecall`、`memory_recalled`、`recall_with_scores` 的内容只代表第一阶段历史设计，不再代表当前主链路。

新增文件：

```text
myagent/memory/markdown.py
myagent/memory/extractor.py
myagent/tools/memory.py
tests/test_memory_tools.py
```

修改文件：

```text
myagent/memory/__init__.py
myagent/tools/__init__.py
myagent/agent/context.py
myagent/agent/loop.py
tests/test_memory_store.py
tests/test_context_builder.py
tests/test_agent_memory.py
```

当前落地结构：

```text
data/memory/
  MEMORY.md
  MEMORY_PROPOSALS.md
  daily/
    YYYY-MM-DD.md
```

当前实现的运行流：

```text
ContextBuilder
  -> 从 MEMORY.md 读取 Core Memory / User Profile / Active Goals
  -> 默认注入 system prompt 的 # Core Memory section

AgentLoop
  -> 注册 memory_append_daily / memory_propose_long_term / memory_search / memory_get
  -> 主 Agent 可在 live path 中通过工具写入或查询 memory
  -> final answer 发布后运行 MemoryExtractor
  -> MemoryExtractor 输出 daily candidate 或 long-term proposal
```

四个工具当前职责：

```text
memory_append_daily
  写入 daily/YYYY-MM-DD.md，适合工作观察、候选记忆、临时上下文。

memory_propose_long_term
  默认写入 MEMORY_PROPOSALS.md proposal；只有 apply=true 时才直接修改 MEMORY.md。

memory_search
  搜索 MEMORY.md 非 core section、MEMORY_PROPOSALS.md、daily notes。

memory_get
  根据 memory_id 读取完整 memory chunk。
```

重要边界：

- 旧 `JsonlMemoryStore` 暂时保留，避免一次性破坏旧模块和测试。
- 旧“用户说记住就靠关键词直接写 JSONL”的路径已经不再作为 AgentLoop 主路径。
- `AgentLoop` 默认不再把旧 JSONL memory recall 注入上下文，避免历史测试记忆污染新的个人助理 memory。
- 自动记忆默认由 post-turn `MemoryExtractor` 执行，但只写 daily candidate 或 proposal，不直接写长期 `MEMORY.md`。
- `MEMORY.md` 的 core sections 会默认进 prompt；更大的历史内容要通过工具搜索。

### Phase 2A Fix: Real Remember / Forget

本轮本地测试暴露了一个严重问题：

```text
模型说“已记住 / 已忘掉”，但底层 memory 文件未必真的变化。
```

修复内容：

- `memory_propose_long_term` 支持 `apply` 行为，默认 `apply=false`，先生成长期记忆 proposal。
- 用户明确要求“记住”的稳定资料可以使用 `apply=true`，直接写入 `MEMORY.md`。
- 自动 `MemoryExtractor` 仍然使用 `apply=false`，只写 `MEMORY_PROPOSALS.md` proposal，避免自动抽取直接污染长期记忆。
- 新增 `memory_forget(query)` 工具，可按 memory id 或文本主题从 `MEMORY.md`、`MEMORY_PROPOSALS.md`、daily notes 删除匹配记忆。
- `AgentLoop` 注册 `memory_forget`。
- `AgentLoop` 默认停止注入旧 `JsonlMemoryStore` recall；旧 JSONL 代码仅保留为兼容模块。

修复后的语义：

```text
用户说“我的名字是 lin，记住”
  -> agent 应调用 memory_propose_long_term(apply=true, section="User Profile")
  -> 写入 MEMORY.md
  -> 下一轮默认进入 Core Memory prompt

用户说“忘掉我正在准备 Java 后端面试”
  -> agent 应调用 memory_forget(query="Java 后端面试")
  -> 从 Markdown memory 文件中删除匹配项
```

这次也清理了本地 ignored memory 数据：

- 从 `data/memory/MEMORY_PROPOSALS.md` 删除错误的 Java 面试 proposal。
- 清空旧 `data/memory/facts.jsonl` 中的 Java 面试测试记忆。
- 把 `用户的名字是 lin` 写入 `data/memory/MEMORY.md` 的 `User Profile`。

本轮 focused verification：

```text
python -m pytest tests/test_memory_store.py tests/test_memory_tools.py tests/test_context_builder.py tests/test_agent_memory.py tests/test_agent_trace.py tests/test_agent_loop.py
```

结果：

```text
24 passed
```

修复后全量验证：

```text
python -m pytest
90 passed, 1 skipped
```

---

### Memory Consolidation 实现笔记

**问题**：MEMORY_PROPOSALS.md 只进不出，proposal 堆积；MEMORY.md 结构空洞。

**方案**：自动化 Consolidation 机制。

1. **统一 MEMORY.md 结构**
   - 新结构：`Profile` / `Active Goals` / `Preferences` / `Facts` / `Notes`
   - 旧结构（Core Memory / User Profile / Active Goals / Decisions / Reference Notes）保留兼容读取

2. **MemoryExtractor 更新**
   - prompt 中使用新 section 列表
   - 默认 section 从 `Core Memory` 改为 `Facts`

3. **MemoryConsolidator（新增 `myagent/memory/consolidator.py`）**
   - LLM 驱动：读取 MEMORY.md + MEMORY_PROPOSALS.md → 发给 LLM 合并 → 输出新 MEMORY.md
   - 自动归档旧 proposals 到 `memory/archive/MEMORY_PROPOSALS-时间戳.md`
   - 清空 MEMORY_PROPOSALS.md
   - LLM 输出格式不对时保留原 proposals，不丢失数据

4. **CronService 集成**
   - `CronPayload` 新增 `job_type` 字段（`user` / `system`）
   - AgentLoop 启动时自动注册系统级 `memory_consolidation` 任务，每 24 小时执行
   - `_on_cron_job` 区分系统任务和用户任务

5. **本地文件处理**
   - MEMORY.md 重写为新结构
   - MEMORY_PROPOSALS.md 归档并清空

新增测试：`tests/test_memory_consolidator.py`（6 个测试）

验证：

```text
python -m pytest tests/test_memory_consolidator.py
6 passed
```

### Memory Proposal 命名与默认写入策略更新

本轮把原先容易误解的 `DREAMS.md` 改为 `MEMORY_PROPOSALS.md`。

新的三层语义：

```text
daily/YYYY-MM-DD.md
  当前工作观察、候选事实、临时上下文。

MEMORY_PROPOSALS.md
  候选长期记忆的临时缓冲区；定时 consolidation 后会归档并清空。

MEMORY.md
  已确认、稳定、默认可进入上下文的长期记忆。
```

`memory_propose_long_term` 的默认行为改为 `apply=false`：

- 默认只创建 proposal，降低误写长期记忆的风险。
- 用户明确要求“记住”的稳定资料才使用 `apply=true` 直接写入 `MEMORY.md`。
- `MemoryExtractor` 继续只写 proposal，不直接污染 `MEMORY.md`。
- proposal 不作为长期待办池保存；它会在 consolidation 成功后被归档并清空。宁可丢掉低置信度候选，也不让候选区无限膨胀。

兼容性处理：

- 新工作区创建 `MEMORY_PROPOSALS.md`。
- 旧工作区如果只有 `DREAMS.md`，初始化时会把内容迁移到 `MEMORY_PROPOSALS.md`，并把标题替换为 `# Memory Proposals`。

验证：

```text
python -m pytest tests/test_memory_tools.py tests/test_memory_consolidator.py tests/test_agent_memory.py
14 passed

python -m pytest
218 passed
```

### MemoryExtractor 克制写入原则

为避免 `daily/` 和 `MEMORY_PROPOSALS.md` 继续膨胀，post-turn extractor 的默认策略应该保守：

- 只记录未来仍可能帮助 MyAgent 服务用户的信息。
- 不记录短回复、普通确认、一次性工具调用、文件阅读过程、已完成 turn 内部细节。
- `daily` 用于近期工作上下文、open loop、临时项目状态和不够稳定的观察。
- `long_term` 只用于稳定偏好、长期目标、身份背景、长期项目事实或重要决策。

这个策略的取舍是：

```text
少记、记准 > 什么都记下来再让系统清理。
```
## 2026-05-18 Update: Storage Boundary

Current memory storage is separate from profile and runtime state:

```text
~/.myagent/memory/
  MEMORY.md
  MEMORY_PROPOSALS.md
  daily/YYYY-MM-DD.md
```

Meaning:
- `MEMORY.md` is durable, reviewed long-term memory with three sections:
  `Always`, `Now`, and `Later`.
- `Always` is very short, stable information that should be visible every turn.
- `Now` is current project/session state that should stay visible for the near term.
- `Later` is searchable background and does not enter the prompt by default.
- `MEMORY_PROPOSALS.md` is the review queue for candidate long-term memory.
- `daily/` stores lightweight daily notes and candidates.
- `~/.myagent/profile/` stores stable human-authored profile instructions, not memory.
- `~/.myagent/runtime/` stores operational state such as cron jobs, not memory.

Prompt rule:
- ContextBuilder sees only `Always` and `Now` by default.
- `Later`, daily notes, and proposals are available through memory tools.

Renaming:
- Memory now reads and writes only `~/.myagent/memory/`.
- There is no automatic migration from `~/.myagent/workspace/`.
- `DREAMS.md` is no longer a supported input name. The current file is `MEMORY_PROPOSALS.md`.
- The old `Profile / Active Goals / Preferences / Facts / Notes` structure is replaced by `Always / Now / Later`.

## 2026-05-18 Update: Budget-Based Consolidation

`Always` and `Now` are not fixed-size lists. The model may suggest a section
when writing a proposal, but the consolidator is responsible for the final
placement.

Current consolidation policy:

- `Always` targets a small visible-memory budget, currently about 4000
  characters.
- `Now` targets a larger working-memory budget, currently about 8000
  characters.
- `Later` is searchable archival memory and is not injected by default.
- When a visible section grows too large, consolidation should merge duplicates,
  compress related details, and demote stale or lower-value items to `Later`.
- Deletion is reserved for vague, contradicted, obsolete, or low-value items.
  Old items are not deleted merely because they are old.

This keeps the design close to mature agent memory patterns:

- `Always` behaves like compact core memory.
- `Now` behaves like working memory for the current phase.
- `Later` behaves like archival memory that can be retrieved when needed.

The first implementation keeps this as an LLM consolidation rule rather than a
large deterministic ranking system. That is intentional: it solves the current
growth problem without adding vector search, scoring tables, or a separate
memory database too early.

## 2026-05-19 Update: Visible Memory Sections

Visible memory is split before it reaches ContextBuilder:

```text
Always Memory
  compact, stable, near-protected

Now Memory
  compact, current, budgeted

Later
  searchable archive, not injected by default
```

This avoids treating all long-term memory as one large section. `Always` should
survive normal budgeting because it is already compacted by consolidation.
`Now` is also compacted, but it can be dropped earlier than `Always` if the
current turn is unusually large.

The main design rule is:

```text
compress memory first; drop only as a final prompt-budget fallback
```
