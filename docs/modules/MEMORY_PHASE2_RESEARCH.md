# Memory Phase 2 外部调研与改造方向

## 目标

这份文档用于给 MyAgent 的 Memory 第二阶段升级定方向。

重要定位：

- MyAgent 是用户个人助理型 Agent，不只是 coding agent。
- Memory 的核心目标是服务“长期陪伴式协作”和“个人工作状态延续”。
- OpenClaw 这类 local-first personal agent 是更贴近的参考对象。
- Codex、Claude Code、AGENTS.md 等 coding agent 经验只作为补充，不应主导 Memory 设计。

原则：

- 不凭主观想象设计。
- 先参考成熟 Agent / Coding Agent / Memory 系统的做法。
- 只采纳适合 MyAgent 当前阶段的部分。
- 保持项目定位：轻量、可教学、可面试、本地可跑。

## 调研对象

本轮重点参考：

- OpenClaw memory
- OpenAI ChatGPT Memory
- OpenAI Agents SDK long-term memory cookbook
- OpenAI Codex / AGENTS.md 思路
- Anthropic Claude Code memory
- Letta / MemGPT memory
- LangGraph / Deep Agents memory
- Zep agent memory

## 外部系统经验

### OpenAI ChatGPT Memory

来源：

- https://help.openai.com/en/articles/8590148-memory-in-chatgpt-remembering-what-you-chat-about
- https://help.openai.com/en/articles/8983136-what-is-memory

关键设计：

- 区分 Saved Memories 和 Reference Chat History。
- Saved Memories 更像用户希望长期保留的资料、偏好和目标。
- Chat History 是从过去对话中动态提取有用信息，不保证记住每个细节。
- 用户可控制：关闭、删除单条、清空、临时聊天不使用 memory。
- Saved Memories 与聊天记录分开存储；删除聊天不等于删除 memory。
- 系统可以更新、合并、删除 memory，但用户应能查看和管理。

可采纳经验：

- MyAgent 应明确区分“长期记忆”和“会话历史”。
- Memory 必须支持用户可见、可删除、可关闭。
- 显式记忆是第一优先级；自动记忆可以后置，但必须可解释。
- 需要避免“用户以为删了聊天，memory 还在”的困惑；本地 CLI 应提供查看/删除路径。

不立即采纳：

- 不做复杂产品级隐私设置页。
- 不做跨设备同步。
- 不做全量 chat history 自动建模。

### OpenAI Agents SDK Cookbook

来源：

- https://cookbook.openai.com/examples/agents_sdk/context_personalization

关键设计：

- 使用 local-first state object 作为 memory 单一事实源。
- 区分 profile、global memory、session memory。
- session notes 是暂存区，global notes 是长期记忆。
- 在运行中 distill memory，结束时 consolidate memory。
- consolidation 要做去重、冲突处理、只保留 durable facts。
- 注入 context 时有 precedence rules。
- memory note 包含 `last_updated`、`keywords` 等字段，便于解释、检索、合并。

可采纳经验：

- MyAgent 第二版可以引入“候选记忆 -> 长期记忆”的两段式流程。
- 可以先用规则或轻量 LLM prompt 做 MemoryExtractor。
- MemoryEntry 应加入 tags/keywords、importance、updated_at。
- 需要 MemoryConsolidator，负责去重、合并、冲突处理。
- session-only 信息不能直接进入长期 memory。

不立即采纳：

- 不引入完整 Agents SDK state object。
- 不做复杂 CRM/profile hydration。
- 不做领域强绑定的 memory schema。

### OpenAI Codex / AGENTS.md

来源：

- https://openai.com/index/introducing-codex/
- https://github.com/openai/codex/blob/main/docs/agents_md.md

关键设计：

- Codex 使用仓库内的 `AGENTS.md` 提供项目级长期上下文。
- `AGENTS.md` 像 README，但面向 Agent，包含导航、测试命令、项目规范。
- 更深层目录的 instruction 可以覆盖或补充上层 instruction。
- 每个任务在独立环境中执行，强调可验证证据、测试日志和用户复核。

可采纳经验：

- MyAgent 的 Memory 不只保存用户偏好，也应保存项目级 procedural memory。
- 已有 `AGENTS.md` 可以视为项目级 procedural memory。
- Memory 应有 scope：user、project、session。
- 项目级 memory 应偏 Markdown、可读、可提交；用户私有 memory 应不提交。

不立即采纳：

- 不做完整 AGENTS.md 层级解析系统。
- 不把所有 memory 都塞进仓库文档。

### Claude Code Memory

来源：

- https://docs.anthropic.com/en/docs/claude-code/memory
- https://docs.anthropic.com/en/docs/claude-code/settings

关键设计：

- Claude Code 使用多层 memory 文件：
  - enterprise policy
  - project memory
  - user memory
  - local project memory
- `CLAUDE.md` 会被加载进上下文。
- 支持 import 其他文件，递归深度有限制。
- 从 cwd 递归向上查找 memory，也能按子树懒加载相关 memory。
- 可以用 `#` 快捷方式快速添加 memory。
- 可以用 `/memory` 直接编辑 memory。
- 强调 memory 最佳实践：具体、结构化、定期 review。
- settings 与 memory 分离：memory 是上下文，settings 是权限和行为配置。

可采纳经验：

- MyAgent 应分清 memory 文件和 settings 文件。
- 可以引入 `/memory` 或 `myagent memory` 子命令，用于查看、添加、删除。
- Memory 内容应该使用 Markdown 组织，便于人 review。
- 项目级 memory 和用户级 memory 应分开。
- 子目录级 memory/skills 可以后置，但这个思路适合未来代码项目场景。

不立即采纳：

- 不做企业级 policy 层。
- 不做完整 recursive import。
- 不做复杂权限 settings。

### OpenClaw Memory

来源：

- https://github.com/openclaw/openclaw/blob/main/docs/concepts/memory.md
- https://openclaw.im/docs/concepts/memory
- https://openclawlab.com/en/docs/concepts/memory/

关键设计：

- memory 的事实源是本地 Markdown 文件，没有隐藏状态。
- 典型层次：
  - `MEMORY.md`：长期、精炼、耐久记忆。
  - `memory/YYYY-MM-DD.md`：每日记录、运行上下文和观察。
  - `MEMORY_PROPOSALS.md`：后台整理和 promotion 候选，供人工 review。
- `memory_search` 和 `memory_get` 是工具；搜索只返回片段，不返回整文件。
- 支持 hybrid search：关键词 + 向量。
- 使用 SQLite index、chunking、embedding cache、MMR reranking、recency boost。
- 有 pre-compaction memory flush，避免上下文压缩前丢失重要信息。
- dreaming 是后台 consolidation：收集短期信号，评分，通过阈值后提升为长期 memory。

可采纳经验：

- MyAgent 可以采用双层文件结构：
  - `MEMORY.md` 或 `global.jsonl` 保存长期精炼事实。
  - `memory/YYYY-MM-DD.md` 或 daily JSONL 保存每日候选记忆。
- 长期 memory 不应直接堆原始对话，应经过 consolidation。
- Memory search 应先返回片段和来源，不直接塞完整文件。
- pre-compaction flush 对 MyAgent 暂时没有必要，但“阶段结束前整理 memory”值得后置记录。
- dreaming 可以简化成手动或命令触发的 `memory review`。

不立即采纳：

- 不上 SQLite vector index。
- 不做 embedding cache。
- 不做 cron dreaming。
- 不做 memory wiki。

### Letta / MemGPT

来源：

- https://docs.letta.com/guides/agents/memory
- https://docs.letta.com/guides/agents/memory-blocks/
- https://docs.letta.com/guides/agents/archival-memory

关键设计：

- 区分 core memory 和 archival memory。
- Core memory 是始终可见的 memory blocks。
- Archival memory 是按需语义检索的外部存储。
- memory block 有 label、description、value、limit。
- description 很重要，告诉 agent 这个 block 怎么用。
- block 可以 read-only，适合共享政策或组织信息。
- archival memory 通过工具插入和搜索，支持 tags。
- archival memory 与 conversation search 区分：
  - archival 是主动整理的长期知识。
  - conversation search 是查历史原话。

可采纳经验：

- MyAgent 可以把最重要的长期记忆做成 always-visible “profile block”。
- 大量细节放进 searchable memory。
- MemoryEntry 应包含 tags。
- 每个 memory block 应有 description 和 size limit。
- read-only memory 对项目规范/用户偏好很有价值。

不立即采纳：

- 不做多 agent 共享 block。
- 不做完整 block API。
- 不做无限 archival database。

### LangGraph / Deep Agents

来源：

- https://docs.langchain.com/oss/javascript/langgraph/memory
- https://docs.langchain.com/oss/python/deepagents/long-term-memory

关键设计：

- 区分 short-term memory 和 long-term memory。
- long-term memory 可按 namespace/key 存储。
- 记忆类型包括：
  - semantic memory：事实和偏好。
  - episodic memory：过去经历、成功路径、任务案例。
  - procedural memory：规则、技能、提示词和做事方式。
- 写入策略分 hot path 和 background。
  - hot path：当前 turn 内写，立即可用，但增加延迟和复杂度。
  - background：异步整理，不影响响应，但记忆更新有延迟。
- Deep Agents 强调 filesystem-backed memory，用户控制存储位置。
- Retrieval 可以是 prompt-loaded，也可以按需工具搜索。
- Memory 权限可分 read-write 和 read-only。

可采纳经验：

- MyAgent 应明确三类 memory：semantic、episodic、procedural。
- 当前 `AGENTS.md` 和 `skills/` 更接近 procedural memory。
- 当前 session history 是 short-term memory，不应和 long-term memory 混淆。
- 第二版优先做 semantic memory；episodic/procedural 先文档化。
- hot path 只处理显式记忆；background consolidation 后置。

不立即采纳：

- 不做 LangGraph checkpoint。
- 不做跨 namespace 复杂 filter。
- 不做生产数据库 store。

### Zep

来源：

- https://help.getzep.com/docs

关键设计：

- 使用 knowledge graph 表示实体、事实和关系。
- 支持 fact invalidation：新事实使旧事实失效时记录有效/失效时间。
- 生成 memory context string，注入给 chatbot。
- 支持 JSON/text/message ingestion。

可采纳经验：

- MyAgent 后续可以考虑 fact validity 和 conflict tracking。
- 记忆应该能表达“旧事实已失效”，而不是只 append 新事实。
- ContextBuilder 注入的应该是经过整理的 memory context，而不是原始存储。

不立即采纳：

- 不做 knowledge graph。
- 不做实体关系抽取。
- 不做复杂 fact invalidation 系统。

## 综合结论

各系统有一个共识：

```text
Memory 不是简单把历史聊天塞回 prompt。
Memory 是分层、可管理、可检索、可审查的状态系统。
```

对 MyAgent 来说，最值得采纳的是：

1. 优先把 Memory 当成个人助理的长期状态，而不是聊天记录或代码仓库说明。
2. 分清 memory scope：profile、project、working。
3. 分清 memory type：preference、fact、decision、task、insight。
4. 分清 memory lifecycle：candidate、active、archived、forgotten。
5. 分清 memory retrieval：always-visible profile/project block、search-on-demand working notes。
6. 保持 local-first，人类可读、可检查。
7. 支持用户控制：查看、删除、关闭。
8. 从简单可解释召回开始，后续再引入 embedding 或 hybrid search。

coding agent 的经验仍然有用，但要降级为辅助参考：

- Codex / AGENTS.md 适合启发 project/procedural memory。
- Claude Code 适合启发分层 memory 文件和 `/memory` 管理体验。
- 但 MyAgent 不应该只记“项目怎么构建和测试”，更应该记用户目标、偏好、长期任务和工作上下文。

## MyAgent 推荐改造方向

### 总体方向

MyAgent 不应该直接跳到向量库或复杂 RAG，也不应该只照搬 coding agent 的 repo memory。

第二版建议目标是：

```text
从“显式关键词记忆”升级为“面向个人助理的轻量长期状态系统”。
```

### Memory 分层

建议引入三层：

```text
Profile Memory
  用户长期偏好、目标、协作方式和稳定约束。

Project Memory
  当前项目、长期任务、阶段决策和路线状态。

Working Memory
  最近阶段的候选信息、观察、临时计划和还没沉淀的上下文。
```

第一版落地可以继续用 JSONL：

```text
data/memory/inbox.jsonl
data/memory/facts.jsonl
```

或者用更人类可读的 Markdown：

```text
data/memory/MEMORY.md
data/memory/daily/YYYY-MM-DD.md
```

对 MyAgent 当前代码来说，JSONL 改动更小；Markdown 更适合人工 review。建议第二版先保留 JSONL，同时在文档里预留 Markdown summary。

更贴近个人助理定位的落地文件可以是：

```text
data/memory/profile.jsonl
data/memory/project.jsonl
data/memory/working.jsonl
```

### Memory 类型

建议给 `MemoryEntry` 增加：

```text
scope: profile | project | working
kind: preference | fact | decision | task | insight
status: active | candidate | archived | forgotten
importance: int
tags: list[str]
created_at
updated_at
last_used_at
source_message_preview
```

第二版优先实现：

```text
kind
scope
importance
tags
updated_at
```

`status`、`last_used_at` 可以后置。

### 写入策略

参考 OpenClaw、Claude Code 和 OpenAI Agents SDK 后，MyAgent 不应只有单一 `MemoryObserver`。

应采用三条路径：

```text
Live path
  主 Agent 通过 memory tools 主动写入或提出长期记忆。

Post-turn path
  每轮完成后 MemoryExtractor 后处理 transcript，补漏候选记忆。

Consolidation path
  手动或后台 review/dreaming，从 daily notes/candidates 晋升到 MEMORY.md。
```

#### Live path：memory tools

建议给主 Agent 暴露：

```text
memory_append_daily
memory_propose_long_term
memory_search
memory_get
```

这对应 OpenClaw / Claude 的 live memory write 思路：

- 用户显式要求记忆时，agent 调用 memory tool。
- 模型判断当前信息长期有用时，也可以调用 memory tool。
- `memory_propose_long_term` 只生成 proposal，不让模型直接随意修改长期记忆文件。

#### Post-turn path：MemoryExtractor

每轮结束后运行：

```text
user message + assistant answer + trace summary
  -> MemoryExtractor
  -> candidates
  -> daily notes / inbox
```

这对应 OpenAI Agents SDK 的 run/session 后抽取思路。

MyAgent 是个人助理项目，第一版可以默认每轮运行，不必为了 token 过度保守。

#### Consolidation path：Dreaming / Review

定期或手动读取：

```text
daily notes
candidates
existing MEMORY.md
```

然后：

- 去重。
- 合并。
- 检查冲突。
- 评分。
- 生成 promotion proposal。

这对应 OpenClaw Dreaming。

长期 `MEMORY.md` 应只接收整理后的 high-signal content。

### 召回策略

当前召回是关键词重叠。

建议第二版升级为可解释 scoring：

```text
score =
  keyword_overlap * 3
  + tag_overlap * 4
  + importance
  + recency_bonus
```

并返回 debug 信息给 trace：

```text
memory_recalled:
  memory_id
  score
  matched_terms
  matched_tags
```

暂不引入 embedding，但接口要预留：

```text
MemoryRecall.recall(query) -> list[MemoryRecallResult]
```

### Context 注入

不要把所有 memory 都塞进 prompt。

参考 Letta / MemGPT 的 Core Memory / Archival Memory 分层，以及 OpenClaw / Claude Code 默认加载高信号 memory 文件的做法，MyAgent 采用：

```text
Core Memory
  默认进入 system prompt 的高信号长期记忆。

Searchable Memory
  不默认进入 prompt，通过 memory_search / memory_get 按需检索。
```

建议 ContextBuilder 默认注入 Core Memory：

```text
# Memory

## Core Memory
- ...

## User Profile
- ...
```

规则：

- Core Memory 来自 `MEMORY.md` 中被标记为 in-context 的 section。
- user/profile 类高优先级，少量 always-visible。
- decisions、reference notes、daily notes、memory proposals 等走 memory_search。
- 每条 memory 尽量短。
- source/score 进入 trace，不进入 prompt。

`memory_search` 的职责不是取代 Core Memory，而是查找未默认注入的 out-of-context memory。

### 用户控制

建议增加轻量 CLI 子命令或 slash command：

```text
/memory list
/memory add <text>
/memory forget <id>
```

如果不想扩展交互命令，也可以先做 Python API 和测试，再后置 CLI。

第二版至少要保证：

- 能列出 memory。
- 能删除或标记 forgotten。
- 能说明 memory 存在哪个文件。

### Consolidation

不要第一步就做自动 dreaming。

建议先实现手动 review/consolidate：

```text
myagent memory review
```

或先只写设计，不实现命令。

Consolidation 规则：

- 去掉 session-only 信息。
- 合并重复事实。
- 新事实冲突旧事实时保留两者并标记冲突，或归档旧事实。
- 长期 memory 只保留耐久、可复用信息。

### 不建议现在做

暂不做：

- 向量数据库。
- SQLite schema 迁移。
- knowledge graph。
- 自动全量 chat history 建模。
- 后台 cron dreaming。
- 多用户云同步。
- 复杂隐私设置页。

## 推荐实施顺序

### Step 1：Memory 文档校准

更新 `docs/modules/MEMORY.md`：

- 增加 Phase 2 Review。
- 写明外部调研结论。
- 明确第二版只做轻量结构化 memory。

### Step 2：数据结构升级

扩展 `MemoryEntry`：

```text
kind
scope
importance
tags
updated_at
```

保持向后兼容旧 JSONL。

### Step 3：召回结果结构化

新增：

```text
MemoryRecallResult
```

包含：

```text
entry
score
matched_terms
matched_tags
```

### Step 4：可解释召回

实现关键词 + tag + importance + recency 的轻量打分。

### Step 5：Trace 增强

`memory_recalled` 记录：

```text
memory_id
score
matched_terms
matched_tags
```

### Step 6：Memory 管理能力

优先做最小 API：

```text
list_entries
forget(id)
```

CLI `/memory` 可以后置。

### Step 7：MemoryExtractor 设计

先写文档和 fake provider 测试，不急着接真实 LLM。

## 面试表达

可以这样讲：

> MyAgent 是个人助理型 Agent，所以 Memory 的核心不是保存聊天历史，也不只是保存代码项目说明，而是维护用户和项目的长期工作状态。我参考 OpenClaw 的 local-first memory 思路，再吸收 ChatGPT、Claude Code、Letta 和 LangGraph 的分层经验，第二版先做 profile/project/working 三层 memory，让它本地可查、可删、可解释，再逐步扩展自动抽取和整理。

如果被问到为什么不直接用向量检索：

> 当前 MyAgent 的 memory 数据量很小，直接上向量库会增加依赖和解释成本。更重要的是先把 memory lifecycle 做清楚：哪些信息值得记、怎么管理、怎么删除、怎么注入上下文。召回层保留接口，未来可以把关键词打分替换成 hybrid search。

如果被问到和 ChatGPT Memory 的区别：

> ChatGPT Memory 是产品级系统，有 saved memories 和 chat history 两条线；MyAgent 第二版借鉴这个分层，但保持本地文件存储和可测试接口。用户明确保存的 memory 优先进入长期事实，自动抽取先进入候选区，避免乱记。

## 参考链接

- OpenAI ChatGPT Memory FAQ: https://help.openai.com/en/articles/8590148-memory-in-chatgpt-remembering-what-you-chat-about
- OpenAI What is Memory: https://help.openai.com/en/articles/8983136-what-is-memory
- OpenAI Agents SDK context personalization cookbook: https://cookbook.openai.com/examples/agents_sdk/context_personalization
- OpenAI Codex introduction: https://openai.com/index/introducing-codex/
- OpenAI Codex AGENTS.md docs: https://github.com/openai/codex/blob/main/docs/agents_md.md
- Claude Code memory: https://docs.anthropic.com/en/docs/claude-code/memory
- Claude Code settings: https://docs.anthropic.com/en/docs/claude-code/settings
- OpenClaw memory overview: https://github.com/openclaw/openclaw/blob/main/docs/concepts/memory.md
- OpenClaw memory docs: https://openclaw.im/docs/concepts/memory
- Letta memory overview: https://docs.letta.com/guides/agents/memory
- Letta memory blocks: https://docs.letta.com/guides/agents/memory-blocks/
- Letta archival memory: https://docs.letta.com/guides/agents/archival-memory
- LangGraph memory overview: https://docs.langchain.com/oss/javascript/langgraph/memory
- Deep Agents long-term memory: https://docs.langchain.com/oss/python/deepagents/long-term-memory
- Zep key concepts: https://help.getzep.com/docs
