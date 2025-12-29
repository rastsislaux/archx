from __future__ import annotations

import importlib.util
import os
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Iterable, Sequence

from archx_setup.plugins.api import CommandPlugin
from archx_setup.plugins.builtin import builtin_plugins
from archx_setup.util import xdg_config_home


@dataclass(frozen=True)
class PluginLoadResult:
    plugins: list[CommandPlugin]
    errors: list[str]


def _load_plugin_module_from_file(py_file: Path, *, module_name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(module_name, py_file)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load plugin module from {py_file}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _extract_plugin(mod: ModuleType, *, origin: Path) -> CommandPlugin:
    # Preferred: PLUGIN = <object implementing CommandPlugin>
    plugin = getattr(mod, "PLUGIN", None)
    if plugin is not None:
        return plugin
    # Alternative: def get_plugin() -> CommandPlugin
    get_plugin = getattr(mod, "get_plugin", None)
    if callable(get_plugin):
        return get_plugin()
    raise ValueError(
        f"Plugin module {origin} must define PLUGIN or get_plugin()."
    )


def _default_user_plugins_dir() -> Path:
    return xdg_config_home() / "archx-setup" / "plugins"


def _split_env_paths(value: str) -> list[Path]:
    out: list[Path] = []
    for part in value.split(os.pathsep):
        part = part.strip()
        if not part:
            continue
        out.append(Path(part))
    return out


def load_plugins(
    *,
    include_builtin: bool = True,
    plugin_dirs: Sequence[Path] | None = None,
) -> PluginLoadResult:
    """
    Loads built-in plugins plus plugins from directories.

    Directory plugins are plain .py files. Each file must define:
      - PLUGIN (preferred), or
      - get_plugin()
    """

    plugins: list[CommandPlugin] = []
    errors: list[str] = []

    if include_builtin:
        plugins.extend(builtin_plugins())

    dirs: list[Path] = []
    if plugin_dirs:
        dirs.extend(list(plugin_dirs))

    # Allow env override/addition without needing to touch CLI.
    env = os.environ.get("ARCHX_SETUP_PLUGINS_DIRS")
    if env:
        dirs.extend(_split_env_paths(env))

    # Default user plugins dir (~/.config/archx-setup/plugins) is searched if it exists.
    user_dir = _default_user_plugins_dir()
    if user_dir.exists():
        dirs.append(user_dir)

    # De-dupe while preserving order.
    seen: set[Path] = set()
    unique_dirs: list[Path] = []
    for d in dirs:
        try:
            d = d.expanduser().resolve()
        except Exception:
            d = d.expanduser()
        if d in seen:
            continue
        seen.add(d)
        unique_dirs.append(d)

    for d in unique_dirs:
        if not d.exists():
            errors.append(f"Plugins dir does not exist: {d}")
            continue
        if not d.is_dir():
            errors.append(f"Plugins path is not a directory: {d}")
            continue
        for py_file in sorted(d.glob("*.py")):
            if py_file.name.startswith("_"):
                continue
            module_name = f"archx_setup_user_plugin_{py_file.stem}_{abs(hash(str(py_file)))}"
            try:
                mod = _load_plugin_module_from_file(py_file, module_name=module_name)
                plugin = _extract_plugin(mod, origin=py_file)
                plugins.append(plugin)
            except Exception as e:
                errors.append(f"Failed to load plugin {py_file}: {e}")

    return PluginLoadResult(plugins=plugins, errors=errors)


