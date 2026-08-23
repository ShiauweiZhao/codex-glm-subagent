# Architecture Decision: Native Z.AI Responses with Plaintext Assignment Handoff

## Context

`codex-glm-subagent` registers a standalone child worker (`zai_glm53_worker`,
model `glm-5.3`) alongside a parent Codex that keeps its selected GPT provider
and ChatGPT login completely unchanged. The child needs a single, explicit
transport to Z.AI that is native and direct, with no runtime provider or model
fallback. The parent also needs a bounded availability policy for explicit GLM
quota/token/rate-limit exhaustion.

## Decision

The child talks over the Codex Responses wire format directly to
`https://open.bigmodel.cn/api/v1` with `wire_api=responses`. Each cross-provider
assignment is staged once and injected as developer context by an exact-match
plaintext `SubagentStart` Hook before native spawn. There is no bridge, no Chat
conversion, no SQLite service state, no daemon, no MCP server, no second Codex
CLI, and no runtime provider or model fallback.

Runtime compatibility is gated by an actual staged Hook and native child
callback, not a version string. A historical Codex 0.149.0 run inherited the
OpenAI parent provider and failed before contacting Z.AI. After the sandbox-safe
handoff-state fix, the bundled codex-cli 0.148.0-alpha.21 returned the exact
native callback `ZAI_GLM53_NATIVE_OK` and `arithmetic=323`. A real provider/model
error remains visible and is not treated as capacity. The retired Codex
0.148.0-alpha.9 `CODEX_CLI_PATH` workaround is protocol-incompatible with the
current Desktop and must not be installed or activated. The recovery helper
retains only status and exact deactivation behavior for users who activated
that legacy override. OpenAI Codex Core, the parent provider/login, and the
direct Z.AI data plane remain unchanged.

Write capability adds a Guardian review seam. Codex applies
`model_catalog_json` at shared model-manager startup; the same field in an
agent role is a per-thread no-op. A separate, explicitly invoked startup-catalog
helper therefore merges the current `models_cache.json` with hidden GLM
metadata and writes one removable top-level `model_catalog_json` block. The GLM
entry sets `auto_review_model_override="glm-5.3"` so Codex does not send its
internal `codex-auto-review` identifier to the Z.AI provider. The combined
catalog retains the selected parent model and `codex-auto-review`, while hidden
visibility keeps GLM out of the parent picker. The helper does not read or
modify `auth.json`, provider settings, the selected parent model, or login.

Without the effective startup override the provider can fail with `modelCode`
not found, and Codex then fails closed before the requested patch is applied.
That condition is
`guardian_model_unavailable`, a non-capacity failure: it must not select Luna
or be described as a policy verdict. A disposable native write smoke must
exercise `apply_patch`, complete Guardian review, and verify the resulting file
before the worker is considered write-ready on a runtime/configuration pair.

Eligible bounded implementation defaults to GLM. Only an explicit GLM
quota/token/rate-limit exhaustion signal allows parent orchestration to reissue
the same self-contained job to `agent_type="worker"`,
`model="gpt-5.6-luna"`, `reasoning_effort="max"`, and `fork_turns="none"`.
This Luna path is not part of the GLM child or Z.AI data plane.

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

- **No runtime fallback**: if a step is outside the worker contract, the child
  returns `ESCALATE_TO_GPT`; it never silently switches provider or model. The
  narrow Luna path is an explicit parent orchestration reroute after verified
  capacity exhaustion; no fallback occurs inside the child.
- **No error masking**: Hook trust, failed staging, authentication, permission,
  data-boundary, model/account compatibility, malformed-assignment,
  missing-callback, and
  `ESCALATE_TO_GPT` failures do not select Luna.
- **Recovery**: a later ordinary eligible job may try GLM again and restore
  GLM-first routing after success. There is no paid recovery probe merely to
  detect returned capacity.
- **Standing authorization**: an explicit user or applicable user/project
  `AGENTS.md` instruction may authorize bounded private source handoff for its
  stated scope without per-assignment repetition. It never covers credentials,
  secrets, personal/regulated data, or out-of-scope source.
- **No bridge**: the child is not a local HTTP service and holds no persistent
  SQLite/daemon state. The Hook only carries a short-lived plaintext assignment;
  it does not proxy model traffic.
- **At-most-once assignment**: stage uses one expiring pending slot; the matching
  `SubagentStart` event atomically claims and consumes it. Missing, stale,
  malformed, replayed, or mismatched handoffs fail visibly.
- **Sandbox-safe local state**: stage and Hook derive one per-user state root
  from the process temporary directory. The root is mode `0700`; lock and
  assignment files are mode `0600`. Unsafe symlinked or foreign-owned state
  roots fail closed. A sandbox-denied stage may be retried once only after an
  exact staging approval; it does not authorize spawn or any provider change.
- **No inherited-turn workaround**: `fork_turns=none` avoids widening the Z.AI
  data boundary and identity confusion. A new assignment gets a new handoff and
  child instead of relying on cross-provider follow-up delivery.
- **Credentials**: macOS stores the key in the Login Keychain through Apple's
  Security.framework (via Python ctypes, no keychain/security CLI); Linux reads
  `ZAI_API_KEY` from the environment. No key value is written to the
  repository, chat, issues, command arguments, or screenshots.
- **Separate activities**: install, configure, and a live smoke are distinct;
  the normal installer never reads or changes `config.toml` or `auth.json`.
  Startup-catalog activation is a separate opt-in action that changes only its
  managed `model_catalog_json` block and requires a Codex Desktop restart; it
  never changes the parent provider, selected model, login, or `auth.json`.

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
