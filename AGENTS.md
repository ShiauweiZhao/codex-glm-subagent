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

## Repository instructions (GLM implementation worker)

下面的规则面向在本仓库内做有界实现的 GLM 子代理与协作方。

- 默认使用简体中文回复，直接、少铺垫。
- `zai_glm53_worker` 只做有界实现/提取：功能、缺陷修复、重构、测试、与代码相关的文档、
  以及明确接口后的跨模块接线。每个 assignment 都必须给出显式 writable scope 和
  validation 命令。
- 需求澄清、分析、审计、评估、设计与架构、接口/行为决策、任务分解、集成点、测试缺口、
  代码评审、最终验证、集成决策，以及 Git 操作，都保留在预选的 GPT 父代理上。子代理不
  commit、不 push、不建 PR、不做最终 review/验证、不处理凭据、不越权请求审批。
- 已由用户或适用的 user/project `AGENTS.md` 明确授权 GLM 处理有界私有源码时，将该授权
  视为其声明仓库/任务范围内的 standing authorization，不逐 assignment 重复询问；密钥、
  个人/受监管数据和范围外源码不在授权内，遇到时必须停下交回 GPT。
- 仅当 GLM 明确返回 quota/token/rate-limit 资源耗尽时，GPT 父代理可把同一份自包含有界
  任务临时重新下发给 `agent_type="worker"`、`model="gpt-5.6-luna"`、
  `reasoning_effort="max"`、`fork_turns="none"`。这是父代理编排切换，不是 GLM/Z.AI
  数据面 runtime fallback。Hook/认证/权限/数据边界/model-account compatibility/
  assignment/callback 错误以及 `ESCALATE_TO_GPT` 不得触发 Luna；后续普通任务成功使用
  GLM 后恢复 GLM 优先，不做额外 paid recovery probe。
- 数据面只有一条：Codex Responses → `https://open.bigmodel.cn/api/v1`，
  `wire_api=responses`，原生直连，`no fallback`（无本地桥、无 Chat 转换、无 SQLite、
  无 daemon、无 MCP、无第二个 CLI、无 provider/model 运行时回退）。控制面无论是否
  需要 bridge 都必须使用一次性 plaintext `SubagentStart` Hook 交付 assignment。
- spawn 或排障 `zai_glm53_worker` 前必须使用 `$use-zai-glm53-worker`，先 stage 成功，
  再以 `fork_turns="none"` 创建 child；stage 失败不得 spawn，不依赖 follow-up 传任务。
- 绝不读取、打印、持久化到仓库，或放入命令行参数的密钥值：macOS 的 Login Keychain、
  Linux 的 `ZAI_API_KEY`。`no API keys` 进仓库/聊天/issue/命令参数/截图。
- 行为变更先写测试（`tests first`），本地验证命令：
  `PYTHONPATH=src python3 -m unittest discover -s tests -v` 以及
  `python3 -m compileall -q src tests`；完成前要跑完整验证。
- 有界子代理遇到未决设计、需要扩权/扩 scope、安全性或后果性判断、缺失 scope 或
  validation oracle、越界审批/沙箱动作时，返回 `ESCALATE_TO_GPT`，由 GPT 父代理决定。
- `git` 及 GitHub 收口归 GPT 父代理，本仓库文档/测试不执行 Git 操作。
- 安装器（`python3 scripts/install.py install`）绝不能改 `~/.codex/config.toml`
  或 `auth.json`，也绝不切换顶层 provider/登录。未获用户明确授权，不做 paid/native
  live smoke。
