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
provider/model fallback.

Official source: https://docs.bigmodel.cn/cn/coding-plan/tool/codex (and its
markdown endpoint).

## Roles and boundaries

- Parent GPT owns requirements, analysis, design, architecture, decomposition,
  review, final verification, integration, Git/GitHub, approvals, credentials,
  and consequential decisions.
- `zai_glm53_worker` does bounded implementation/extraction only, with an
  explicit writable scope and validation commands, and returns
  `ESCALATE_TO_GPT` for anything outside its contract.

## Delivery components

- Installer: `python3 scripts/install.py install`. It never edits
  `~/.codex/config.toml` or `auth.json`; no top-level provider/login change.
- macOS helper: `~/.codex/zai-glm53-subagent/bin/codex-zai-glm53-credentials`
  with `configure`, `status`, `purge`; API key stored in the Login Keychain via
  Apple's Security.framework (Python ctypes, no keychain/security CLI).
- Linux: API key provided through the `ZAI_API_KEY` environment variable.
- Skill `$use-zai-glm53-worker`: requires `fork_turns=none` and
  `reasoning_effort=max`, stages a self-contained assignment through stdin, then
  native-spawns the exact worker so the Hook injects it. Includes the Z.AI data
  boundary warning and no fallback. No paid/native smoke without explicit user
  authorization.

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
