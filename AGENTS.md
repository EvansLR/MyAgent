# AGENTS.md

This file defines how AI coding agents should collaborate in this repository.
Treat it as project-level operating guidance, not as runtime behavior for the
application itself.

## Core Collaboration Principles

- Prefer documentation before implementation. Clarify the module goal, scope,
  interfaces, and tradeoffs before writing code.
- Keep work aligned with the current project stage. Build the smallest runnable
  version first, then improve it incrementally.
- Optimize for explainability. This project should be easy to discuss in an
  interview or learning context, so code and docs should make design choices
  clear.
- Avoid over-engineering. Do not introduce production-grade complexity unless it
  directly supports the current goal.
- Preserve user intent. If the user has established a workflow or preference,
  follow it unless there is a strong technical reason to ask for a change.

## Documentation Workflow

Before implementing a meaningful module or feature:

1. Read the relevant existing docs.
2. Create or update the module design document.
3. Make sure the doc explains what will be built and what will be deferred.
4. Implement the minimal useful version.
5. Update the same module doc with implementation notes after coding.

Module docs should generally explain:

- Responsibility
- Motivation
- Inputs and outputs
- Core interfaces
- Relationship to other modules
- First-stage scope
- Deferred work
- Test strategy
- How to explain the design in an interview

Implementation notes should help a reader understand the code, including:

- Files added or changed
- Important classes and functions
- Runtime flow
- Manual test steps
- Automated test coverage
- Current limitations

## Engineering Style

- Follow existing local patterns before adding new abstractions.
- Keep modules small and boundaries clear.
- Prefer explicit, testable interfaces over hidden behavior.
- Use simple data structures unless the problem clearly needs more.
- Add abstractions only when they reduce real complexity or match an existing
  pattern.
- Keep comments concise and useful; avoid comments that merely repeat the code.
- Do not mix unrelated refactors into feature work.
- Treat local configuration, secrets, generated data, traces, and caches as
  non-committable unless the user explicitly says otherwise.

## Testing Expectations

- Add focused tests for meaningful behavior.
- Prefer fake providers, fake clients, local fixtures, and project-local test
  workspaces over real network dependencies.
- Test behavior and boundaries rather than private implementation details.
- If a feature cannot be fully covered by automated tests, document a manual
  test path.
- Run the relevant tests before reporting that a feature is ready.

## Git Workflow

- Do not commit automatically after implementation.
- Wait for the user to test or confirm.
- Commit at module-level granularity rather than every tiny edit.
- Keep commits focused on related changes.
- After the user confirms, commit and push to the remote repository when this
  project is configured to do so.
- Never revert user changes unless the user explicitly asks for that.

## User Experience

- Keep CLI output understandable and calm.
- Show useful progress for long-running or tool-driven work.
- Prefer user-facing status text that explains what is happening without
  exposing unnecessary internals.
- When tools are shown in the terminal, keep tool names stable and code-facing,
  while surrounding text can be human-friendly.

## Learning and Interview Orientation

When designing a feature, be ready to explain:

- Why this module exists
- What problem it solves
- How it connects to upstream and downstream modules
- Why the current implementation is intentionally simplified
- How it could evolve in a production system

The best version of a feature is not always the most complete one. For this
kind of project, a clear, runnable, well-documented implementation is usually
more valuable than a large system that is hard to explain.

