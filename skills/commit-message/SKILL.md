---
name: commit-message
description: Generate concise Git commit messages from a change summary or diff.
---

# Commit Message

## Description

Help MyAgent write clear commit messages for project changes.

## When To Use

Use this skill when the user asks to:

- Write a commit message
- Summarize staged changes
- Choose a conventional commit prefix
- Prepare a small Git commit

## Instructions

- Prefer concise conventional commits.
- Use present tense.
- Keep the first line short.
- Mention the module or behavior changed.
- Do not include unrelated changes.

## Examples

```text
feat: add jsonl trace recording
feat: add explicit memory recall
docs: design skills module
fix: preserve reasoning content in tool calls
```
