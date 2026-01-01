from __future__ import annotations

import json
import re
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


def _require_int(value: Any, *, what: str) -> int:
    if not isinstance(value, int):
        raise ValueError(f"'{what}' must be an integer if present")
    return value


def _require_str(value: Any, *, what: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"'{what}' must be a non-empty string")
    return value


def _as_table_list(value: Any, *, what: str) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list) and all(isinstance(x, dict) for x in value):
        return value
    raise ValueError(f"'{what}' must be a table or array-of-tables")


def _expand_packages(tables: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for t in tables:
        backend = t.get("backend")
        if backend is not None and not isinstance(backend, str):
            raise ValueError("'backend' must be a string if present (in [[package]]/[[packages]])")

        name = t.get("name")
        names = t.get("names")
        if name is not None and names is not None:
            raise ValueError("Use either 'name' or 'names' in [[package]]/[[packages]], not both")

        if isinstance(name, str) and name:
            cmd: dict[str, Any] = {"kind": "package", "name": name}
            if backend:
                cmd["backend"] = backend
            out.append(cmd)
            continue

        if isinstance(names, list) and all(isinstance(x, str) and x for x in names):
            for n in names:
                cmd = {"kind": "package", "name": n}
                if backend:
                    cmd["backend"] = backend
                out.append(cmd)
            continue

        raise ValueError("[[package]]/[[packages]] requires 'name' (string) or 'names' (array of strings)")
    return out


def _tables_to_commands(
    kind: str,
    tables: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for t in tables:
        existing_kind = t.get("kind")
        if existing_kind is not None and existing_kind != kind:
            raise ValueError(f"Command table for [[{kind}]] must not set kind={existing_kind!r}")
        cmd = dict(t)
        cmd["kind"] = kind
        out.append(cmd)
    return out


def _normalize_top_level(obj: Any) -> tuple[int | None, str | None, list[dict[str, Any]]]:
    if isinstance(obj, list):
        return None, None, obj
    if isinstance(obj, dict):
        version = obj.get("version")
        description = obj.get("description")
        if version is not None:
            _require_int(version, what="version")
        if description is not None and not isinstance(description, str):
            raise ValueError("'description' must be a string if present")

        # Style A: explicit commands list (JSON/YAML list, or TOML [[commands]]).
        cmds = obj.get("commands")
        if isinstance(cmds, list):
            extra_keys = set(obj.keys()) - {"version", "description", "commands"}
            if extra_keys:
                extra = ", ".join(sorted(extra_keys))
                raise ValueError(
                    f"When using 'commands', no other top-level command tables are allowed (found: {extra})."
                )
            return version, description, cmds

        # Style B: explicit generic command list ([[command]]), supports non-builtin plugins.
        generic = obj.get("command")
        if isinstance(generic, list):
            extra_keys = set(obj.keys()) - {"version", "description", "command"}
            if extra_keys:
                extra = ", ".join(sorted(extra_keys))
                raise ValueError(
                    f"When using 'command', no other top-level command tables are allowed (found: {extra})."
                )
            for i, t in enumerate(generic, start=1):
                if not isinstance(t, dict):
                    raise ValueError(f"[[command]] entry {i} must be a table")
                k = t.get("kind") or t.get("command")
                if not isinstance(k, str) or not k:
                    raise ValueError(f"[[command]] entry {i} requires 'kind'")
            return version, description, generic

        # Style C: TOML-friendly "array-of-tables per kind", e.g. [[package]], [[symlink]], [[hyprpm]].
        out_cmds: list[dict[str, Any]] = []
        for key, value in obj.items():
            if key in {"version", "description"}:
                continue
            tables = _as_table_list(value, what=key)

            if key in {"package", "packages"}:
                out_cmds.extend(_expand_packages(tables))
            elif key in {"symlink", "symlinks"}:
                out_cmds.extend(_tables_to_commands("symlink", tables))
            elif key in {"shell", "shells"}:
                out_cmds.extend(_tables_to_commands("shell", tables))
            elif key in {"service", "services"}:
                out_cmds.extend(_tables_to_commands("service", tables))
            else:
                # Non-builtin plugins: [[hyprpm]] ... becomes kind="hyprpm", etc.
                out_cmds.extend(_tables_to_commands(key, tables))

        if out_cmds:
            return version, description, out_cmds
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


_TOML_AOT_HEADER_RE = re.compile(r"^\s*\[\[\s*([A-Za-z0-9_.-]+)\s*\]\]\s*$", re.MULTILINE)


def _resolve_toml_path(obj: Any, dotted: str) -> Any:
    cur: Any = obj
    for part in dotted.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def _normalize_toml_top_level(
    *,
    raw: Any,
    text: str,
    path: Path,
) -> tuple[int | None, str | None, list[dict[str, Any]]]:
    """
    TOML-specific normalization that preserves the *appearance order* of array-of-tables.

    Why: tomllib groups all [[package]] tables together under key "package", which loses
    interleaving like:
        [[package]] ...
        [[symlink]] ...
        [[package]] ...

    We reconstruct the intended command sequence by scanning the TOML text for [[...]]
    headers in order and consuming the corresponding tables from the parsed structure.
    """
    # Preserve legacy list formats too (rare in TOML but supported for consistency).
    if isinstance(raw, list):
        return None, None, raw

    if not isinstance(raw, dict):
        raise ValueError("Config must be a list of command objects or {version, commands:[...]}.")

    version = raw.get("version")
    description = raw.get("description")
    if version is not None:
        _require_int(version, what="version")
    if description is not None and not isinstance(description, str):
        raise ValueError("'description' must be a string if present")

    # Style A: explicit list ([[commands]]).
    cmds = raw.get("commands")
    if isinstance(cmds, list):
        extra_keys = set(raw.keys()) - {"version", "description", "commands"}
        if extra_keys:
            extra = ", ".join(sorted(extra_keys))
            raise ValueError(
                f"When using 'commands', no other top-level command tables are allowed (found: {extra})."
            )
        return version, description, cmds

    # Style B: explicit generic list ([[command]]).
    generic = raw.get("command")
    if isinstance(generic, list):
        extra_keys = set(raw.keys()) - {"version", "description", "command"}
        if extra_keys:
            extra = ", ".join(sorted(extra_keys))
            raise ValueError(
                f"When using 'command', no other top-level command tables are allowed (found: {extra})."
            )
        for i, t in enumerate(generic, start=1):
            if not isinstance(t, dict):
                raise ValueError(f"[[command]] entry {i} must be a table")
            k = t.get("kind") or t.get("command")
            if not isinstance(k, str) or not k:
                raise ValueError(f"[[command]] entry {i} requires 'kind'")
        return version, description, generic

    # Style C: order-preserving kind tables ([[package]], [[symlink]], [[hyprpm]], ...).
    headers = _TOML_AOT_HEADER_RE.findall(text)
    if not headers:
        raise ValueError("TOML config must define either [[commands]], [[command]], or at least one [[<kind>]] table.")

    def kind_for_header(h: str) -> str:
        # Preserve exact kind strings, with small convenience aliases.
        if h in {"package", "packages"}:
            return "package"
        if h in {"symlink", "symlinks"}:
            return "symlink"
        if h in {"shell", "shells"}:
            return "shell"
        if h in {"service", "services"}:
            return "service"
        return h

    counters: dict[str, int] = {}
    out_cmds: list[dict[str, Any]] = []

    for header in headers:
        # Skip headers that are metadata-only or unsupported; we only match [[...]] anyway.
        # But explicitly disallow mixed use if someone includes [[commands]] or [[command]] here.
        if header in {"commands", "command"}:
            raise ValueError(
                f"{path}: do not mix [[{header}]] with kind tables like [[package]]; choose one style."
            )

        tables_obj = _resolve_toml_path(raw, header)
        if not isinstance(tables_obj, list) or not all(isinstance(x, dict) for x in tables_obj):
            raise ValueError(f"{path}: [[{header}]] does not parse as an array-of-tables")

        idx = counters.get(header, 0)
        if idx >= len(tables_obj):
            raise ValueError(f"{path}: too many [[{header}]] headers (parsed only {len(tables_obj)} tables)")
        counters[header] = idx + 1
        table = tables_obj[idx]

        if header in {"package", "packages"}:
            out_cmds.extend(_expand_packages([table]))
            continue

        k = kind_for_header(header)
        out_cmds.extend(_tables_to_commands(k, [table]))

    # Validate consumption: ensure every parsed array-of-tables was represented in the text scan.
    for key, value in raw.items():
        if key in {"version", "description"}:
            continue
        if isinstance(value, list) and all(isinstance(x, dict) for x in value):
            used = counters.get(key, 0)
            if used != len(value):
                raise ValueError(
                    f"{path}: parsed {len(value)} [[{key}]] tables but found {used} headers in file"
                )

    return version, description, out_cmds


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
        version, description, cmds = _normalize_top_level(raw)
    elif suffix == ".toml":
        raw = _load_toml(text, path)
        version, description, cmds = _normalize_toml_top_level(raw=raw, text=text, path=path)
    elif suffix in (".yaml", ".yml"):
        raw = _load_yaml(text, path)
        version, description, cmds = _normalize_top_level(raw)
    else:
        raise ValueError(
            f"Unsupported config format for {path} (expected .json, .toml, .yaml, .yml)."
        )
    normalized: list[dict[str, Any]] = []
    for item in cmds:
        if not isinstance(item, dict):
            raise ValueError(f"Command must be an object in {path}")
        normalized.append(item)
    return LoadedConfig(path=path, version=version, description=description, commands=normalized)


