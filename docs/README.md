# MyAgent Docs

这份目录索引用来减少文档入口混乱。

## 先读

1. `NEXT_STEPS.md`
   - 当前状态、最近决策、建议下一步。
   - 新对话续接优先读它。

2. `ARCHITECTURE.md`
   - 总体架构和 personal assistant runtime 定位。

3. `DECISIONS.md`
   - 已确认的重要设计决策。

4. `PROJECT_PLAYBOOK.md`
   - 开发节奏和文档优先工作法。

## 历史计划

- `PHASE1_PLAN.md`
  - Phase 1 历史计划。

- `PHASE2_REVIEW_PLAN.md`
  - Phase 2 模块复盘方法和历史范围。
  - 不再作为当前下一步入口。

- `PERSONAL_AGENT_DIRECTION.md`
  - 个人助理方向调研和 OpenClaw 风格参考。

## 模块文档

模块设计和实现记录放在 `docs/modules/`：

- `AGENT_LOOP.md`
- `CLI_CHANNEL.md`
- `CONFIG.md`
- `CONTEXT_BUILDER.md`
- `LLM_PROVIDER.md`
- `MCP.md`
- `MEMORY.md`
- `MESSAGE_BUS.md`
- `SKILLS.md`
- `SUBAGENT.md`
- `TOOL_REGISTRY.md`
- `TRACE.md`
- `WORKSPACE.md`

研究性或阶段性调研文档保留在对应模块旁边，例如：

- `CONTEXT_BUILDER_PHASE2_RESEARCH.md`
- `MEMORY_PHASE2_RESEARCH.md`

这些文档记录历史依据，不一定代表当前下一步。当前状态以 `NEXT_STEPS.md` 为准。

## 阶段报告

阶段性总结和展示材料放在 `docs/reports/`：

- `reports/PROJECT_STAGE_REPORT_2026-05-17.md`
  - 当前阶段项目报告，覆盖项目定位、已完成能力、最近 Feishu/Gateway 工作、验证状态、当前限制和下一步建议。
