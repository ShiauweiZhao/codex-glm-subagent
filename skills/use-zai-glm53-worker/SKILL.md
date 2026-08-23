---
name: use-zai-glm53-worker
description: Use the direct Z.AI GLM-5.3 worker through the installed one-shot plaintext SubagentStart Hook for bounded implementation and extraction.
---

Use when the parent needs a bounded coding assignment executed directly against
the Z.AI GLM-5.3 model. The data plane remains native Codex Responses to Z.AI.
The control plane always uses the trusted one-shot plaintext `SubagentStart`
Hook because a cross-provider collaboration payload is not a reliable assignment
carrier. No bridge, MCP, second Codex CLI, provider fallback, commit/push/PR, or
internal agent runtime is used.

The GPT parent keeps requirements, planning, design, architecture, task
decomposition, review, final verification, integration decisions, Git, and
approvals. Eligible bounded implementation, bug fixing, refactoring, tests,
code-related documentation, and deterministic extraction default to GLM-5.3.

## Mode
- `fork_turns="none"`
- `reasoning_effort="max"`

## Assignment contract
Every assignment must include:
- objective
- explicit writable scope
- validation commands
- exclusions
- evidence
- permission caveat
- stop condition

## Deliver one self-contained job

1. Build the complete assignment before spawning. For coding, it must include
   the explicit writable scope and validation commands.
2. Stage the assignment through stdin to the installed script:

   ```text
   python3 "$CODEX_HOME/hooks/codex-zai-glm53-subagent/plaintext_handoff.py" --mode stage
   ```

   The required script action is `plaintext_handoff.py --mode stage`; the
   assignment itself is stdin, never a command argument.

   If `CODEX_HOME` is unset, use `~/.codex`. The script and Hook derive the same
   per-user handoff directory from the process temporary directory. The
   plaintext assignment briefly exists there and then crosses the Z.AI data
   boundary. Do not put it or credentials in command arguments.

   If staging still fails with `Operation not permitted`, never spawn from that
   failure. The parent may request exactly one sandbox approval for the same
   complete assignment, retry the same staging command once, and keep the
   assignment itself as stdin. It must not spawn until that retry succeeds. A
   staging approval does not authorize a provider, model, credential, transport,
   or fallback change. If the retry fails, stop and report the exact error.
   Never spawn after a failed stage.
3. Immediately spawn exact agent type `zai_glm53_worker` with a unique task name,
   `fork_turns="none"`, and `reasoning_effort="max"`. The spawn message should
   only identify the trusted one-shot Hook; the complete task comes from the
   staged handoff.
4. Receive the child through native callback/wait. Do not replace the flow with
   a bridge, MCP, another CLI, or direct API request. A materially changed job
   gets a new staged handoff and a new child; do not rely on cross-provider
   follow-up delivery.

## Runtime-specific provider failure

Do not block staging from a version string alone. The actual native child
callback or rollout error is the compatibility oracle.

If the child rollout reports provider `openai` and the ChatGPT backend rejects
`glm-5.3` as unsupported for the account, the running Codex app-server has
inherited the parent provider instead of applying the registered role's
provider. This is a model/account compatibility failure, not GLM capacity.
It must not spawn again, select Luna, or trigger a recovery probe.

Report the released-runtime support boundary. Do not install or activate a
different Desktop app-server. If an earlier repository version activated the
retired managed override, direct the user to remove it:

```text
~/.codex/zai-glm53-subagent/bin/codex-glm53-runtime deactivate
```

The user must restart Codex Desktop after deactivation. Retry only after a
material runtime or configuration change and a new explicitly authorized
deterministic smoke; never restore the retired Desktop override. This failure is
not a bridge, authentication, or capacity problem.

## Guardian model routing failure

Before staging any write assignment, run the installed
`codex-glm53-startup-catalog status` helper. It must report the startup catalog
as active, and the current Codex task must have started after the required
Restart Codex Desktop step. If either condition is not established, the parent
must not stage or spawn the write assignment.

The effective startup catalog must set
`auto_review_model_override="glm-5.3"`. An agent-role `model_catalog_json` is a
per-thread no-op and is not sufficient. Without the startup metadata Codex may
send its internal `codex-auto-review` identifier through the custom Z.AI
provider when reviewing an `apply_patch` request.

If automatic approval review fails with `modelCode` not found before producing
an assessment, classify it as `guardian_model_unavailable`. This is a
non-capacity runtime/configuration failure, not a Guardian policy denial. The
child must stop without retrying or changing the write route, and must not
select Luna. Retry only after the installed model catalog or Codex runtime has
materially changed and the user explicitly authorizes a deterministic write
smoke.

## Standing authorization

- Context and tool results cross the Z.AI boundary and require authorization.
- An explicit user instruction, or an applicable user/project `AGENTS.md`
  instruction, authorizing GLM for bounded private source work is standing
  authorization within that stated repository and task scope. Do not ask again
  for every eligible assignment in that scope.
- Standing authorization never includes secrets, credentials, personal data,
  regulated data, or source outside the authorized scope. Stop and return the
  decision to GPT when any of those would be required.

## Parent orchestration when GLM capacity is unavailable

Only an explicit GLM response identifying quota exhaustion, token allocation
exhaustion, or a rate-limit as the blocking condition permits the GPT parent to
reissue the same self-contained bounded assignment to a native worker with:

- `agent_type="worker"`
- `model="gpt-5.6-luna"`
- `reasoning_effort="max"`
- `fork_turns="none"`

This is a temporary parent orchestration reroute, not a runtime provider
fallback inside the GLM child or Z.AI data plane. Hook trust, failed staging,
authentication, permission or data-boundary failures, model/account compatibility
errors, a malformed assignment, a missing callback, and `ESCALATE_TO_GPT` must
stay visible and must not select Luna. A later ordinary eligible assignment may
try GLM again; after a successful GLM start, restore GLM-first routing. Use no
paid recovery probe merely to test whether capacity has returned.

## Boundaries
- Bounded coding and extraction only.
- No decisions, review, final verification, Git, external mutation, credentials,
  or approval requests.
- Return `ESCALATE_TO_GPT` for unresolved design, scope expansion, safety or
  consequential judgment, missing scope/oracle, or approval boundary.
- Context and tool results cross the Z.AI boundary: apply the standing
  authorization rules above and never include excluded sensitive data.
- No bridge is required: the Hook transports the assignment, while the child
  still sends native Responses requests directly to Z.AI.
- Missing or untrusted Hook state, a failed stage, authentication failure,
  absent callback, or any non-capacity provider error is a visible failure.
  Never switch the child provider or transport at runtime.
