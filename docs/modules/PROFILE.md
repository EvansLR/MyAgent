# Profile Module

## Responsibility

The profile module loads stable, human-authored runtime instructions for MyAgent.
It is separate from code workspace, long-term memory, and runtime state.

```text
~/.myagent/profile/
  AGENT.md   # agent identity, principles, response style
  USER.md    # stable user profile and collaboration preferences
  TOOLS.md   # stable tool usage guidance
```

## Boundary

- Profile is written by the user or maintainer.
- Profile is injected into ContextBuilder as model-facing instruction sections.
- Profile is not memory. MyAgent does not write learned facts here.
- Profile is not runtime state. Cron jobs, trace, and session summaries live elsewhere.
- Profile is not the code workspace. Filesystem tools still use the current project root.

## Runtime Flow

```text
AgentLoop
  -> ProfileLoader
  -> ContextBuilder(profile_provider=...)
  -> system prompt sections
```

`ProfileLoader` reads only `~/.myagent/profile/` by default.
There is no fallback to the old `~/.myagent/workspace/` location.

## Context Sections

```text
AGENT.md -> Agent Instructions  priority=5   protected
USER.md  -> User Profile        priority=7   protected
TOOLS.md -> Tool Guidelines     priority=35  medium
```

`AGENT.md` and `USER.md` are protected because they define stable behavior and
user preferences. `TOOLS.md` is medium priority because tool tips are useful but
can be dropped first when prompt budget is tight.

## Code

```text
myagent/profile/__init__.py
myagent/profile/loader.py
tests/test_profile.py
```

The old `myagent.workspace.WorkspaceLoader` name was removed to avoid confusing
runtime profile with the filesystem workspace used by code tools.
