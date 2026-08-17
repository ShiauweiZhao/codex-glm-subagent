# Architecture Decision: Native Codex Responses to Z.AI

## Context

`codex-glm-subagent` registers a standalone child worker (`zai_glm53_worker`,
model `glm-5.3`) alongside a parent Codex that keeps its selected GPT provider
and ChatGPT login completely unchanged. The child needs a single, explicit
transport to Z.AI that is native and direct, with no runtime provider or model
fallback.

## Decision

The child talks over the Codex Responses wire format directly to
`https://open.bigmodel.cn/api/v1` with `wire_api=responses`. There is no
localhost bridge, no Chat conversion, no SQLite state, no daemon, no Hook, no
MCP server, no second Codex CLI, and no runtime provider or model fallback.

Official source: https://docs.bigmodel.cn/cn/coding-plan/tool/codex (and its
markdown endpoint).

## Data flow

```
Parent Codex (selected GPT + ChatGPT login)
        |
        | spawn with fork_turns=none, reasoning_effort=max
        v
zai_glm53_worker (model glm-5.3)
        |
        | Codex Responses (wire_api=responses)
        v
https://open.bigmodel.cn/api/v1
```

## Consequences

- **No fallback**: if a step is outside the worker contract, the child returns
  `ESCALATE_TO_GPT`; it never silently switches provider or model.
- **No bridge**: the child is not a local HTTP service and holds no persistent
  SQLite/daemon state.
- **Credentials**: macOS stores the key in the Login Keychain through Apple's
  Security.framework (via Python ctypes, no keychain/security CLI); Linux reads
  `ZAI_API_KEY` from the environment. No key value is written to the
  repository, chat, issues, command arguments, or screenshots.
- **Separate activities**: install, configure, and a live smoke are distinct;
  this repository never changes the parent top-level provider or login.

## Status

`locally_verified` only. This build has not been installed or configured in a
real `~/.codex` (not `configured`) and no explicitly authorized real GLM child
smoke has been performed (not `ready`). A real GLM child smoke is `ready` only
after explicit user authorization.
