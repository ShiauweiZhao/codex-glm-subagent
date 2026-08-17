# codex-glm-subagent

> Public repository: https://github.com/ShiauweiZhao/codex-glm-subagent

## Outcome

`codex-glm-subagent` keeps the parent Codex prompt's selected GPT provider and
ChatGPT login completely unchanged while registering a standalone child worker
named `zai_glm53_worker` that runs model `glm-5.3` through Z.AI.

The child talks natively over the Codex Responses wire format directly to
`https://open.bigmodel.cn/api/v1` with `wire_api=responses`. There is no
local bridge, no Chat conversion, no SQLite state, no daemon, no Hook, no MCP
server, no second Codex CLI, and no runtime provider or model fallback.

## Boundaries

- The parent GPT owns requirements, analysis, design, architecture, task
  decomposition, review, final verification, integration, Git/GitHub, approvals,
  credentials, and consequential decisions.
- The GLM child (`zai_glm53_worker`) performs bounded implementation/extraction
  only, with an explicit writable scope and validation commands, and returns
  `ESCALATE_TO_GPT` for unresolved design, scope expansion, safety or
  consequential judgment, missing scope/oracle, or approval boundaries.
- Install (`install`), configure (`configure`), and a live smoke are separate
  activities. This repository and its installer never change the parent
  top-level provider, model, or ChatGPT login.

## Architecture / Data Flow

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

Single explicit transport path, native and direct. No runtime fallback exists in
the child.

Official source:
https://docs.bigmodel.cn/cn/coding-plan/tool/codex (and its markdown endpoint).

## Requirements

- A Codex installation that supports spawning a standalone registered worker
  with a native Responses transport.
- Python 3.11 or newer for the installer
  (`python3 scripts/install.py install`).
- macOS: the installer stores the API key in the Login Keychain through Apple's
  Security.framework (via Python ctypes); no keychain/security CLI tool is
  required.
- Linux: the API key is provided through the `ZAI_API_KEY` environment variable.
- Internet access to `https://open.bigmodel.cn`.

## Install

Run the installer from the repository root:

```
python3 scripts/install.py install
```

The installer registers the standalone child and helper tooling. It never edits
`~/.codex/config.toml` or `auth.json`; the parent top-level provider and login
remain untouched. No API key is written into the repository, chat, issues,
command arguments, or screenshots.

## macOS Configure

After install, the macOS helper is available at:
`~/.codex/zai-glm53-subagent/bin/codex-zai-glm53-credentials`

```
~/.codex/zai-glm53-subagent/bin/codex-zai-glm53-credentials configure
~/.codex/zai-glm53-subagent/bin/codex-zai-glm53-credentials status
~/.codex/zai-glm53-subagent/bin/codex-zai-glm53-credentials purge
```

`configure` stores the API key in the Login Keychain. `status` reports
configuration state without printing the key. `purge` removes only that exact
macOS Keychain item.

## Linux Configure

On Linux, set the API key through the environment:

```
export ZAI_API_KEY=<your-key>
```

The key is read from `ZAI_API_KEY`; it is never stored in a config file that the
installer manages, and never placed in the repository or command arguments.

## Use / Delegation

- The `$use-zai-glm53-worker` skill requires `fork_turns=none` and
  `reasoning_effort=max`.
- Assignments are self-contained, direct spawns with an explicit writable scope
  and validation commands.
- The skill and worker warn about the Z.AI data boundary.
- No fallback provider or model is used; if a step is outside the worker's
  contract it returns `ESCALATE_TO_GPT`.
- A paid or native live smoke requires explicit user authorization and is never
  triggered incidentally.

## Local Tests

Local validation (no paid API contact):

```
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 -m compileall -q src tests
```

Behavior changes are written tests-first.

## Uninstall

Normal uninstall:

```
python3 scripts/install.py uninstall
```

Uninstall preserves credentials. To also remove the stored key, run the macOS
helper `purge` step or explicitly pass `--purge-secrets`, which removes only the
exact macOS Keychain item.

## Verification Levels

Documentation and tests distinguish three levels:

- `locally_verified`: repository tests and an isolated temp-home install smoke
  passed without a paid API.
- `configured`: the worker and helper are installed into a real Codex home and
  credentials have been supplied.
- `ready`: verified by an explicitly authorized real GLM child smoke.

Current status is `locally_verified` only: this build has not been installed or
configured in a real `~/.codex` (so it is **not** `configured`) and no
explicitly authorized real GLM child smoke has been performed (so it is **not**
`ready`). Do not report a live service as verified without an authorized smoke.

## Security

- Never put API keys in the repository, chat, issues, command arguments, or
  screenshots.
- macOS stores the key in the Login Keychain; Linux uses `ZAI_API_KEY` in the
  environment.
- No runtime fallback means there is no path that silently switches provider or
  credentials.
- See SECURITY.md for reporting guidance.

## License

Apache-2.0. See LICENSE.
