import pathlib
import re
import unittest


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


def read(relpath):
    path = REPO_ROOT / relpath
    if not path.exists():
        raise FileNotFoundError(f"missing expected file: {relpath}")
    return path.read_text(encoding="utf-8")


class DocsContractTests(unittest.TestCase):
    """Mechanical assertions over the public repository documentation."""

    REQUIRED_FILES = [
        "README.md",
        "LICENSE",
        "SECURITY.md",
        "THIRD_PARTY_NOTICES.md",
        "docs/architecture-decision.md",
        "docs/plans/2026-08-17-glm53-subagent-design.md",
        "AGENTS.md",
    ]

    README_HEADINGS = [
        "Outcome",
        "Boundaries",
        "Architecture / Data Flow",
        "Requirements",
        "Install",
        "macOS Configure",
        "Linux Configure",
        "Use / Delegation",
        "Local Tests",
        "Uninstall",
        "Verification Levels",
        "Security",
        "License",
    ]

    def test_required_docs_exist(self):
        for relpath in self.REQUIRED_FILES:
            self.assertTrue(
                (REPO_ROOT / relpath).exists(), f"missing file: {relpath}"
            )

    def test_license_is_apache_2(self):
        license_text = read("LICENSE")
        self.assertIn("Apache License", license_text)
        self.assertIn("Version 2.0", license_text)

    def test_readme_section_headings(self):
        readme = read("README.md")
        for heading in self.README_HEADINGS:
            self.assertIn(f"## {heading}", readme, f"missing README heading: {heading}")

    def test_readme_outcome_first_and_parent_provider_unchanged(self):
        readme = read("README.md")
        # Parent top-level provider/login must remain untouched.
        self.assertIn("ShiauweiZhao/codex-glm-subagent", readme)
        self.assertIn("glm-5.3", readme)
        self.assertIn("zai_glm53_worker", readme)

    def test_readme_install_configure_smoke_separate(self):
        readme = read("README.md")
        self.assertIn("scripts/install.py install", readme)
        # Docs must not imply install == configured == live.
        self.assertIn("configured", readme)
        self.assertIn("locally_verified", readme)
        self.assertIn("ready", readme)

    def test_readme_transport_facts(self):
        readme = read("README.md")
        self.assertIn("https://open.bigmodel.cn/api/v1", readme)
        self.assertIn("wire_api=responses", readme)
        self.assertIn("open.bigmodel.cn", readme)

    def test_readme_python_311(self):
        readme = read("README.md")
        self.assertIn("3.11", readme)

    def test_readme_macos_security_framework(self):
        readme = read("README.md")
        self.assertIn("Security.framework", readme)
        # Must not claim the keychain/security CLI must be available or is shelled out to.
        self.assertNotRegex(readme, r"`keychain`\s+must be available")
        self.assertNotRegex(readme, r"through\s+`security`")

    def test_readme_current_status_locally_verified_only(self):
        readme = read("README.md")
        # Current status must be locally_verified only -- explicitly not configured/ready.
        self.assertRegex(readme, r"Current status is `?locally_verified")
        self.assertNotRegex(readme, r"Current status is `?configured")
        self.assertNotRegex(readme, r"Current status is `?ready")

    def test_readme_no_localhost_bridge_or_fallback(self):
        readme = read("README.md")
        self.assertNotIn("localhost", readme.lower())
        self.assertIn("no fallback", readme.lower())

    def test_readme_requires_hook_independently_of_bridge(self):
        readme = read("README.md")
        self.assertIn("SubagentStart", readme)
        self.assertIn("plaintext", readme.lower())
        self.assertIn("Hook is required independently of bridge", readme)
        self.assertIn("/hooks", readme)
        self.assertIn("^zai_glm53_worker$", readme)

    def test_readme_installer_never_touches_config_or_auth(self):
        readme = read("README.md")
        self.assertIn("config.toml", readme)
        self.assertIn("auth.json", readme)
        self.assertIn("Login Keychain", readme)
        self.assertIn("ZAI_API_KEY", readme)

    def test_architecture_decision(self):
        doc = read("docs/architecture-decision.md")
        self.assertIn("wire_api=responses", doc)
        self.assertIn("open.bigmodel.cn", doc)
        self.assertIn("glm-5.3", doc)
        self.assertIn("no fallback", doc.lower())
        self.assertIn("Hook is required independently of bridge", doc)
        self.assertIn("provider-internal ciphertext", doc)

    def test_agents_managed_block_intact(self):
        agents = read("AGENTS.md")
        self.assertIn("<!-- codex-glm-subagent:start -->", agents)
        self.assertIn("<!-- codex-glm-subagent:end -->", agents)
        self.assertIn("zai_glm53_worker", agents)

    def test_agents_repo_instructions(self):
        agents = read("AGENTS.md")
        lowered = agents.lower()
        self.assertIn("no api keys", lowered)
        self.assertIn("no fallback", lowered)
        self.assertIn("tests first", lowered)
        self.assertIn("git", lowered)

    def test_security_policy(self):
        sec = read("SECURITY.md")
        self.assertIn("report", sec.lower())
        self.assertIn("key", sec.lower())

    def test_third_party_notices(self):
        notices = read("THIRD_PARTY_NOTICES.md")
        self.assertIn("Apache-2.0", notices)
        self.assertIn("codex-opencode-go-subagent", notices)
        self.assertIn("Utopia-V/codex-deepseek-subagent", notices)
        self.assertIn("Copyright (c) 2026 Utopia-V", notices)

    def test_third_party_notices_security_framework(self):
        notices = read("THIRD_PARTY_NOTICES.md")
        self.assertIn("Security.framework", notices)
        # Must not claim the security CLI is used for credential storage.
        self.assertNotRegex(notices, r"through\s+`security`")
        self.assertNotRegex(notices, r"`security`\s+for credential storage")

    def test_no_inline_token_example(self):
        """No real token must ever appear with a value, e.g.
        experimental_bearer_token = \"<secret>\". Only a bare key name
        or a clearly empty placeholder is allowed."""
        pattern = re.compile(
            r'experimental_bearer_token\s*=\s*["\'][\w.\-]{8,}["\']'
        )
        for relpath in self.REQUIRED_FILES:
            if not (REPO_ROOT / relpath).exists():
                continue
            text = read(relpath)
            self.assertFalse(
                pattern.search(text),
                f"inline token example with a value found in {relpath}",
            )

    def test_no_api_key_value_anywhere(self):
        key_pattern = re.compile(
            r'["\'](?:sk-|zai-)?[A-Za-z0-9]{32,}["\']'
        )
        for relpath in self.REQUIRED_FILES:
            if not (REPO_ROOT / relpath).exists():
                continue
            text = read(relpath)
            self.assertFalse(
                key_pattern.search(text),
                f"possible embedded secret value found in {relpath}",
            )


if __name__ == "__main__":
    unittest.main()
