"""Install and select a known-compatible, unmodified Codex runtime.

Codex 0.149.0 stopped allowing a registered child role to select a provider
different from its parent.  The last runtime verified with this repository's
native cross-provider child contract is installed side-by-side and selected by
Codex Desktop's ``CODEX_CLI_PATH`` environment override.  This module never
edits Codex config or authentication files and never patches the Codex binary.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable, Optional


COMPAT_CODEX_VERSION = "0.148.0-alpha.9"
COMPAT_PACKAGE = f"@openai/codex@{COMPAT_CODEX_VERSION}"
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
    """Install the pinned official npm package without running package scripts."""

    target = runtime_root(codex_home)
    if target.exists() or target.is_symlink():
        try:
            binary = installed_binary(codex_home, runner=runner)
        except (OSError, RuntimeError) as error:
            raise RuntimeError(
                "refusing to overwrite an unverified compatible runtime"
            ) from error
        return {
            "status": "already_installed",
            "version": COMPAT_CODEX_VERSION,
            "codex_cli_path": str(binary),
        }

    npm = which("npm")
    if not npm:
        raise RuntimeError("npm is required to install the compatible Codex runtime")

    parent = target.parent
    parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".codex-runtime-staging-", dir=parent))
    npm_cache = staging / ".npm-cache"
    try:
        completed = runner(
            [
                npm,
                "install",
                "--prefix",
                str(staging),
                "--cache",
                str(npm_cache),
                "--ignore-scripts",
                "--no-audit",
                "--no-fund",
                "--package-lock=false",
                COMPAT_PACKAGE,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError("npm failed to install the compatible Codex runtime")
        staged_binary = _find_binary(staging)
        _verify_binary(staged_binary, runner)
        if npm_cache.exists():
            shutil.rmtree(npm_cache)
        os.replace(staging, target)
    except OSError as error:
        raise RuntimeError("could not install the compatible Codex runtime") from error
    finally:
        if staging.exists() or staging.is_symlink():
            shutil.rmtree(staging)

    binary = installed_binary(codex_home, runner=runner)
    return {
        "status": "installed",
        "version": COMPAT_CODEX_VERSION,
        "codex_cli_path": str(binary),
    }


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
    if current == str(binary):
        return {
            "status": "already_active",
            "codex_cli_path": str(binary),
            "restart_required": True,
        }
    completed = runner(
        [launchctl, "setenv", CODEX_CLI_ENV, str(binary)],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError("could not activate the compatible Codex Desktop runtime")
    return {
        "status": "activated",
        "codex_cli_path": str(binary),
        "restart_required": True,
    }


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
        return {"installed": False, "version": COMPAT_CODEX_VERSION, "active": False}
    active = False
    if platform == "darwin":
        launchctl = _launchctl(which)
        active = _current_override(launchctl, runner) == str(binary)
    return {
        "installed": True,
        "version": COMPAT_CODEX_VERSION,
        "codex_cli_path": str(binary),
        "active": active,
    }


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Manage the Codex runtime compatible with cross-provider child roles"
    )
    parser.add_argument("action", choices=("install", "activate", "deactivate", "status"))
    parser.add_argument("--codex-home", type=Path, default=Path.home() / ".codex")
    parser.add_argument(
        "--activate",
        action="store_true",
        help="activate the runtime immediately after install (macOS; restart required)",
    )
    args = parser.parse_args(argv)
    if args.activate and args.action != "install":
        parser.error("--activate is only valid with install")
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
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
