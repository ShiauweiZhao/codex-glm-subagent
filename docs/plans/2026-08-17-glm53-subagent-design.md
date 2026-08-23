# Design Plan: codex-glm-subagent

Date: 2026-08-17

Public repository: https://github.com/ShiauweiZhao/codex-glm-subagent

## Goal

Keep the parent Codex selected GPT/provider and ChatGPT login unchanged while
registering a standalone child `zai_glm53_worker` running model `glm-5.3`.

## Transport

Native Codex Responses directly to `https://open.bigmodel.cn/api/v1` with
`wire_api=responses`. Assignment delivery uses a one-shot plaintext
`SubagentStart` Hook because that control-plane requirement is independent of
whether the model data plane needs a bridge. GLM needs no bridge: there is no
Chat conversion, SQLite service state, daemon, MCP, second Codex CLI, or runtime
provider/model fallback. Explicit GLM quota/token/rate-limit exhaustion may be
handled outside that data plane by a temporary parent orchestration reroute to
`gpt-5.6-luna`.

Official source: https://docs.bigmodel.cn/cn/coding-plan/tool/codex (and its
markdown endpoint).

## Roles and boundaries

- Parent GPT owns requirements, analysis, design, architecture, decomposition,
  review, final verification, integration, Git/GitHub, approvals, credentials,
  and consequential decisions.
- `zai_glm53_worker` does bounded implementation/extraction only, with an
  explicit writable scope and validation commands, and returns
  `ESCALATE_TO_GPT` for anything outside its contract.
- Eligible bounded jobs default to GLM. Only verified quota/token/rate-limit
  exhaustion permits the GPT parent to reissue the same self-contained job to
  `agent_type="worker"`, `model="gpt-5.6-luna"`,
  `reasoning_effort="max"`, `fork_turns="none"`. This parent orchestration is
  no runtime fallback inside the GLM worker or Z.AI provider.
- Hook trust, staging, authentication, permission, data-boundary, model/account
  compatibility, assignment, missing-callback, and `ESCALATE_TO_GPT` failures
  stay visible and never select Luna. Retry GLM through a later ordinary eligible
  job; use no paid recovery probe.
- An explicit user or applicable user/project `AGENTS.md` instruction is
  standing authorization for bounded private source handoff only in its stated
  scope. It excludes secrets, credentials, personal/regulated data, and
  out-of-scope source.

## Delivery components

- Installer: `python3 scripts/install.py install`. It never edits
  `~/.codex/config.toml` or `auth.json`; no top-level provider/login change.
- Explicit startup-catalog helper:
  `~/.codex/zai-glm53-subagent/bin/codex-glm53-startup-catalog activate`.
  This separate opt-in action preserves the parent model catalog, injects
  hidden GLM review metadata, changes only its managed top-level
  `model_catalog_json` block, and requires a Codex Desktop restart. It never
  reads or changes `auth.json`, provider settings, the selected model, or login.
- macOS helper: `~/.codex/zai-glm53-subagent/bin/codex-zai-glm53-credentials`
  with `configure`, `status`, `purge`; API key stored in the Login Keychain via
  Apple's Security.framework (Python ctypes, no keychain/security CLI).
- Linux: API key provided through the `ZAI_API_KEY` environment variable.
- Skill `$use-zai-glm53-worker`: requires `fork_turns=none` and
  `reasoning_effort=max`, stages a self-contained assignment through stdin, then
  native-spawns the exact worker so the Hook injects it. Includes the Z.AI data
  boundary warning and no runtime fallback inside GLM. No paid/native smoke
  without explicit user authorization.

## Security

Never put API keys in the repository, chat, issues, command arguments, or
screenshots. Normal uninstall preserves credentials; explicit `--purge-secrets`
removes only the exact macOS Keychain item.

## Verification

Local validation (no paid API contact):

```
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 -m compileall -q src tests
```

Levels: `locally_verified`, `configured`, `ready`. Current status is
`locally_verified` only; this build has not been installed/configured in a real
`~/.codex` (not `configured`) and no explicitly authorized real GLM child smoke
has been performed (not `ready`).
