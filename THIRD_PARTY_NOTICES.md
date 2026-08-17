# Third-Party Notices

This project is distributed under the Apache License, Version 2.0 (see LICENSE).

## Attribute attribution

The installer, macOS Keychain credential helper, and the standalone-worker role
pattern are derived from the Apache-2.0 licensed repository
`ShiauweiZhao/codex-opencode-go-subagent`. That source is the origin of the
installer/Keychain/role structure used here.

No OpenCode Go bridge code, localhost bridge, or Chat-Completions conversion is
included in this repository. The transport used here is native Codex Responses
direction to Z.AI (`https://open.bigmodel.cn/api/v1`, `wire_api=responses`).

## Official documentation

Z.AI's official Codex integration documentation is referenced (not copied as
code):

- https://docs.bigmodel.cn/cn/coding-plan/tool/codex

## Dependencies

- Python 3.11+ standard library only for the installer and tests. No third-party
  runtime packages are required.
- macOS uses the system Keychain through Apple's Security.framework (via Python
  ctypes) for credential storage; no keychain/security CLI tool is required.

## License attribution

Contributions to this repository are licensed under the Apache License,
Version 2.0. Notices above are provided for attribution and provenance
transparency only.
