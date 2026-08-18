# Security

## Reporting

If you find a security issue in `codex-glm-subagent` or its installer, report it
privately to the maintainers instead of opening a public issue. Include steps to
reproduce, affected versions, and the impact. Do not include any secret or API
key value in a report.

## Secret handling

- API keys are never placed in the repository, chat, issues, command arguments,
  or screenshots.
- macOS: the key is stored in the Login Keychain via the credential helper
  (`configure` / `status` / `purge`).
- Linux: the key is provided through the `ZAI_API_KEY` environment variable.
- The installer never edits `~/.codex/config.toml` or `auth.json`, and never
  changes the parent top-level provider or ChatGPT login.
- The complete child assignment briefly exists as plaintext in the current
  user's private handoff state and is then sent to Z.AI. The Hook is a transport
  compatibility layer, not a confidential channel; never stage credentials or
  material the user has not authorized to cross the Z.AI boundary.
- Hook state files and locks use user-only permissions. The exact
  `^zai_glm53_worker$` matcher consumes one staged assignment at most once;
  missing, malformed, expired, replayed, or quarantined state fails closed.

## Key rotation

If a key is ever exposed, treat it as compromised, rotate it at
`https://open.bigmodel.cn`, and remove the stored value:

- macOS: `~/.codex/zai-glm53-subagent/bin/codex-zai-glm53-credentials purge`
- Linux: unset `ZAI_API_KEY` in the affected shell / environment.

## Blast radius

This repository contains documentation and a bounded installer for a standalone
child worker. It does not include credentials, tokens, or secrets, and does not
introduce a bridge or runtime provider/model fallback. The installed plaintext
Hook adds a short-lived assignment state file under the current user's Codex
home; normal uninstall removes the managed Hook and matcher but preserves
unrelated user Hook entries.
