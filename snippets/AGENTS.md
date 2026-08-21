<!-- codex-glm-subagent:start -->
Classified bounded implementation/extraction tasks with an explicit writable
scope and validation default to `zai_glm53_worker`. The GPT parent keeps
requirements, planning, design/architecture, task decomposition, review, final
verification, integration decisions, approvals, and all Git operations.
Cross-provider assignment delivery always uses the installed one-shot plaintext
`SubagentStart` Hook; before spawning, use `$use-zai-glm53-worker` to stage the
complete assignment. The Z.AI data plane remains native Responses with no bridge.
An explicit user or applicable user/project `AGENTS.md` authorization for
bounded private source handoff is standing authorization in its stated scope;
do not repeat the question for every assignment. It never covers secrets,
personal/regulated data, or out-of-scope source.
Only explicit GLM quota/token/rate-limit exhaustion permits a temporary parent
orchestration reroute to `agent_type="worker"`, `model="gpt-5.6-luna"`,
`reasoning_effort="max"`, `fork_turns="none"`. This is not a child runtime
fallback. Hook, authentication, permission, data-boundary, model/account
compatibility, assignment, callback, and `ESCALATE_TO_GPT` failures remain
visible. Retry GLM on a later ordinary job; use no paid recovery probe.
<!-- codex-glm-subagent:end -->
