# Third-Party Notices

This project is distributed under the Apache License, Version 2.0 (see LICENSE).

## Attribute attribution

The installer, macOS Keychain credential helper, and the standalone-worker role
pattern are derived from the Apache-2.0 licensed repository
`ShiauweiZhao/codex-opencode-go-subagent`. That source is the origin of the
installer/Keychain/role structure and the GLM-specific adaptation of the
plaintext handoff used here.

No OpenCode Go bridge code, localhost bridge, or Chat-Completions conversion is
included in this repository. The transport used here is native Codex Responses
direction to Z.AI (`https://open.bigmodel.cn/api/v1`, `wire_api=responses`).

## Utopia-V/codex-deepseek-subagent

`hooks/plaintext_handoff.py`, its protocol design, and the related one-shot
handoff tests are adapted through the OpenCode Go repository from:

- https://github.com/Utopia-V/codex-deepseek-subagent
- snapshot: `1377b7655ea98ed50a5131172b579b56ed744793`

MIT License

Copyright (c) 2026 Utopia-V

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## Official documentation

Z.AI's official Codex integration documentation is referenced (not copied as
code):

- https://docs.bigmodel.cn/cn/coding-plan/tool/codex

## Dependencies

- The base installer and tests use the Python 3.11+ standard library only. They
  require no third-party Python runtime package.
- The explicit Codex 0.149 compatibility action downloads the unmodified
  Apache-2.0-licensed official `@openai/codex@0.148.0-alpha.9` package from npm.
  It is optional, installed side-by-side under the user's Codex home, and is not
  redistributed in this repository.
- macOS uses the system Keychain through Apple's Security.framework (via Python
  ctypes) for credential storage; no keychain/security CLI tool is required.

## License attribution

Contributions to this repository are licensed under the Apache License,
Version 2.0. Notices above are provided for attribution and provenance
transparency only.
