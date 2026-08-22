import subprocess
import tempfile
import unittest
from pathlib import Path

from codex_glm53_subagent import compat_runtime


class FakeNpmRunner:
    def __init__(self):
        self.calls = []

    def __call__(self, args, **kwargs):
        self.calls.append((list(args), kwargs))
        if args[0] == "/test/bin/npm":
            prefix = Path(args[args.index("--prefix") + 1])
            binary = (
                prefix
                / "node_modules"
                / "@openai"
                / "codex-darwin-arm64"
                / "vendor"
                / "aarch64-apple-darwin"
                / "bin"
                / "codex"
            )
            binary.parent.mkdir(parents=True)
            binary.write_text("compatible codex", encoding="utf-8")
            binary.chmod(0o700)
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
        return subprocess.CompletedProcess(
            args,
            0,
            stdout=f"codex-cli {compat_runtime.COMPAT_CODEX_VERSION}\n",
            stderr="",
        )


class FakeLaunchctlRunner:
    def __init__(self, current=""):
        self.current = current
        self.calls = []

    def __call__(self, args, **kwargs):
        self.calls.append((list(args), kwargs))
        if len(args) == 2 and args[1] == "--version":
            return subprocess.CompletedProcess(
                args,
                0,
                stdout=f"codex-cli {compat_runtime.COMPAT_CODEX_VERSION}\n",
                stderr="",
            )
        action = args[1]
        if action == "getenv":
            return subprocess.CompletedProcess(args, 0, stdout=self.current, stderr="")
        if action == "setenv":
            self.current = args[3]
        elif action == "unsetenv":
            self.current = ""
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")


class CompatRuntimeInstallTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="glm53-compat-runtime-")
        self.codex_home = Path(self.tmp.name) / "codex"

    def tearDown(self):
        self.tmp.cleanup()

    def test_installs_pinned_official_runtime_without_package_scripts(self):
        runner = FakeNpmRunner()

        report = compat_runtime.install(
            self.codex_home,
            runner=runner,
            which=lambda command: "/test/bin/npm" if command == "npm" else None,
        )

        binary = Path(report["codex_cli_path"])
        self.assertTrue(binary.is_file())
        self.assertEqual(report["version"], compat_runtime.COMPAT_CODEX_VERSION)
        npm_args = runner.calls[0][0]
        self.assertEqual(npm_args[0], "/test/bin/npm")
        self.assertIn("--ignore-scripts", npm_args)
        self.assertIn("--no-audit", npm_args)
        self.assertIn("--no-fund", npm_args)
        self.assertIn("--package-lock=false", npm_args)
        self.assertIn("--cache", npm_args)
        cache_path = Path(npm_args[npm_args.index("--cache") + 1])
        prefix_path = Path(npm_args[npm_args.index("--prefix") + 1])
        self.assertTrue(cache_path.is_relative_to(prefix_path))
        self.assertIn(
            f"@openai/codex@{compat_runtime.COMPAT_CODEX_VERSION}", npm_args
        )
        self.assertNotIn("config.toml", " ".join(npm_args))
        self.assertNotIn("auth.json", " ".join(npm_args))

    def test_existing_verified_runtime_is_idempotent(self):
        runner = FakeNpmRunner()
        first = compat_runtime.install(
            self.codex_home,
            runner=runner,
            which=lambda _command: "/test/bin/npm",
        )
        second = compat_runtime.install(
            self.codex_home,
            runner=runner,
            which=lambda _command: "/test/bin/npm",
        )

        self.assertEqual(first["status"], "installed")
        self.assertEqual(second["status"], "already_installed")
        self.assertEqual(sum(call[0][0] == "/test/bin/npm" for call in runner.calls), 1)

    def test_rejects_unverified_existing_runtime_without_overwrite(self):
        target = compat_runtime.runtime_root(self.codex_home)
        target.mkdir(parents=True)
        marker = target / "keep-me"
        marker.write_text("unmanaged", encoding="utf-8")

        with self.assertRaisesRegex(RuntimeError, "unverified compatible runtime"):
            compat_runtime.install(
                self.codex_home,
                runner=FakeNpmRunner(),
                which=lambda _command: "/test/bin/npm",
            )

        self.assertEqual(marker.read_text(encoding="utf-8"), "unmanaged")

    @unittest.skipUnless(hasattr(Path, "symlink_to"), "symlinks are unavailable")
    def test_rejects_intermediate_symlink_escape_before_download(self):
        self.codex_home.mkdir()
        outside = Path(self.tmp.name) / "outside"
        outside.mkdir()
        (self.codex_home / "zai-glm53-subagent").symlink_to(
            outside, target_is_directory=True
        )
        runner = FakeNpmRunner()

        with self.assertRaisesRegex(RuntimeError, "escapes Codex home"):
            compat_runtime.install(
                self.codex_home,
                runner=runner,
                which=lambda _command: "/test/bin/npm",
            )

        self.assertEqual(runner.calls, [])
        self.assertEqual(list(outside.iterdir()), [])


class CompatRuntimeActivationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="glm53-compat-activation-")
        self.codex_home = Path(self.tmp.name) / "codex"
        self.npm_runner = FakeNpmRunner()
        report = compat_runtime.install(
            self.codex_home,
            runner=self.npm_runner,
            which=lambda _command: "/test/bin/npm",
        )
        self.binary = Path(report["codex_cli_path"])

    def tearDown(self):
        self.tmp.cleanup()

    def test_activate_sets_desktop_cli_override_and_is_reversible(self):
        runner = FakeLaunchctlRunner()
        which = lambda command: "/bin/launchctl" if command == "launchctl" else None

        activated = compat_runtime.activate(
            self.codex_home, platform="darwin", runner=runner, which=which
        )
        self.assertEqual(activated["status"], "activated")
        self.assertTrue(activated["restart_required"])
        self.assertEqual(
            runner.calls[-1][0],
            ["/bin/launchctl", "setenv", "CODEX_CLI_PATH", str(self.binary)],
        )

        deactivated = compat_runtime.deactivate(
            self.codex_home, platform="darwin", runner=runner, which=which
        )
        self.assertEqual(deactivated["status"], "deactivated")
        self.assertEqual(
            runner.calls[-1][0],
            ["/bin/launchctl", "unsetenv", "CODEX_CLI_PATH"],
        )

    def test_activate_refuses_to_replace_an_unrelated_override(self):
        runner = FakeLaunchctlRunner(current="/other/codex")

        with self.assertRaisesRegex(RuntimeError, "already set to another executable"):
            compat_runtime.activate(
                self.codex_home,
                platform="darwin",
                runner=runner,
                which=lambda _command: "/bin/launchctl",
            )

        self.assertEqual(runner.current, "/other/codex")

    def test_deactivate_refuses_to_remove_an_unrelated_override(self):
        runner = FakeLaunchctlRunner(current="/other/codex")

        with self.assertRaisesRegex(RuntimeError, "not managed by this installation"):
            compat_runtime.deactivate(
                self.codex_home,
                platform="darwin",
                runner=runner,
                which=lambda _command: "/bin/launchctl",
            )

        self.assertEqual(runner.current, "/other/codex")


if __name__ == "__main__":
    unittest.main()
