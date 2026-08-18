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

   If `CODEX_HOME` is unset, use `~/.codex`. The plaintext assignment briefly
   exists in the local user state and then crosses the Z.AI data boundary. Do
   not put it or credentials in command arguments. If the parent sandbox needs
   approval to write that state, the parent owns that approval decision.
   Never spawn after a failed stage.
3. Immediately spawn exact agent type `zai_glm53_worker` with a unique task name,
   `fork_turns="none"`, and `reasoning_effort="max"`. The spawn message should
   only identify the trusted one-shot Hook; the complete task comes from the
   staged handoff.
4. Receive the child through native callback/wait. Do not replace the flow with
   a bridge, MCP, another CLI, or direct API request. A materially changed job
   gets a new staged handoff and a new child; do not rely on cross-provider
   follow-up delivery.

## Boundaries
- Bounded coding and extraction only.
- No decisions, review, final verification, Git, external mutation, credentials,
  or approval requests.
- Return `ESCALATE_TO_GPT` for unresolved design, scope expansion, safety or
  consequential judgment, missing scope/oracle, or approval boundary.
- Context and tool results cross the Z.AI boundary: do not include secrets or
  private/regulated data without explicit authorization.
- No bridge is required: the Hook transports the assignment, while the child
  still sends native Responses requests directly to Z.AI.
- Missing or untrusted Hook state, a failed stage, absent callback, or provider
  error is a visible failure. Do not fall back to another model or transport.
