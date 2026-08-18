# Architecture Decision: Native Z.AI Responses with Plaintext Assignment Handoff

## Context

`codex-glm-subagent` registers a standalone child worker (`zai_glm53_worker`,
model `glm-5.3`) alongside a parent Codex that keeps its selected GPT provider
and ChatGPT login completely unchanged. The child needs a single, explicit
transport to Z.AI that is native and direct, with no runtime provider or model
fallback.

## Decision

The child talks over the Codex Responses wire format directly to
`https://open.bigmodel.cn/api/v1` with `wire_api=responses`. Each cross-provider
assignment is staged once and injected as developer context by an exact-match
plaintext `SubagentStart` Hook before native spawn. There is no bridge, no Chat
conversion, no SQLite service state, no daemon, no MCP server, no second Codex
CLI, and no runtime provider or model fallback.

Hook is required independently of bridge. A bridge adapts wire protocols; this
Hook adapts the assignment carrier. The GLM endpoint already accepts Responses,
but the OpenAI parent to non-OpenAI child collaboration body may remain in
provider-internal ciphertext that the child cannot consume. Therefore removing
the bridge does not remove the need for the Hook.

Official source: https://docs.bigmodel.cn/cn/coding-plan/tool/codex (and its
markdown endpoint).

## Data flow

```
Parent Codex (selected GPT + ChatGPT login)
        |
        | stage complete assignment through stdin
        v
one-shot plaintext SubagentStart Hook
        |
        | exact zai_glm53_worker match + developer context
        | native spawn, fork_turns=none, reasoning_effort=max
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
  SQLite/daemon state. The Hook only carries a short-lived plaintext assignment;
  it does not proxy model traffic.
- **At-most-once assignment**: stage uses one expiring pending slot; the matching
  `SubagentStart` event atomically claims and consumes it. Missing, stale,
  malformed, replayed, or mismatched handoffs fail visibly.
- **No inherited-turn workaround**: `fork_turns=none` avoids widening the Z.AI
  data boundary and identity confusion. A new assignment gets a new handoff and
  child instead of relying on cross-provider follow-up delivery.
- **Credentials**: macOS stores the key in the Login Keychain through Apple's
  Security.framework (via Python ctypes, no keychain/security CLI); Linux reads
  `ZAI_API_KEY` from the environment. No key value is written to the
  repository, chat, issues, command arguments, or screenshots.
- **Separate activities**: install, configure, and a live smoke are distinct;
  this repository never changes the parent top-level provider or login.

## Control-plane reference

The handoff protocol is adapted from the one-shot POSIX design in
`Utopia-V/codex-deepseek-subagent` and the tested adaptation in
`ShiauweiZhao/codex-opencode-go-subagent`. Provider identity, Hook matcher,
staged envelope, skill, agent instructions, installer, and smoke oracle must
remain consistent; changing only a model or base URL is insufficient.

## Status

`locally_verified` only. This build has not been installed or configured in a
real `~/.codex` (not `configured`) and no explicitly authorized real GLM child
smoke has been performed (not `ready`). A real GLM child smoke is `ready` only
after explicit user authorization.
