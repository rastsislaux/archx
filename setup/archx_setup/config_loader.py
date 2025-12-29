from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from json import JSONDecodeError


@dataclass(frozen=True)
class LoadedConfig:
    path: Path
    version: int | None
    description: str | None
    commands: list[dict[str, Any]]


def _normalize_top_level(obj: Any) -> tuple[int | None, str | None, list[dict[str, Any]]]:
    if isinstance(obj, list):
        return None, None, obj
    if isinstance(obj, dict):
        cmds = obj.get("commands")
        if isinstance(cmds, list):
            version = obj.get("version")
            description = obj.get("description")
            if version is not None and not isinstance(version, int):
                raise ValueError("'version' must be an integer if present")
            if description is not None and not isinstance(description, str):
                raise ValueError("'description' must be a string if present")
            return version, description, cmds
    raise ValueError("Config must be a list of command objects or {version, commands:[...]}.")


def _load_json(text: str, path: Path) -> Any:
    try:
        return json.loads(text)
    except JSONDecodeError as e:
        raise ValueError(
            f"Invalid JSON in {path} at line {e.lineno}, column {e.colno}: {e.msg}"
        ) from e


def _load_toml(text: str, path: Path) -> Any:
    # TOML parsing is in stdlib as of Python 3.11. On older Pythons, allow tomli if installed.
    try:
        import tomllib  # type: ignore
    except Exception:  # pragma: no cover
        try:
            import tomli as tomllib  # type: ignore
        except Exception as e:
            raise ValueError(
                "TOML config support requires Python 3.11+ (tomllib) or 'tomli' installed. "
                f"Failed to import TOML parser for {path}."
            ) from e
    try:
        return tomllib.loads(text)
    except Exception as e:
        raise ValueError(f"Invalid TOML in {path}: {e}") from e


def _load_yaml(text: str, path: Path) -> Any:
    try:
        import yaml  # type: ignore
    except Exception as e:
        raise ValueError(
            "YAML config support requires PyYAML. Install it (e.g. 'python -m pip install pyyaml') "
            f"and retry loading {path}."
        ) from e
    try:
        return yaml.safe_load(text)
    except Exception as e:
        mark = getattr(e, "problem_mark", None)
        if mark is not None and hasattr(mark, "line") and hasattr(mark, "column"):
            line = int(mark.line) + 1
            col = int(mark.column) + 1
            raise ValueError(f"Invalid YAML in {path} at line {line}, column {col}: {e}") from e
        raise ValueError(f"Invalid YAML in {path}: {e}") from e


def load_config_file(path: Path) -> LoadedConfig:
    text = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()

    if suffix == ".json":
        raw = _load_json(text, path)
    elif suffix == ".toml":
        raw = _load_toml(text, path)
    elif suffix in (".yaml", ".yml"):
        raw = _load_yaml(text, path)
    else:
        raise ValueError(
            f"Unsupported config format for {path} (expected .json, .toml, .yaml, .yml)."
        )

    version, description, cmds = _normalize_top_level(raw)
    normalized: list[dict[str, Any]] = []
    for item in cmds:
        if not isinstance(item, dict):
            raise ValueError(f"Command must be an object in {path}")
        normalized.append(item)
    return LoadedConfig(path=path, version=version, description=description, commands=normalized)


