"""Explicitly activate the GLM metadata catalog at Codex startup scope.

Codex applies ``model_catalog_json`` only while constructing its shared model
manager. Agent-role config is a per-thread override and therefore cannot add
GLM metadata to that manager. This module provides a separate, opt-in command
that preserves the current parent catalog, injects hidden GLM metadata, and
adds one removable managed block to ``config.toml``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import tomllib
from pathlib import Path
from typing import Any, Optional


JSON = dict[str, Any]

GLM_MODEL = "glm-5.3"
PARENT_GUARDIAN_MODEL = "codex-auto-review"
RUNTIME_RELATIVE = Path("zai-glm53-subagent")
SOURCE_CATALOG_RELATIVE = RUNTIME_RELATIVE / "glm-5.3-models.json"
STARTUP_CATALOG_RELATIVE = RUNTIME_RELATIVE / "startup-models.json"
BACKUP_RELATIVE = RUNTIME_RELATIVE / "config-before-startup-catalog.toml"
MANAGED_BEGIN = "# codex-glm-subagent startup catalog: begin"
MANAGED_END = "# codex-glm-subagent startup catalog: end"


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


def _read_json_object(path: Path, label: str) -> JSON:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise RuntimeError(f"missing {label}: {path}") from error
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"cannot parse {label}: {error}") from error
    if not isinstance(payload, dict):
        raise RuntimeError(f"{label} must be a JSON object")
    return payload


def _models(payload: JSON, label: str) -> list[JSON]:
    raw = payload.get("models")
    if not isinstance(raw, list) or not raw:
        raise RuntimeError(f"{label} must contain a non-empty models list")
    result: list[JSON] = []
    seen: set[str] = set()
    for entry in raw:
        if not isinstance(entry, dict):
            raise RuntimeError(f"{label} contains a non-object model")
        slug = entry.get("slug")
        if not isinstance(slug, str) or not slug or slug in seen:
            raise RuntimeError(f"{label} contains an invalid or duplicate model slug")
        seen.add(slug)
        result.append(dict(entry))
    return result


def _parse_config(data: bytes) -> JSON:
    try:
        return tomllib.loads(data.decode("utf-8")) if data else {}
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
        raise RuntimeError(f"cannot parse config.toml: {error}") from error


def _managed_bounds(text: str) -> Optional[tuple[int, int]]:
    begin_count = text.count(MANAGED_BEGIN)
    end_count = text.count(MANAGED_END)
    if begin_count == 0 and end_count == 0:
        return None
    if begin_count != 1 or end_count != 1:
        raise RuntimeError("config.toml contains an invalid managed startup catalog block")
    begin = text.index(MANAGED_BEGIN)
    end = text.index(MANAGED_END, begin) + len(MANAGED_END)
    if end < len(text) and text[end] == "\n":
        end += 1
    return begin, end


def _managed_block(startup_catalog: Path) -> str:
    encoded_path = json.dumps(str(startup_catalog), ensure_ascii=False)
    return (
        f"{MANAGED_BEGIN}\n"
        f"model_catalog_json = {encoded_path}\n"
        f"{MANAGED_END}\n"
    )


def _startup_catalog(codex_home: Path, config: JSON) -> JSON:
    cache = _read_json_object(codex_home / "models_cache.json", "Codex model cache")
    base_models = _models(cache, "Codex model cache")
    by_slug = {entry["slug"]: entry for entry in base_models}

    parent_model = config.get("model")
    if not isinstance(parent_model, str) or parent_model not in by_slug:
        raise RuntimeError(
            "config.toml must select a parent model present in models_cache.json"
        )
    if PARENT_GUARDIAN_MODEL not in by_slug:
        raise RuntimeError(
            "Codex model cache is missing codex-auto-review; refusing to replace "
            "the parent startup catalog"
        )

    source = _read_json_object(
        codex_home / SOURCE_CATALOG_RELATIVE, "installed GLM model catalog"
    )
    glm_models = _models(source, "installed GLM model catalog")
    if len(glm_models) != 1 or glm_models[0]["slug"] != GLM_MODEL:
        raise RuntimeError("installed GLM model catalog must contain only glm-5.3")
    glm = glm_models[0]
    if glm.get("auto_review_model_override") != GLM_MODEL:
        raise RuntimeError("glm-5.3 must route automatic review to itself")

    # The global startup catalog is shared by the parent and every child. Keep
    # GLM out of the parent's picker/default selection while retaining metadata
    # lookup for the explicitly configured worker.
    glm["visibility"] = "hide"
    combined = [entry for entry in base_models if entry["slug"] != GLM_MODEL]
    combined.append(glm)
    return {"models": combined}


def activate(codex_home: Path) -> JSON:
    codex_home = Path(os.path.abspath(codex_home))
    config_path = codex_home / "config.toml"
    config_data = config_path.read_bytes() if config_path.exists() else b""
    config = _parse_config(config_data)
    config_text = config_data.decode("utf-8")
    bounds = _managed_bounds(config_text)
    startup_path = codex_home / STARTUP_CATALOG_RELATIVE

    if bounds is None and "model_catalog_json" in config:
        raise RuntimeError(
            "refusing to replace unmanaged model_catalog_json in config.toml"
        )
    if bounds is not None and config.get("model_catalog_json") != str(startup_path):
        raise RuntimeError("managed model_catalog_json does not match the installed path")

    # Complete all semantic validation before writing any file.
    catalog = _startup_catalog(codex_home, config)
    catalog_data = (json.dumps(catalog, ensure_ascii=False, indent=2) + "\n").encode()

    if bounds is None:
        backup_path = codex_home / BACKUP_RELATIVE
        _atomic_write(backup_path, config_data, 0o600)
        new_config = _managed_block(startup_path).encode() + config_data
        status_value = "activated"
    else:
        new_config = config_data
        status_value = "already_activated"

    _atomic_write(startup_path, catalog_data, 0o600)
    _atomic_write(config_path, new_config, 0o600)
    return {
        "status": status_value,
        "model": GLM_MODEL,
        "model_catalog_json": str(startup_path),
        "restart_required": True,
    }


def deactivate(codex_home: Path) -> JSON:
    codex_home = Path(os.path.abspath(codex_home))
    config_path = codex_home / "config.toml"
    if not config_path.exists():
        return {"status": "already_inactive", "restart_required": False}
    config_data = config_path.read_bytes()
    config_text = config_data.decode("utf-8")
    bounds = _managed_bounds(config_text)
    if bounds is None:
        return {"status": "already_inactive", "restart_required": False}

    config = _parse_config(config_data)
    expected = str(codex_home / STARTUP_CATALOG_RELATIVE)
    if config.get("model_catalog_json") != expected:
        raise RuntimeError("managed model_catalog_json does not match the installed path")
    begin, end = bounds
    restored = (config_text[:begin] + config_text[end:]).encode("utf-8")
    _parse_config(restored)
    _atomic_write(config_path, restored, 0o600)
    return {"status": "deactivated", "restart_required": True}


def status(codex_home: Path) -> JSON:
    codex_home = Path(os.path.abspath(codex_home))
    config_path = codex_home / "config.toml"
    if not config_path.exists():
        return {"status": "inactive", "restart_required": False}
    config_data = config_path.read_bytes()
    bounds = _managed_bounds(config_data.decode("utf-8"))
    if bounds is None:
        return {"status": "inactive", "restart_required": False}
    config = _parse_config(config_data)
    expected = str(codex_home / STARTUP_CATALOG_RELATIVE)
    if config.get("model_catalog_json") != expected:
        raise RuntimeError("managed model_catalog_json does not match the installed path")
    catalog = _read_json_object(Path(expected), "startup model catalog")
    models = _models(catalog, "startup model catalog")
    glm = next((entry for entry in models if entry["slug"] == GLM_MODEL), None)
    if glm is None or glm.get("auto_review_model_override") != GLM_MODEL:
        raise RuntimeError("startup model catalog does not contain valid GLM review metadata")
    return {
        "status": "active",
        "restart_required": True,
        "model": GLM_MODEL,
        "model_catalog_json": expected,
    }


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Manage the opt-in GLM startup model catalog"
    )
    parser.add_argument("action", choices=("activate", "deactivate", "status"))
    parser.add_argument("--codex-home", type=Path, default=Path.home() / ".codex")
    args = parser.parse_args(argv)
    if args.action == "activate":
        report = activate(args.codex_home)
    elif args.action == "deactivate":
        report = deactivate(args.codex_home)
    else:
        report = status(args.codex_home)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
