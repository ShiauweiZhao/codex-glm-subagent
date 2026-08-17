---
name: use-zai-glm53-worker
description: Self-contained, direct native spawn of the Z.AI GLM-5.3 worker for bounded implementation and extraction only.
---

Use when the parent needs a bounded coding assignment executed directly against
the Z.AI GLM-5.3 model. Direct native GLM-5.3 worker use; no Hook, bridge, MCP,
second Codex CLI, provider fallback, commit/push/PR, or internal tooling.

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

## Boundaries
- Bounded coding and extraction only.
- No decisions, review, final verification, Git, external mutation, credentials,
  or approval requests.
- Return `ESCALATE_TO_GPT` for unresolved design, scope expansion, safety or
  consequential judgment, missing scope/oracle, or approval boundary.
- Context and tool results cross the Z.AI boundary: do not include secrets or
  private/regulated data without explicit authorization.
