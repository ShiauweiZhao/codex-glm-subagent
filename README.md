# codex-glm-subagent

> Public repository: https://github.com/ShiauweiZhao/codex-glm-subagent

## Outcome

`codex-glm-subagent` keeps the parent Codex prompt's selected GPT provider and
ChatGPT login completely unchanged while registering a standalone child worker
named `zai_glm53_worker` that runs model `glm-5.3` through Z.AI.

The child talks natively over the Codex Responses wire format directly to
`https://open.bigmodel.cn/api/v1` with `wire_api=responses`. The parent delivers
each complete assignment through an installed one-shot plaintext
`SubagentStart` Hook. There is no local bridge, no Chat conversion, no SQLite
service state, no daemon, no MCP server, no second Codex CLI, and no runtime
provider or model fallback inside the GLM child or Z.AI data plane. An explicit
GLM quota/token/rate-limit failure may instead trigger a temporary parent
orchestration reroute to a native `gpt-5.6-luna` worker.

Hook is required independently of bridge: the Hook fixes the cross-provider
assignment carrier, while a bridge would only adapt an incompatible wire API.
GLM-5.3 already supports the Responses wire directly, so it needs the Hook but
does not need a bridge.

## Boundaries

- The parent GPT owns requirements, analysis, design, architecture, task
  decomposition, review, final verification, integration, Git/GitHub, approvals,
  credentials, and consequential decisions.
- The GLM child (`zai_glm53_worker`) performs bounded implementation/extraction
  only, with an explicit writable scope and validation commands, and returns
  `ESCALATE_TO_GPT` for unresolved design, scope expansion, safety or
  consequential judgment, missing scope/oracle, or approval boundaries.
- Eligible bounded implementation defaults to GLM-5.3. Only explicit
  quota/token/rate-limit exhaustion permits the parent to reissue that same
  self-contained job to `agent_type="worker"`, `model="gpt-5.6-luna"`,
  `reasoning_effort="max"`, `fork_turns="none"`.
- Install (`install`), configure (`configure`), and a live smoke are separate
  activities. This repository and its installer never change the parent
  top-level provider, model, or ChatGPT login.

## Architecture / Data Flow

```
Parent Codex (selected GPT + ChatGPT login)
        |
        | stage complete assignment through stdin
        v
one-shot plaintext SubagentStart Hook
        |
        | additional developer context + native spawn
        | fork_turns=none, reasoning_effort=max
        v
zai_glm53_worker (model glm-5.3)
        |
        | Codex Responses (wire_api=responses)
        v
https://open.bigmodel.cn/api/v1
```

The data plane remains a single native and direct transport path. The Hook is a
control-plane compatibility layer for provider-internal ciphertext; it is not a
model bridge and does not change the Z.AI request path. No runtime fallback
exists in the child: no fallback provider, model, or credential switch can occur
there.

The Luna path is parent orchestration, not part of the diagrammed Z.AI data
plane and not a runtime fallback. Hook trust, staging, authentication,
permission, data-boundary, model/account compatibility, assignment,
missing-callback, and
`ESCALATE_TO_GPT` failures stay visible instead of selecting Luna.

Official source:
https://docs.bigmodel.cn/cn/coding-plan/tool/codex (and its markdown endpoint).

## Requirements

- A Codex installation that supports spawning a standalone registered worker
  with a native Responses transport.
- Python 3.11 or newer for the installer
  (`python3 scripts/install.py install`).
- npm is required only when explicitly installing the Codex 0.149 compatibility
  runtime described below.
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

The installer registers the standalone child, helper tooling, the plaintext
handoff script, and one exact `^zai_glm53_worker$` `SubagentStart` matcher in
`~/.codex/hooks.json`. It preserves unrelated Hook entries and never forges the
Hook trust decision. It never edits `~/.codex/config.toml` or `auth.json`; the
parent top-level provider and login remain untouched. No API key is written into
the repository, chat, issues, command arguments, or screenshots.

## Codex 0.149 Compatibility

Codex 0.149.0 changed child-role handling so a registered role can override its
model but inherits the parent provider. Consequently, an OpenAI parent sends
`glm-5.3` to the ChatGPT backend and receives a model/account compatibility
error before Z.AI is contacted. `SubagentStart` Hook output can append context
only, so the Hook cannot repair provider selection.

Upstream evidence: [Codex 0.149 role override implementation](https://github.com/openai/codex/blob/rust-v0.149.0/codex-rs/core/src/agent/role.rs),
[SubagentStart output schema](https://github.com/openai/codex/blob/rust-v0.149.0/codex-rs/hooks/schema/generated/subagent-start.command.output.schema.json),
and [custom-provider subagent issue #17598](https://github.com/openai/codex/issues/17598).

On macOS, this repository provides an explicit compatibility mode that installs
the unmodified official `@openai/codex@0.148.0-alpha.9` package under
`~/.codex/zai-glm53-subagent/codex-runtime/`. This is the last version verified
with the repository's cross-provider native child contract. Package lifecycle
scripts are disabled during installation.

After the normal repository install, install and activate the compatibility
runtime:

```
~/.codex/zai-glm53-subagent/bin/codex-glm53-runtime install --activate
```

Activation sets the macOS user-session `CODEX_CLI_PATH` override that Codex
Desktop natively supports. It does not patch OpenAI Codex Core, replace anything
inside `/Applications`, edit `config.toml` or `auth.json`, change the parent
provider/login, or introduce a second concurrently orchestrated Codex CLI.
Restart Codex Desktop after activation; the selected compatible executable
becomes the app's primary local app-server.

Inspect or deactivate the override with:

```
~/.codex/zai-glm53-subagent/bin/codex-glm53-runtime status
~/.codex/zai-glm53-subagent/bin/codex-glm53-runtime deactivate
```

Activation refuses to replace an unrelated existing `CODEX_CLI_PATH`, and
deactivation refuses to unset an override it does not own. Restart Codex Desktop
again after deactivation. When upstream restores supported per-child provider
selection, deactivate this compatibility mode and use the current bundled
runtime.

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

- After install, open `/hooks`, verify the matcher is exactly
  `^zai_glm53_worker$`, verify its command points to
  `codex-zai-glm53-subagent/plaintext_handoff.py --mode hook`, trust it, and
  start a new Codex task so the updated agent, skill, and Hook policy reload.
- The `$use-zai-glm53-worker` skill requires `fork_turns=none` and
  `reasoning_effort=max`. It stages one complete assignment through stdin before
  calling the native spawn route; a failed stage must never be followed by a
  spawn.
- Assignments are self-contained and include an explicit writable scope and
  validation commands. The child spawn message only identifies the trusted
  one-shot Hook; the Hook injects the actual assignment.
- The skill and worker warn about the Z.AI data boundary.
- An explicit user instruction, or applicable user/project `AGENTS.md`, may
  grant standing authorization for bounded private source handoff within its
  stated scope. Do not ask again for each eligible assignment. Secrets,
  credentials, personal/regulated data, and out-of-scope source remain excluded.
- There is no runtime fallback in the GLM child. After an explicit
  quota/token/rate-limit exhaustion signal, the GPT parent may temporarily
  reissue the same bounded job to the Luna worker parameters listed above.
  Other failures and `ESCALATE_TO_GPT` return to GPT without rerouting.
- A later ordinary eligible job may try GLM again; a successful GLM start
  restores GLM-first routing. Use no paid recovery probe just to test capacity.
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

If compatibility mode is active, deactivate it and restart Codex Desktop before
running the normal uninstall:

```
~/.codex/zai-glm53-subagent/bin/codex-glm53-runtime deactivate
```

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
- No runtime fallback means the GLM child never silently switches provider or
  credentials; the narrow, explicit parent orchestration reroute is auditable.
- See SECURITY.md for reporting guidance.

## License

Apache-2.0. See LICENSE.
