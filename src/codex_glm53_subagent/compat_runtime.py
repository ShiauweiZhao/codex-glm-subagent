"""Inspect and deactivate the retired Codex Desktop runtime override.

An earlier release installed Codex 0.148.0-alpha.9 side-by-side and selected it
through ``CODEX_CLI_PATH``.  That executable is protocol-incompatible with the
current Desktop app-server host.  Installation and activation now fail closed;
status and deactivation remain available for exact legacy recovery only.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable, Optional


COMPAT_CODEX_VERSION = "0.148.0-alpha.9"
CODEX_CLI_ENV = "CODEX_CLI_PATH"

Runner = Callable[..., subprocess.CompletedProcess]
Which = Callable[[str], Optional[str]]


def runtime_root(codex_home: Path) -> Path:
    home = Path(os.path.abspath(codex_home))
    target = home / "zai-glm53-subagent" / "codex-runtime" / COMPAT_CODEX_VERSION
    resolved_home = home.resolve(strict=False)
    resolved_target = target.resolve(strict=False)
    try:
        resolved_target.relative_to(resolved_home)
    except ValueError as error:
        raise RuntimeError("compatible runtime path escapes Codex home") from error
    return target


def _find_binary(root: Path) -> Path:
    candidates = sorted(root.glob("node_modules/@openai/codex-*/vendor/*/bin/codex"))
    files = [candidate for candidate in candidates if candidate.is_file()]
    if len(files) != 1:
        raise RuntimeError("compatible runtime does not contain exactly one Codex binary")
    resolved_root = root.resolve(strict=True)
    resolved_binary = files[0].resolve(strict=True)
    try:
        resolved_binary.relative_to(resolved_root)
    except ValueError as error:
        raise RuntimeError("compatible runtime Codex binary escapes its install root") from error
    return resolved_binary


def _verify_binary(binary: Path, runner: Runner) -> None:
    try:
        completed = runner(
            [str(binary), "--version"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as error:
        raise RuntimeError("could not execute the compatible Codex runtime") from error
    expected = f"codex-cli {COMPAT_CODEX_VERSION}"
    if completed.returncode != 0 or completed.stdout.strip() != expected:
        raise RuntimeError("unverified compatible runtime version")


def installed_binary(codex_home: Path, *, runner: Runner = subprocess.run) -> Path:
    root = runtime_root(codex_home)
    binary = _find_binary(root)
    _verify_binary(binary, runner)
    return binary


def install(
    codex_home: Path,
    *,
    runner: Runner = subprocess.run,
    which: Which = shutil.which,
) -> dict:
    """Refuse the retired Desktop-wide runtime workaround."""

    del codex_home, runner, which
    raise RuntimeError(
        "installing a replacement Codex Desktop app-server is disabled; "
        "use the bundled runtime and validate the native child path"
    )


def _launchctl(which: Which) -> str:
    executable = which("launchctl")
    if not executable:
        raise RuntimeError("launchctl is required to select the Desktop runtime")
    return executable


def _current_override(launchctl: str, runner: Runner) -> str:
    try:
        completed = runner(
            [launchctl, "getenv", CODEX_CLI_ENV],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as error:
        raise RuntimeError("could not inspect the Codex Desktop runtime override") from error
    if completed.returncode != 0:
        raise RuntimeError("could not inspect the Codex Desktop runtime override")
    return completed.stdout.strip()


def activate(
    codex_home: Path,
    *,
    platform: str = sys.platform,
    runner: Runner = subprocess.run,
    which: Which = shutil.which,
) -> dict:
    if platform != "darwin":
        raise RuntimeError("automatic Desktop runtime activation is only supported on macOS")
    binary = installed_binary(codex_home, runner=runner)
    launchctl = _launchctl(which)
    current = _current_override(launchctl, runner)
    if current and current != str(binary):
        raise RuntimeError(
            f"{CODEX_CLI_ENV} is already set to another executable; refusing to replace it"
        )
    raise RuntimeError(
        "refusing to replace Codex Desktop app-server: the legacy runtime is "
        "protocol-incompatible with the current Desktop; use the bundled runtime"
    )


def deactivate(
    codex_home: Path,
    *,
    platform: str = sys.platform,
    runner: Runner = subprocess.run,
    which: Which = shutil.which,
) -> dict:
    if platform != "darwin":
        raise RuntimeError("automatic Desktop runtime deactivation is only supported on macOS")
    binary = installed_binary(codex_home, runner=runner)
    launchctl = _launchctl(which)
    current = _current_override(launchctl, runner)
    if not current:
        return {"status": "already_inactive", "restart_required": True}
    if current != str(binary):
        raise RuntimeError(
            f"{CODEX_CLI_ENV} is not managed by this installation; refusing to remove it"
        )
    completed = runner(
        [launchctl, "unsetenv", CODEX_CLI_ENV],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError("could not deactivate the compatible Codex Desktop runtime")
    return {"status": "deactivated", "restart_required": True}


def status(
    codex_home: Path,
    *,
    platform: str = sys.platform,
    runner: Runner = subprocess.run,
    which: Which = shutil.which,
) -> dict:
    try:
        binary = installed_binary(codex_home, runner=runner)
    except (OSError, RuntimeError):
        return {
            "installed": False,
            "version": COMPAT_CODEX_VERSION,
            "active": False,
            "activation_supported": False,
            "reason": "the retired runtime is protocol-incompatible with current Codex Desktop",
        }
    active = False
    if platform == "darwin":
        launchctl = _launchctl(which)
        active = _current_override(launchctl, runner) == str(binary)
    return {
        "installed": True,
        "version": COMPAT_CODEX_VERSION,
        "codex_cli_path": str(binary),
        "active": active,
        "activation_supported": False,
        "reason": "the retired runtime is protocol-incompatible with current Codex Desktop",
    }


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Inspect or deactivate the retired legacy Codex Desktop runtime override"
    )
    parser.add_argument("action", choices=("install", "activate", "deactivate", "status"))
    parser.add_argument("--codex-home", type=Path, default=Path.home() / ".codex")
    parser.add_argument(
        "--activate",
        action="store_true",
        help="retired option; installation and activation now fail closed",
    )
    args = parser.parse_args(argv)
    if args.activate and args.action != "install":
        parser.error("--activate is only valid with install")
    try:
        if args.action == "install":
            report = install(args.codex_home)
            if args.activate:
                report["activation"] = activate(args.codex_home)
        elif args.action == "activate":
            report = activate(args.codex_home)
        elif args.action == "deactivate":
            report = deactivate(args.codex_home)
        else:
            report = status(args.codex_home)
    except RuntimeError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
