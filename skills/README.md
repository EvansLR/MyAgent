# Local Skills

This directory contains local prompt skills discovered by MyAgent.

## Built-in Project Skills

- `code-review`
- `commit-message`
- `interview-prep`

## Imported Example Skills

The following skills were copied from Anthropic's public `anthropics/skills` repository for local testing and study:

```text
https://github.com/anthropics/skills
commit: d211d437443a7b2496a3dad9575e7dddd724c585
```

Imported skills:

- `doc-coauthoring`
- `frontend-design`
- `mcp-builder`
- `skill-creator`
- `webapp-testing`

Each imported skill keeps its own `SKILL.md` and any included `LICENSE.txt`, scripts, examples, or reference files.

## How To Trigger Locally

Start MyAgent:

```text
python -m myagent
```

Then ask for a task that matches a skill description. MyAgent will see the skill metadata in `# Available Skills`.
If the model needs the full workflow, it can call:

```text
skill_get(skill_id="mcp-builder")
```

Example prompts:

```text
请使用 mcp-builder skill，帮我设计一个 GitHub issue 管理 MCP server。
```

```text
请先加载 webapp-testing skill，然后告诉我怎么测试本地前端页面。
```

```text
请使用 doc-coauthoring skill，带我写一份 ContextBuilder v2 的设计文档。
```

```text
请用 skill-creator skill，帮我设计一个适合 MyAgent 的任务复盘 skill。
```

```text
请用 frontend-design skill，帮我设计一个本地 Agent dashboard 页面。
```

You should see a tool status similar to:

```text
正在调用工具：skill_get skill_id=mcp-builder
```
