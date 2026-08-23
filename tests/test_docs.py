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
        "Codex Runtime Compatibility",
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

    def test_readme_current_status_distinguishes_read_and_write_readiness(self):
        readme = read("README.md")
        normalized = " ".join(readme.split())
        self.assertRegex(readme, r"Current status is `?read_ready")
        self.assertIn("Write status is `unverified`", normalized)
        self.assertIn("0.148.0-alpha.21", readme)
        self.assertIn("ZAI_GLM53_NATIVE_OK", readme)
        self.assertIn("arithmetic=323", readme)
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

    def test_readme_documents_sandbox_safe_handoff_state(self):
        readme = read("README.md")
        normalized = " ".join(readme.lower().split())
        self.assertIn("process temporary directory", normalized)
        self.assertIn("mode `0700`", normalized)
        self.assertIn("mode `0600`", normalized)
        self.assertIn("sandbox approval", normalized)
        self.assertIn("operation not permitted", normalized)

    def test_readme_installer_never_touches_config_or_auth(self):
        readme = read("README.md")
        self.assertIn("config.toml", readme)
        self.assertIn("auth.json", readme)
        self.assertIn("Login Keychain", readme)
        self.assertIn("ZAI_API_KEY", readme)

    def test_readme_documents_explicit_startup_catalog_activation(self):
        readme = read("README.md")
        normalized = " ".join(readme.lower().split())
        self.assertIn("codex-glm53-startup-catalog activate", readme)
        self.assertIn("codex-glm53-startup-catalog deactivate", readme)
        self.assertIn("models_cache.json", readme)
        self.assertIn("model_catalog_json", readme)
        self.assertIn("startup only", normalized)
        self.assertIn("per-thread", normalized)
        self.assertIn("no-op", normalized)
        self.assertIn("hidden", normalized)
        self.assertIn("restart codex desktop", normalized)
        self.assertIn("does not read or modify `auth.json`", normalized)

    def test_readme_retires_unsafe_desktop_runtime_override(self):
        readme = read("README.md")
        normalized = " ".join(readme.split())
        self.assertIn("0.148.0-alpha.9", readme)
        self.assertIn("CODEX_CLI_PATH", readme)
        self.assertIn("codex-glm53-runtime deactivate", readme)
        self.assertNotIn("codex-glm53-runtime install --activate", readme)
        self.assertIn("not a stable public environment variable", normalized)
        self.assertIn("protocol-incompatible", normalized)
        self.assertIn("restart", readme.lower())
        self.assertIn(
            "https://developers.openai.com/codex/multi-agent/", readme
        )
        self.assertIn(
            "https://developers.openai.com/codex/config-reference/", readme
        )
        self.assertIn(
            "https://developers.openai.com/codex/environment-variables/", readme
        )

    def test_architecture_decision(self):
        doc = read("docs/architecture-decision.md")
        self.assertIn("wire_api=responses", doc)
        self.assertIn("open.bigmodel.cn", doc)
        self.assertIn("glm-5.3", doc)
        self.assertIn("no fallback", doc.lower())
        self.assertIn("Hook is required independently of bridge", doc)
        self.assertIn("provider-internal ciphertext", doc)

    def test_guardian_model_routing_and_write_smoke_are_documented(self):
        for relpath in ("README.md", "docs/architecture-decision.md"):
            text = read(relpath)
            normalized = " ".join(text.lower().split())
            self.assertIn("auto_review_model_override", text, relpath)
            self.assertIn("guardian", normalized, relpath)
            self.assertIn("write smoke", normalized, relpath)
            self.assertIn("modelcode", normalized, relpath)

    def test_parent_orchestration_reroute_is_distinct_from_runtime_fallback(self):
        for relpath in (
            "README.md",
            "docs/architecture-decision.md",
            "docs/plans/2026-08-17-glm53-subagent-design.md",
        ):
            text = read(relpath)
            lowered = text.lower()
            self.assertIn("gpt-5.6-luna", text, relpath)
            self.assertIn("quota", lowered, relpath)
            self.assertIn("rate-limit", lowered, relpath)
            self.assertIn("parent orchestration", lowered, relpath)
            self.assertIn("no runtime fallback", lowered, relpath)
            self.assertIn("standing authorization", lowered, relpath)

    def test_managed_agents_block_routes_bounded_work(self):
        for relpath in ("AGENTS.md", "snippets/AGENTS.md"):
            text = read(relpath)
            normalized = " ".join(text.lower().split())
            self.assertIn("zai_glm53_worker", text, relpath)
            self.assertIn("gpt-5.6-luna", text, relpath)
            self.assertIn("standing authorization", normalized, relpath)
            self.assertIn("rate-limit", normalized, relpath)
            self.assertIn("model/account compatibility", normalized, relpath)

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
