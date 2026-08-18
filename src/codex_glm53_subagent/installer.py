"""Conservative standalone installer/runtime for the GLM-5.3 worker agent.

Installs the agent catalog, skill tree, one-shot plaintext handoff Hook, runtime
package, rendered credential wrapper, and a SHA256 manifest into distinct
coexistence-safe destinations under ``~/.codex``. No bridge, service, daemon,
SQLite, network, or provider fallback is installed; ``config.toml`` and
``auth.json`` are never created, read, or modified.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Optional


JSON = dict[str, Any]

AGENT_NAME = "zai_glm53_worker"
HOOK_MATCHER = f"^{AGENT_NAME}$"
AGENTS_START = "<!-- codex-glm-subagent:start -->"
AGENTS_END = "<!-- codex-glm-subagent:end -->"
MANIFEST_RELATIVE = Path("zai-glm53-subagent") / "install-manifest.json"

AUTH_BODY_PLACEHOLDER = "__CODEX_GLM53_AUTH_BODY__"
AUTH_BODY_LINE = f'placeholder = "{AUTH_BODY_PLACEHOLDER}"'
MODEL_CATALOG_PLACEHOLDER = "__CODEX_GLM53_MODEL_CATALOG__"
PYTHON_PLACEHOLDER = "__PYTHON_EXECUTABLE__"
RUNTIME_ROOT_PLACEHOLDER = "__CODEX_GLM53_RUNTIME_ROOT__"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _atomic_write(path: Path, data: bytes, mode: int = 0o600) -> bool:
    if path.exists() and path.read_bytes() == data:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise
    return True


def _escaped(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _managed_target(codex_home: Path, relative: str | Path) -> Path:
    if isinstance(relative, Path):
        raw = relative.as_posix()
    elif isinstance(relative, str):
        raw = relative
    else:
        raise RuntimeError("invalid managed path")
    parts = raw.split("/")
    relative_path = Path(raw)
    if (
        not raw
        or relative_path.is_absolute()
        or any(part in ("", ".", "..") for part in parts)
    ):
        raise RuntimeError("invalid managed path")

    home_resolved = codex_home.resolve(strict=False)
    target = codex_home / relative_path
    target_resolved = target.resolve(strict=False)
    try:
        target_resolved.relative_to(home_resolved)
    except ValueError as error:
        raise RuntimeError("managed path escapes Codex home") from error
    if target_resolved == home_resolved:
        raise RuntimeError("invalid managed path")
    return target


def _managed_sources(repo_root: Path) -> list[tuple[Path, Path, int]]:
    sources: list[tuple[Path, Path, int]] = [
        (
            repo_root / "agents" / "zai-glm53-worker.toml",
            Path("agents") / "zai-glm53-worker.toml",
            0o600,
        ),
        (
            repo_root / "agents" / "glm-5.3-models.json",
            Path("zai-glm53-subagent") / "glm-5.3-models.json",
            0o600,
        ),
        (
            repo_root / "hooks" / "plaintext_handoff.py",
            Path("hooks")
            / "codex-zai-glm53-subagent"
            / "plaintext_handoff.py",
            0o600,
        ),
    ]
    skill_root = repo_root / "skills" / "use-zai-glm53-worker"
    for source in sorted(path for path in skill_root.rglob("*") if path.is_file()):
        sources.append(
            (
                source,
                Path("skills")
                / "use-zai-glm53-worker"
                / source.relative_to(skill_root),
                0o600,
            )
        )
    package_root = repo_root / "src" / "codex_glm53_subagent"
    for source in sorted(path for path in package_root.rglob("*.py") if path.is_file()):
        sources.append(
            (
                source,
                Path("zai-glm53-subagent")
                / "runtime"
                / "codex_glm53_subagent"
                / source.relative_to(package_root),
                0o600,
            )
        )
    sources.append(
        (
            repo_root / "scripts" / "codex-zai-glm53-credentials",
            Path("zai-glm53-subagent") / "bin" / "codex-zai-glm53-credentials",
            0o700,
        )
    )
    return sources


def _render_auth_body(helper: Path, platform: str) -> str:
    if platform == "darwin":
        escaped = _escaped(str(helper))
        return (
            "[model_providers.zai_glm53.auth]\n"
            f'command = "{escaped}"\n'
            'args = ["print-api-key"]\n'
            "timeout_ms = 5000\n"
            "refresh_interval_ms = 300000"
        )
    return 'env_key = "ZAI_API_KEY"'


def _source_data(
    source: Path, relative: Path, codex_home: Path, platform: str
) -> bytes:
    data = source.read_bytes()
    if relative == Path("agents") / "zai-glm53-worker.toml":
        helper = (
            codex_home / "zai-glm53-subagent" / "bin" / "codex-zai-glm53-credentials"
        )
        data = data.replace(
            AUTH_BODY_LINE.encode(), _render_auth_body(helper, platform).encode()
        )
        catalog_path = codex_home / "zai-glm53-subagent" / "glm-5.3-models.json"
        data = data.replace(
            MODEL_CATALOG_PLACEHOLDER.encode(), _escaped(str(catalog_path)).encode()
        )
    if relative == Path("zai-glm53-subagent") / "bin" / "codex-zai-glm53-credentials":
        shell_python = shlex.quote(str(Path(sys.executable)))
        data = data.replace(PYTHON_PLACEHOLDER.encode(), shell_python.encode())
        runtime_root = codex_home / "zai-glm53-subagent" / "runtime"
        data = data.replace(
            RUNTIME_ROOT_PLACEHOLDER.encode(), shlex.quote(str(runtime_root)).encode()
        )
    return data


def _load_manifest(manifest_path: Path) -> JSON:
    if not manifest_path.exists():
        return {}
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"cannot parse existing install manifest: {error}") from error
    if not isinstance(payload, dict):
        raise RuntimeError("install manifest must be a JSON object")
    return payload


def _replace_agents_block(existing: str, block: Optional[str]) -> str:
    start = existing.find(AGENTS_START)
    if start >= 0:
        end = existing.find(AGENTS_END, start)
        if end < 0:
            raise RuntimeError("AGENTS.md contains an unterminated managed block")
        end += len(AGENTS_END)
        if end < len(existing) and existing[end] == "\n":
            end += 1
        prefix = existing[:start]
        if prefix.endswith("\n\n"):
            prefix = prefix[:-1]
        existing = prefix + existing[end:]
    if block is None:
        return existing
    prefix = existing
    if prefix and not prefix.endswith("\n"):
        prefix += "\n"
    if prefix and not prefix.endswith("\n\n"):
        prefix += "\n"
    return prefix + block.rstrip() + "\n"


def _load_hooks(path: Path) -> JSON:
    if not path.exists():
        return {"description": "Codex user hooks", "hooks": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"cannot parse existing hooks.json: {error}") from error
    if not isinstance(payload, dict) or not isinstance(payload.get("hooks", {}), dict):
        raise RuntimeError("existing hooks.json must contain an object-valued hooks field")
    payload.setdefault("hooks", {})
    return payload


def _hook_entry(script_path: Path) -> JSON:
    escaped = _escaped(str(script_path))
    return {
        "matcher": HOOK_MATCHER,
        "hooks": [
            {
                "type": "command",
                "command": f'python3 "{escaped}" --mode hook',
                "timeout": 10,
                "statusMessage": "Delivering the staged Z.AI GLM-5.3 assignment",
                "additionalContextLimit": 0,
            }
        ],
    }


def _merge_hook(payload: JSON, entry: JSON) -> JSON:
    events = payload.setdefault("hooks", {})
    current = events.get("SubagentStart") or []
    if not isinstance(current, list):
        raise RuntimeError("hooks.SubagentStart must be a list")
    kept = [
        item
        for item in current
        if not isinstance(item, dict) or item.get("matcher") != HOOK_MATCHER
    ]
    events["SubagentStart"] = kept + [entry]
    return payload


def _remove_hook(payload: JSON) -> JSON:
    events = payload.setdefault("hooks", {})
    current = events.get("SubagentStart") or []
    if isinstance(current, list):
        kept = [
            item
            for item in current
            if not isinstance(item, dict) or item.get("matcher") != HOOK_MATCHER
        ]
        if kept:
            events["SubagentStart"] = kept
        else:
            events.pop("SubagentStart", None)
    return payload


def _prune_empty_owned_dirs(codex_home: Path) -> None:
    owned = [
        Path("hooks") / "codex-zai-glm53-subagent",
        Path("zai-glm53-subagent") / "runtime" / "codex_glm53_subagent",
        Path("zai-glm53-subagent") / "runtime",
        Path("zai-glm53-subagent") / "bin",
        Path("zai-glm53-subagent"),
        Path("skills") / "use-zai-glm53-worker" / "agents",
        Path("skills") / "use-zai-glm53-worker",
        Path("skills"),
    ]
    for relative in owned:
        directory = codex_home / relative
        try:
            if directory.exists() and directory.is_dir():
                directory.rmdir()
        except OSError:
            pass


def install(
    repo_root: Path, codex_home: Path, *, platform: Optional[str] = None
) -> JSON:
    repo_root = Path(repo_root).resolve()
    codex_home = Path(os.path.abspath(codex_home))
    platform = platform or sys.platform
    sources = _managed_sources(repo_root)
    manifest_path = _managed_target(codex_home, MANIFEST_RELATIVE)
    agents_path = _managed_target(codex_home, "AGENTS.md")
    hooks_path = _managed_target(codex_home, "hooks.json")
    old = _load_manifest(manifest_path)
    old_files = old.get("managed_files") or {}
    if not isinstance(old_files, dict):
        raise RuntimeError("install manifest has invalid managed files")

    planned: list[tuple[Path, Path, bytes, int]] = []
    for source, relative, _mode in sources:
        if not source.is_file():
            raise RuntimeError(f"missing install source: {source}")
        destination = _managed_target(codex_home, relative)
        data = _source_data(source, relative, codex_home, platform)
        planned.append((relative, destination, data, _mode))
        if not destination.exists() or destination.read_bytes() == data:
            continue
        expected = old_files.get(str(relative))
        if not expected or _sha256(destination.read_bytes()) != expected:
            raise RuntimeError(
                f"refusing to overwrite unmanaged or modified file: {destination}"
            )

    existing_agents = (
        agents_path.read_text(encoding="utf-8") if agents_path.exists() else ""
    )
    block = (repo_root / "snippets" / "AGENTS.md").read_text(encoding="utf-8")
    merged_agents = _replace_agents_block(existing_agents, block)
    hooks = _merge_hook(
        _load_hooks(hooks_path),
        _hook_entry(
            codex_home
            / "hooks"
            / "codex-zai-glm53-subagent"
            / "plaintext_handoff.py"
        ),
    )

    changed = False
    manifest_files: dict[str, str] = {}
    for relative, destination, data, mode in planned:
        changed = _atomic_write(destination, data, mode) or changed
        manifest_files[str(relative)] = _sha256(data)

    changed = _atomic_write(agents_path, merged_agents.encode("utf-8"), 0o600) or changed
    hooks_data = (json.dumps(hooks, ensure_ascii=False, indent=2) + "\n").encode()
    changed = _atomic_write(hooks_path, hooks_data, 0o600) or changed

    manifest: JSON = {
        "schema_version": 1,
        "agent": AGENT_NAME,
        "hook_matcher": HOOK_MATCHER,
        "managed_files": manifest_files,
    }
    manifest_data = (
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    ).encode("utf-8")
    changed = _atomic_write(manifest_path, manifest_data, 0o600) or changed
    return {
        "status": "installed" if changed else "already_installed",
        "codex_home": str(codex_home),
    }


def uninstall(
    codex_home: Path,
    *,
    platform: Optional[str] = None,
    purge_secrets: bool = False,
    purge_fn: Optional[Callable[[Path], None]] = None,
) -> JSON:
    codex_home = Path(os.path.abspath(codex_home))
    platform = platform or sys.platform
    manifest_path = _managed_target(codex_home, MANIFEST_RELATIVE)
    manifest = _load_manifest(manifest_path)
    managed_files = manifest.get("managed_files") or {}
    if not isinstance(managed_files, dict):
        raise RuntimeError("install manifest has invalid managed files")

    validated: list[tuple[str, str, Path]] = []
    for relative, expected_hash in managed_files.items():
        target = _managed_target(codex_home, relative)
        if (
            not isinstance(expected_hash, str)
            or len(expected_hash) != 64
            or any(character not in "0123456789abcdef" for character in expected_hash)
        ):
            raise RuntimeError("invalid managed hash")
        validated.append((relative, expected_hash, target))

    preserved: list[str] = []
    removable: list[tuple[str, Path]] = []
    for relative, expected_hash, target in validated:
        if not target.exists():
            continue
        try:
            actual_hash = _sha256(target.read_bytes())
        except OSError as error:
            raise RuntimeError("could not inspect managed file") from error
        if actual_hash != expected_hash:
            preserved.append(relative)
            continue
        removable.append((relative, target))

    agents_path = _managed_target(codex_home, "AGENTS.md")
    hooks_path = _managed_target(codex_home, "hooks.json")
    cleaned_agents: Optional[bytes] = None
    if agents_path.exists():
        cleaned = _replace_agents_block(agents_path.read_text(encoding="utf-8"), None)
        cleaned_agents = cleaned.encode("utf-8")
    cleaned_hooks: Optional[bytes] = None
    if hooks_path.exists():
        hooks = _remove_hook(_load_hooks(hooks_path))
        cleaned_hooks = (json.dumps(hooks, ensure_ascii=False, indent=2) + "\n").encode()

    if purge_secrets and platform == "darwin" and purge_fn is not None:
        purge_fn(codex_home)

    removed: list[str] = []
    for relative, target in removable:
        target.unlink()
        removed.append(relative)

    if cleaned_agents is not None:
        _atomic_write(agents_path, cleaned_agents, 0o600)
    if cleaned_hooks is not None:
        _atomic_write(hooks_path, cleaned_hooks, 0o600)

    if manifest_path.exists():
        manifest_path.unlink()

    _prune_empty_owned_dirs(codex_home)

    return {
        "status": "uninstalled",
        "removed": removed,
        "preserved_modified": preserved,
    }


def _credential_purge(codex_home: Path) -> None:
    runtime = codex_home / "zai-glm53-subagent" / "runtime"
    env = dict(os.environ)
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(runtime) + (os.pathsep + existing if existing else "")
    completed = subprocess.run(
        [sys.executable, "-m", "codex_glm53_subagent.credentials", "purge"],
        env=env,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError("credential purge failed")


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Install the GLM-5.3 standalone worker Codex subagent"
    )
    parser.add_argument(
        "action", choices=("install", "uninstall"), nargs="?", default="install"
    )
    parser.add_argument("--codex-home", type=Path, default=Path.home() / ".codex")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
    )
    parser.add_argument("--purge-secrets", action="store_true")
    args = parser.parse_args(argv)
    if args.action == "install" and args.purge_secrets:
        parser.error("--purge-secrets is only valid with uninstall")
    if args.action == "install":
        report = install(args.repo_root, args.codex_home)
    else:
        report = uninstall(
            args.codex_home, purge_secrets=args.purge_secrets, purge_fn=_credential_purge
        )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
