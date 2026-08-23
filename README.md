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

Write-capable use needs one separate, explicit startup-catalog activation:

```text
~/.codex/zai-glm53-subagent/bin/codex-glm53-startup-catalog activate
~/.codex/zai-glm53-subagent/bin/codex-glm53-startup-catalog status
```

The activation command is intentionally not part of `install`. It reads the
current `models_cache.json`, builds a combined startup catalog that preserves
the parent's current model metadata, injects `glm-5.3` as a hidden model, and
adds only a managed top-level `model_catalog_json` block to `config.toml`. It
stores an exact mode-`0600` pre-activation config backup and does not read or
modify `auth.json`, the parent provider, selected model, or ChatGPT login.
Restart Codex Desktop after activation; the catalog is startup only.

## Codex Runtime Compatibility

The official [Codex subagents documentation](https://developers.openai.com/codex/multi-agent/)
says personal custom agents belong under `~/.codex/agents/` and are loaded as
configuration layers for spawned sessions. The official
[configuration reference](https://developers.openai.com/codex/config-reference/)
classifies `model_provider` and `model_providers` as machine-local provider
settings that must live at user level rather than in project-scoped config.
This repository therefore keeps the worker role in the documented personal
agent location and does not modify OpenAI Codex Core.

Compatibility is determined by an actual staged Hook plus native child
callback, not by the Codex version string alone. A historical Codex `0.149.0`
run applied the child model while inheriting the OpenAI parent's provider and
failed with a visible model/account compatibility error before Z.AI was
contacted. In contrast, after the sandbox-safe handoff-state fix, the current
bundled `codex-cli 0.148.0-alpha.21` completed the native callback exactly:

```text
ZAI_GLM53_NATIVE_OK
arithmetic=323
```

Write capability has a separate Guardian gate. Codex otherwise selects its
internal `codex-auto-review` model for automatic approval review, which a
custom Z.AI provider cannot serve and may report as `modelCode` not found.
Codex applies `model_catalog_json` while constructing its shared model manager
at startup only; the same setting in an agent role is accepted as a per-thread
override but is a no-op. The explicit activation above is therefore required:
its combined catalog gives `glm-5.3` the
`auto_review_model_override="glm-5.3"` metadata while retaining the parent's
current models and `codex-auto-review`. GLM stays hidden from the parent picker,
and both the coding turn and Guardian review use the explicit `zai_glm53`
provider/model only when that worker is spawned.

Because a configured startup catalog is static, rerun `activate` after a Codex
upgrade or model-cache refresh, then restart Codex Desktop. Activation fails
closed if the selected parent model or `codex-auto-review` is absent, or if an
unmanaged global `model_catalog_json` already exists. A native read callback is
not sufficient evidence for implementation work: each Codex
runtime/configuration combination must also pass an explicitly authorized
temporary write smoke before write capability is reported as ready.

An earlier repository release worked around that gap by installing the official
`@openai/codex@0.148.0-alpha.9` package and selecting it with
`CODEX_CLI_PATH`. The official
[environment-variable reference](https://developers.openai.com/codex/environment-variables/)
lists stable public variables and does not list `CODEX_CLI_PATH`; it is not a
stable public environment variable. Native verification also showed that this
older executable is protocol-incompatible with the current Codex Desktop
code-mode host. The workaround is retired: `install` and `activate` now fail
closed without downloading a runtime or setting a Desktop override.

If the legacy override was activated by an earlier version, inspect and remove
only that exact managed override with:

```
~/.codex/zai-glm53-subagent/bin/codex-glm53-runtime status
~/.codex/zai-glm53-subagent/bin/codex-glm53-runtime deactivate
```

Deactivation refuses to unset an unrelated `CODEX_CLI_PATH`. Restart Codex
Desktop after deactivation so it returns to the bundled app-server. If an
actual child rollout reports provider `openai` and a model/account compatibility
error, keep that runtime-specific failure visible: do not spawn again, do not
select Luna, and do not replace the Desktop runtime. Retry only after a material
runtime or configuration change and a newly authorized deterministic smoke.

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
- Stage and Hook resolve the same per-user state root under the process
  temporary directory, avoiding routine writes to `~/.codex` from a
  workspace-only sandbox. The state directory is mode `0700`; assignment
  envelopes and lock files are mode `0600`, and symlinked or foreign-owned
  roots fail closed.
- If staging nevertheless reports `Operation not permitted`, the parent may
  request one sandbox approval for the same stdin assignment and retry once.
  This approval covers staging only; spawn remains forbidden until staging
  succeeds and it never authorizes a provider, model, credential, transport, or
  fallback change.
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
- A write smoke uses a disposable writable directory, requires `apply_patch` to
  produce the expected file contents, and requires a completed Guardian
  assessment. `modelCode` not found is classified as
  `guardian_model_unavailable`, a non-capacity failure: do not retry the same
  write, do not select Luna, and do not claim write readiness.

## Local Tests

Local validation (no paid API contact):

```
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 -m compileall -q src tests
```

Behavior changes are written tests-first.

## Uninstall

Deactivate the startup catalog and restart Codex Desktop before uninstalling:

```text
~/.codex/zai-glm53-subagent/bin/codex-glm53-startup-catalog deactivate
```

This removes only the exact managed block and preserves unrelated changes made
to `config.toml` after activation. If the retired legacy override is also
active, deactivate it before running the normal uninstall:

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

Documentation and tests distinguish four levels:

- `locally_verified`: repository tests and an isolated temp-home install smoke
  passed without a paid API.
- `configured`: the worker and helper are installed into a real Codex home and
  credentials have been supplied.
- `read_ready`: verified by an explicitly authorized real GLM child callback
  that performs no mutation.
- `write_ready`: verified by an explicitly authorized real GLM `apply_patch`
  smoke whose Guardian assessment completed and whose file result was checked.

Current status is `read_ready` on the verified local macOS installation. Write
status is `unverified`; no successful Guardian-gated write smoke has been
recorded yet. On
2026-08-22, the bundled `codex-cli 0.148.0-alpha.21` returned this exact native
child callback after the assignment was staged through the installed Hook:

```text
ZAI_GLM53_NATIVE_OK
arithmetic=323
```

This result is environment-specific. Other Codex builds must repeat the native
read smoke before being reported as `read_ready`, and every build/configuration
pair must separately pass the write smoke before being reported as
`write_ready`.

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
