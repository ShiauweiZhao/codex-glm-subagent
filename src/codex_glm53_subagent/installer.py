"""Conservative standalone installer/runtime for the GLM-5.3 worker agent.

Installs the agent catalog, skill tree, runtime package, rendered credential
wrapper, and a SHA256 manifest into distinct coexistence-safe destinations
under ``~/.codex``. No Hook, bridge, service, daemon, SQLite, network, or
provider fallback is installed; ``config.toml`` and ``auth.json`` are never
created, read, or modified.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Optional


JSON = dict[str, Any]

AGENT_NAME = "zai_glm53_worker"
AGENTS_START = "<!-- codex-glm53-subagent:start -->"
AGENTS_END = "<!-- codex-glm53-subagent:end -->"
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
        escaped_python = _escaped(str(Path(sys.executable)))
        data = data.replace(PYTHON_PLACEHOLDER.encode(), escaped_python.encode())
        runtime_root = codex_home / "zai-glm53-subagent" / "runtime"
        data = data.replace(RUNTIME_ROOT_PLACEHOLDER.encode(), str(runtime_root).encode())
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


def _prune_empty_owned_dirs(codex_home: Path) -> None:
    owned = [
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
    manifest_path = codex_home / MANIFEST_RELATIVE
    old = _load_manifest(manifest_path)
    old_files = old.get("managed_files") or {}
    if not isinstance(old_files, dict):
        old_files = {}

    for source, relative, _mode in sources:
        if not source.is_file():
            raise RuntimeError(f"missing install source: {source}")
        destination = codex_home / relative
        data = _source_data(source, relative, codex_home, platform)
        if not destination.exists() or destination.read_bytes() == data:
            continue
        expected = old_files.get(str(relative))
        if not expected or _sha256(destination.read_bytes()) != expected:
            raise RuntimeError(
                f"refusing to overwrite unmanaged or modified file: {destination}"
            )

    agents_path = codex_home / "AGENTS.md"
    existing_agents = (
        agents_path.read_text(encoding="utf-8") if agents_path.exists() else ""
    )
    block = (repo_root / "snippets" / "AGENTS.md").read_text(encoding="utf-8")
    merged_agents = _replace_agents_block(existing_agents, block)

    changed = False
    manifest_files: dict[str, str] = {}
    for source, relative, mode in sources:
        data = _source_data(source, relative, codex_home, platform)
        destination = codex_home / relative
        changed = _atomic_write(destination, data, mode) or changed
        manifest_files[str(relative)] = _sha256(data)

    changed = _atomic_write(agents_path, merged_agents.encode("utf-8"), 0o600) or changed

    manifest: JSON = {
        "schema_version": 1,
        "agent": AGENT_NAME,
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
    manifest_path = codex_home / MANIFEST_RELATIVE
    manifest = _load_manifest(manifest_path)
    preserved: list[str] = []
    removed: list[str] = []
    for relative, expected_hash in (manifest.get("managed_files") or {}).items():
        target = codex_home / relative
        if not target.exists():
            continue
        if _sha256(target.read_bytes()) != expected_hash:
            preserved.append(relative)
            continue
        target.unlink()
        removed.append(relative)

    agents_path = codex_home / "AGENTS.md"
    if agents_path.exists():
        cleaned = _replace_agents_block(agents_path.read_text(encoding="utf-8"), None)
        _atomic_write(agents_path, cleaned.encode("utf-8"), 0o600)

    if manifest_path.exists():
        manifest_path.unlink()

    _prune_empty_owned_dirs(codex_home)

    if purge_secrets and platform == "darwin" and purge_fn is not None:
        purge_fn(codex_home)

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
    subprocess.run(
        [sys.executable, "-m", "codex_glm53_subagent.credentials", "purge"],
        env=env,
        check=False,
    )


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
