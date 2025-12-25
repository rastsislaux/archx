from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


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


def load_config_file(path: Path) -> LoadedConfig:
    raw = json.loads(path.read_text(encoding="utf-8"))
    version, description, cmds = _normalize_top_level(raw)
    normalized: list[dict[str, Any]] = []
    for item in cmds:
        if not isinstance(item, dict):
            raise ValueError(f"Command must be an object in {path}")
        normalized.append(item)
    return LoadedConfig(path=path, version=version, description=description, commands=normalized)


