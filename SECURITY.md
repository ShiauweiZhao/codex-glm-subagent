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

## Key rotation

If a key is ever exposed, treat it as compromised, rotate it at
`https://open.bigmodel.cn`, and remove the stored value:

- macOS: `~/.codex/zai-glm53-subagent/bin/codex-zai-glm53-credentials purge`
- Linux: unset `ZAI_API_KEY` in the affected shell / environment.

## Blast radius

This repository contains documentation and a bounded installer for a standalone
child worker. It does not include credentials, tokens, or secrets, and does not
introduce a runtime provider/model fallback.
