import json
import os
import shutil
import stat
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, os.path.join(str(REPO), "src"))

from codex_glm53_subagent import installer  # noqa: E402


AGENT_TOML = '''\
name = "zai_glm53_worker"
description = "test worker"
developer_instructions = "bounded worker"
model_provider = "zai_glm53"
model = "glm-5.3"
model_context_window = 1048576
model_catalog_json = "__CODEX_GLM53_MODEL_CATALOG__"

[model_providers.zai_glm53]
name = "Z.AI GLM-5.3 Responses"
base_url = "https://open.bigmodel.cn/api/v1"
wire_api = "responses"
request_max_retries = 1
stream_max_retries = 1
stream_idle_timeout_ms = 300000
placeholder = "__CODEX_GLM53_AUTH_BODY__"
'''

MODELS_JSON = '{"models": [{"slug": "glm-5.3", "display_name": "glm-5.3"}]}'
SKILL_MD = "# use-zai-glm53-worker\n\nBounded worker skill.\n"
OPENAI_YAML = (
    "interface:\n"
    "  display_name: Use Z.AI GLM-5.3 Worker\n"
    "  short_description: Bounded implementation worker.\n"
)
PKG_INIT = '"""codex-glm-subagent package."""\nfrom .credentials import main\n'
CREDENTIALS_PY = (
    '"""credentials module for tests."""\n'
    'KEYCHAIN_SERVICE = "com.shiauweizhao.codex-glm-subagent"\n'
    'API_KEY_ACCOUNT = "zai-api-key"\n'
    'def main(argv=None):\n    return 0\n'
)
WRAPPER = (
    "#!/bin/sh\n"
    'export PYTHONPATH="__CODEX_GLM53_RUNTIME_ROOT__${PYTHONPATH:+:$PYTHONPATH}"\n'
    'exec "__PYTHON_EXECUTABLE__" -m codex_glm53_subagent.credentials "$@"\n'
)
SNIPPET = (
    "<!-- codex-glm53-subagent:start -->\n"
    "Managed GLM-5.3 standalone worker block.\n"
    "<!-- codex-glm53-subagent:end -->\n"
)


def make_repo(root: Path) -> Path:
    root = Path(root)
    agents = root / "agents"
    agents.mkdir(parents=True)
    (agents / "zai-glm53-worker.toml").write_text(AGENT_TOML, encoding="utf-8")
    (agents / "glm-5.3-models.json").write_text(MODELS_JSON, encoding="utf-8")

    skill = root / "skills" / "use-zai-glm53-worker"
    (skill / "agents").mkdir(parents=True)
    (skill / "SKILL.md").write_text(SKILL_MD, encoding="utf-8")
    (skill / "agents" / "openai.yaml").write_text(OPENAI_YAML, encoding="utf-8")

    pkg = root / "src" / "codex_glm53_subagent"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text(PKG_INIT, encoding="utf-8")
    (pkg / "credentials.py").write_text(CREDENTIALS_PY, encoding="utf-8")

    scripts = root / "scripts"
    scripts.mkdir()
    wrapper = scripts / "codex-zai-glm53-credentials"
    wrapper.write_text(WRAPPER, encoding="utf-8")
    os.chmod(wrapper, 0o700)

    snippets = root / "snippets"
    snippets.mkdir()
    (snippets / "AGENTS.md").write_text(SNIPPET, encoding="utf-8")
    return root


class InstallerTestBase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="glm53-installer-test-"))
        self.repo = make_repo(self.tmp / "repo")
        self.codex = self.tmp / "codex"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def install(self, platform="darwin"):
        return installer.install(self.repo, self.codex, platform=platform)


class RenderTest(InstallerTestBase):
    def test_mac_render_subtable(self):
        self.install("darwin")
        agent_path = self.codex / "agents" / "zai-glm53-worker.toml"
        data = tomllib.loads(agent_path.read_text(encoding="utf-8"))
        prov = data["model_providers"]["zai_glm53"]
        self.assertIsInstance(prov["auth"], dict)
        helper = self.codex / "zai-glm53-subagent" / "bin" / "codex-zai-glm53-credentials"
        self.assertEqual(prov["auth"]["command"], str(helper))
        self.assertEqual(prov["auth"]["args"], ["print-api-key"])
        self.assertEqual(prov["auth"]["timeout_ms"], 5000)
        self.assertEqual(prov["auth"]["refresh_interval_ms"], 300000)
        catalog = self.codex / "zai-glm53-subagent" / "glm-5.3-models.json"
        self.assertEqual(data["model_catalog_json"], str(catalog))
        self.assertEqual(agent_path.read_text(encoding="utf-8").count(
            "[model_providers.zai_glm53.auth]"), 1)

    def test_linux_render_env_key(self):
        self.install("linux")
        agent_path = self.codex / "agents" / "zai-glm53-worker.toml"
        text = agent_path.read_text(encoding="utf-8")
        data = tomllib.loads(text)
        prov = data["model_providers"]["zai_glm53"]
        self.assertEqual(prov["env_key"], "ZAI_API_KEY")
        self.assertNotIn("auth", prov)
        self.assertNotIn("[model_providers.zai_glm53.auth]", text)
        self.assertNotIn("print-api-key", text)

    def test_catalog_and_skill_installed(self):
        self.install("darwin")
        catalog = self.codex / "zai-glm53-subagent" / "glm-5.3-models.json"
        self.assertEqual(json.loads(catalog.read_text()), json.loads(MODELS_JSON))
        self.assertTrue((self.codex / "skills" / "use-zai-glm53-worker" / "SKILL.md").is_file())
        self.assertTrue(
            (self.codex / "skills" / "use-zai-glm53-worker" / "agents" / "openai.yaml").is_file()
        )

    def test_wrapper_renders_abs_python_and_runtime(self):
        self.install("darwin")
        wrapper = (self.codex / "zai-glm53-subagent" / "bin" / "codex-zai-glm53-credentials")
        text = wrapper.read_text(encoding="utf-8")
        self.assertIn(sys.executable, text)
        self.assertIn(str(self.codex / "zai-glm53-subagent" / "runtime"), text)
        self.assertIn("-m codex_glm53_subagent.credentials", text)
        self.assertNotIn("__PYTHON_EXECUTABLE__", text)
        self.assertNotIn("__CODEX_GLM53_RUNTIME_ROOT__", text)


class InstallBehaviorTest(InstallerTestBase):
    def test_idempotent(self):
        first = self.install("darwin")
        second = self.install("darwin")
        self.assertEqual(first["status"], "installed")
        self.assertEqual(second["status"], "already_installed")
        self.assertEqual(
            (self.codex / "agents" / "zai-glm53-worker.toml").read_bytes(),
            (self.codex / "agents" / "zai-glm53-worker.toml").read_bytes(),
        )

    def test_unmanaged_refusal_before_any_write(self):
        dest = self.codex / "zai-glm53-subagent" / "glm-5.3-models.json"
        dest.parent.mkdir(parents=True)
        dest.write_text("UNMANAGED CONTENT", encoding="utf-8")
        with self.assertRaises(RuntimeError):
            self.install("darwin")
        # Earlier-managed agent toml must NOT have been written.
        self.assertFalse((self.codex / "agents" / "zai-glm53-worker.toml").exists())
        self.assertFalse((self.codex / "zai-glm53-subagent" / "install-manifest.json").exists())
        self.assertFalse((self.codex / "hooks.json").exists())

    def test_config_auth_sentinels_unchanged(self):
        self.codex.mkdir()
        (self.codex / "config.toml").write_text("SENTINEL_CONFIG", encoding="utf-8")
        (self.codex / "auth.json").write_text("SENTINEL_AUTH", encoding="utf-8")
        self.install("darwin")
        self.assertEqual((self.codex / "config.toml").read_text(), "SENTINEL_CONFIG")
        self.assertEqual((self.codex / "auth.json").read_text(), "SENTINEL_AUTH")

    def test_no_hooks_inline_token_or_fallback(self):
        self.install("darwin")
        self.assertFalse((self.codex / "hooks.json").exists())
        text = (self.codex / "agents" / "zai-glm53-worker.toml").read_text(encoding="utf-8")
        self.assertNotIn("experimental_bearer_token", text)
        self.assertNotIn("fallback", text.lower())
        data = tomllib.loads(text)
        self.assertEqual(list(data["model_providers"].keys()), ["zai_glm53"])

    def test_executable_modes(self):
        self.install("darwin")
        helper = self.codex / "zai-glm53-subagent" / "bin" / "codex-zai-glm53-credentials"
        self.assertEqual(stat.S_IMODE(os.stat(helper).st_mode), 0o700)
        agent = self.codex / "agents" / "zai-glm53-worker.toml"
        self.assertEqual(stat.S_IMODE(os.stat(agent).st_mode), 0o600)
        manifest = self.codex / "zai-glm53-subagent" / "install-manifest.json"
        self.assertEqual(stat.S_IMODE(os.stat(manifest).st_mode), 0o600)
        skill = self.codex / "skills" / "use-zai-glm53-worker" / "SKILL.md"
        self.assertEqual(stat.S_IMODE(os.stat(skill).st_mode), 0o600)


class AgentsBlockTest(InstallerTestBase):
    def test_block_merge_and_removal_preserves_other_text(self):
        self.codex.mkdir()
        (self.codex / "AGENTS.md").write_text(
            "# Header\n"
            "keep me\n"
            "<!-- codex-glm53-subagent:start -->\n"
            "OLD BLOCK\n"
            "<!-- codex-glm53-subagent:end -->\n"
            "footer text\n",
            encoding="utf-8",
        )
        self.install("darwin")
        merged = (self.codex / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("# Header", merged)
        self.assertIn("keep me", merged)
        self.assertIn("footer text", merged)
        self.assertIn("Managed GLM-5.3 standalone worker block.", merged)
        self.assertNotIn("OLD BLOCK", merged)

        installer.uninstall(self.codex, platform="darwin")
        after = (self.codex / "AGENTS.md").read_text(encoding="utf-8")
        self.assertNotIn("<!-- codex-glm53-subagent:start -->", after)
        self.assertNotIn("<!-- codex-glm53-subagent:end -->", after)
        self.assertIn("# Header", after)
        self.assertIn("keep me", after)
        self.assertIn("footer text", after)


class UninstallTest(InstallerTestBase):
    def test_uninstall_preserves_modified_file(self):
        self.install("darwin")
        mod = self.codex / "zai-glm53-subagent" / "glm-5.3-models.json"
        mod.write_text("MODIFIED", encoding="utf-8")
        report = installer.uninstall(self.codex, platform="darwin")
        self.assertTrue(mod.exists())
        self.assertEqual(mod.read_text(), "MODIFIED")
        self.assertIn("zai-glm53-subagent/glm-5.3-models.json", report["preserved_modified"])
        self.assertFalse((self.codex / "agents" / "zai-glm53-worker.toml").exists())
        self.assertFalse((self.codex / "zai-glm53-subagent" / "install-manifest.json").exists())

    def test_uninstall_prunes_only_empty_owned_dirs(self):
        self.install("darwin")
        kept = self.codex / "agents" / "other-agent.toml"
        kept.write_text("OTHER", encoding="utf-8")
        installer.uninstall(self.codex, platform="darwin")
        self.assertTrue(kept.exists())
        self.assertFalse((self.codex / "zai-glm53-subagent").exists())
        # agents dir is non-empty (other-agent.toml) so it must survive.
        self.assertTrue((self.codex / "agents").exists())


class PurgeBoundaryTest(InstallerTestBase):
    def test_purge_opt_in_boundary(self):
        self.install("darwin")
        calls = []

        def fake_purge(codex_home):
            calls.append(codex_home)

        installer.uninstall(self.codex, platform="darwin", purge_secrets=False, purge_fn=fake_purge)
        self.assertEqual(calls, [])

        self.install("darwin")
        installer.uninstall(self.codex, platform="darwin", purge_secrets=True, purge_fn=fake_purge)
        self.assertEqual(len(calls), 1)

        self.install("darwin")
        installer.uninstall(self.codex, platform="linux", purge_secrets=True, purge_fn=fake_purge)
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
