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


def seed_legacy_runtime(codex_home):
    binary = (
        compat_runtime.runtime_root(codex_home)
        / "node_modules"
        / "@openai"
        / "codex-darwin-arm64"
        / "vendor"
        / "aarch64-apple-darwin"
        / "bin"
        / "codex"
    )
    binary.parent.mkdir(parents=True)
    binary.write_text("legacy compatible codex", encoding="utf-8")
    binary.chmod(0o700)
    return binary.resolve()


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

    def test_install_refuses_unsupported_desktop_override_before_npm(self):
        runner = FakeNpmRunner()

        with self.assertRaisesRegex(
            RuntimeError,
            "no released Codex runtime verified by this repository supports",
        ):
            compat_runtime.install(
                self.codex_home,
                runner=runner,
                which=lambda command: "/test/bin/npm" if command == "npm" else None,
            )

        self.assertEqual(runner.calls, [])


class CompatRuntimeActivationTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="glm53-compat-activation-")
        self.codex_home = Path(self.tmp.name) / "codex"
        self.binary = seed_legacy_runtime(self.codex_home)

    def tearDown(self):
        self.tmp.cleanup()

    def test_activate_refuses_to_replace_desktop_app_server(self):
        runner = FakeLaunchctlRunner()
        which = lambda command: "/bin/launchctl" if command == "launchctl" else None

        with self.assertRaisesRegex(
            RuntimeError, "refusing to replace Codex Desktop app-server"
        ):
            compat_runtime.activate(
                self.codex_home, platform="darwin", runner=runner, which=which
            )

        self.assertFalse(any(call[0][1] == "setenv" for call in runner.calls))

    def test_deactivate_removes_the_legacy_managed_override(self):
        runner = FakeLaunchctlRunner(current=str(self.binary))
        which = lambda command: "/bin/launchctl" if command == "launchctl" else None

        deactivated = compat_runtime.deactivate(
            self.codex_home, platform="darwin", runner=runner, which=which
        )
        self.assertEqual(deactivated["status"], "deactivated")
        self.assertEqual(
            runner.calls[-1][0],
            ["/bin/launchctl", "unsetenv", "CODEX_CLI_PATH"],
        )

    def test_status_marks_legacy_override_as_unsupported(self):
        runner = FakeLaunchctlRunner(current=str(self.binary))

        report = compat_runtime.status(
            self.codex_home,
            platform="darwin",
            runner=runner,
            which=lambda _command: "/bin/launchctl",
        )

        self.assertTrue(report["installed"])
        self.assertTrue(report["active"])
        self.assertFalse(report["activation_supported"])
        self.assertIn("protocol-incompatible", report["reason"])

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
