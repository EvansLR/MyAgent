# Agent Workspace 模块设计

## 职责

Agent Workspace 是 MyAgent 运行时个人助理的长期状态目录。

一句话版本：

```text
把源码仓库和运行时个人助理状态分开，让 Agent 能维护跨对话的 identity、persona、user profile 和记忆。
```

## 为什么需要它

当前 MyAgent 的源码项目位于 `E:\ClaudeCode\openSource\MyAgent`，这是开发代码的地方。

但个人助理需要长期理解用户、记住偏好、保持一致风格。这些信息不应该：

- 和源码混在一起（源码是公开的、可提交的）
- 每次重启就丢失（需要持久化）
- 只对当前项目有效（应该服务于"用户"而不是"某个代码仓库"）

引入 Agent Workspace 后：

```text
E:\ClaudeCode\openSource\MyAgent     # 源码项目
~/.myagent/workspace/               # 个人助理长期状态
```

这样 Agent 可以跨不同对话、不同任务保持一致的自我认知。

## 输入输出

### 输入

- 文件系统：workspace 目录下的 Markdown 文件
- 配置：可选的 `workspace_root` 路径覆盖

### 输出

- ContextBuilder 使用的 system prompt 片段
- Memory 模块读取/写入的长期记忆文件

## 核心接口

### WorkspaceLoader

```text
load_file(filename) -> str
load_all() -> dict[str, str]
exists(filename) -> bool
```

### WorkspaceProvider（供 ContextBuilder 使用）

```text
agent_principles() -> str      # AGENT.md（身份+原则+风格）
user_profile() -> str          # USER.md
tool_guidelines() -> str       # TOOLS.md
core_memory() -> str           # MEMORY.md
```

## 数据结构

### 目录结构（第一版）

```text
~/.myagent/workspace/
  AGENT.md        # 身份、操作原则和沟通风格
  USER.md         # 用户画像、偏好、称呼和协作方式
  TOOLS.md        # 工具使用约定和风险提示
  MEMORY.md       # 精炼后的长期记忆
  memory/
    YYYY-MM-DD.md # working memory / daily notes
```

第一版把 AGENT.md、PERSONA.md 合并为 AGENT.md，减少用户维护的文件数。PERSONA.md 仍被兼容读取（作为可选扩展），但文档推荐把风格内容写进 AGENT.md。

### 文件说明

#### AGENT.md

身份、操作原则和沟通风格。

第一版把"你是谁""你怎么做事""你怎么说话"合并到一个文件，减少维护成本。

示例内容：

```text
# MyAgent 自我设定

## 身份
你是 MyAgent，一个本地运行的个人助理。你的目标是帮助用户完成日常任务、学习问题和代码探索。

## 操作原则
- 不执行不可逆操作前必须征求用户同意
- 不访问工作区外的敏感文件
- 复杂任务先拆解步骤，再逐一执行
- 不确定时主动询问，不编造信息

## 沟通风格
- 简洁直接，不啰嗦
- 技术讨论用专业术语，日常对话轻松自然
- 承认不知道，不假装有实时信息
```

#### USER.md

用户画像、偏好、称呼和协作方式。

示例内容：

```text
# 用户画像

## 基本信息
- 称呼：开发者
- 技术栈：Python、TypeScript

## 协作偏好
- 喜欢先看到方案概述再讨论细节
- 对代码审查要求严格
- 偏好中文交流
```

#### TOOLS.md

工具使用约定和风险提示。

示例内容：

```text
# 工具使用约定

## 文件操作
- 写文件前确认路径
- 编辑前先读取原文件

## 网络工具
- web_search 结果需要交叉验证
- 不访问不明链接
```

#### MEMORY.md

精炼后的长期记忆（与 `data/memory/` 的 working memory 区分）。

```text
# 长期记忆

## 项目偏好
- 使用 pytest 做测试
- 偏好 dataclass 而不是 dict

## 重要决策
- 2024-05: 选择 Markdown-backed memory 而不是 JSONL
```

## 与其他模块的关系

### ContextBuilder

Workspace 的文件内容由 `WorkspaceProvider` 提供给 `ContextBuilder`，作为 system prompt 的组成部分。

注入顺序：

```text
Identity（固定）
Agent Principles（AGENT.md, workspace: protected）
User Profile（USER.md, workspace: protected）
Runtime Environment（固定）
Delegation Policy（固定）
Core Memory（workspace: high）
Tool Guidelines（TOOLS.md, workspace: medium）
Available Skills（medium）
Available Tools（medium）
Conversation（dynamic）
```

### Memory

- `MEMORY.md` 是 Memory 模块的"精炼输出"，由 `MemoryExtractor` 生成或手动维护。
- `memory/YYYY-MM-DD.md` 是 working memory，由 `MemoryAppendDailyTool` 写入。
- 两者区分：MEMORY.md 是"应该知道什么"，daily notes 是"最近观察了什么"。

### Skills

Workspace 中的 `skills/` 目录可以作为用户自定义 skill 的补充来源，与项目级的 `skills/` 目录合并。

### Config

`myagent.json` 可以配置 `workspace` 路径：

```json
{
  "workspace": "~/.myagent/workspace"
}
```

默认路径是 `~/.myagent/workspace/`。

## 第一阶段范围

第一版实现：

1. **目录创建**：如果 `~/.myagent/workspace/` 不存在，自动创建。
2. **文件读取**：读取 AGENT.md、USER.md、TOOLS.md、MEMORY.md，缺失时返回空字符串。
3. **ContextBuilder 注入**：把 workspace 内容作为独立 section 注入 system prompt。
4. **Trace 记录**：记录 workspace 加载状态（哪些文件存在、长度）。

推荐把身份、原则、风格全部写进 AGENT.md。

暂不创建模板文件，让用户按需创建。但文档中提供示例。

## 暂不实现

- 多 workspace 切换
- workspace 模板生成器
- 自动同步（workspace <-> 源码项目）
- 图形化 workspace 编辑器
- workspace 版本控制
- 加密/隐私保护
- 跨设备同步

## 测试点

```text
tests/test_workspace.py
```

测试内容：

1. `test_workspace_loads_existing_files`
   - 能读取 AGENT.md、PERSONA.md 等文件内容。

2. `test_workspace_returns_empty_for_missing_files`
   - 文件不存在时返回空字符串，不报错。

3. `test_workspace_provider_includes_all_sections`
   - ContextBuilder 中 workspace section 被正确注入。

4. `test_workspace_respects_custom_path`
   - 配置自定义 workspace 路径时从该路径读取。

5. `test_workspace_creates_directory_if_missing`
   - 目录不存在时自动创建。

## 面试表达

可以这样讲：

> MyAgent 区分了源码仓库和运行时个人助理状态。源码在 `E:\ClaudeCode\openSource\MyAgent`，但个人助理的长期记忆、风格设定、用户画像放在 `~/.myagent/workspace/`。这样即使换了一个代码项目，Agent 仍然记得你是谁、你喜欢怎么协作。第一版只做了文件读取和 system prompt 注入，没有做多 workspace、模板生成或同步，因为当前目标是先让"个人助理"这个概念在代码里有体现。

如果面试官问"为什么不把 workspace 放在源码目录里"，可以回答：

> 源码目录是公开的、可提交的，但个人助理状态包含用户偏好和记忆，属于私有数据。分开后，源码可以分享，workspace 保留在本地。

## Phase 2A Implementation Notes

已实现第一版 Agent Workspace 骨架。

### 新增文件

```text
myagent/workspace/__init__.py
myagent/workspace/loader.py
tests/test_workspace.py
```

### 实现内容

- `WorkspaceLoader`：读取 `~/.myagent/workspace/` 下的 Markdown 文件
- 支持文件：`AGENT.md`、`PERSONA.md`、`USER.md`、`TOOLS.md`、`MEMORY.md`
- 文件缺失时返回空字符串，不报错
- 目录不存在时自动创建
- 提供 `present_files()`、`missing_files()`、`to_trace_data()` 用于可观测性

### ContextBuilder 改动

`ContextBuilder` 新增 `workspace_provider` 参数。`build_sections()` 中按以下顺序注入 workspace 内容：

```text
Agent Principles   (AGENT.md)   priority=5,  tier=protected
User Profile       (USER.md)    priority=7,  tier=protected
Tool Guidelines    (TOOLS.md)   priority=35, tier=medium
```



### AgentLoop 改动

`AgentLoop` 初始化时自动创建 `WorkspaceLoader` 并传给 `ContextBuilder`。每个 turn 开始时记录 `workspace_loaded` trace event。

### Trace 事件

新增：

```text
workspace_loaded
  workspace_root: "C:\Users\...\.myagent\workspace"
  files_present: ["AGENT.md", "PERSONA.md"]
  files_missing: ["USER.md", "TOOLS.md"]
```

### 验证结果

```text
python -m pytest tests/test_workspace.py
8 passed

python -m pytest
152 passed
```

### 当前边界

- 不自动生成模板文件（AGENT.md 等），让用户按需创建
- 不处理 workspace 版本控制或加密
- 多 workspace 切换暂不支持
- `data/memory/MEMORY.md`（项目级）和 `~/.myagent/workspace/MEMORY.md`（个人级）并存，由 Memory 模块后续统一
