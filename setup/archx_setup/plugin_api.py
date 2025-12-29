"""
Stable SDK for external command plugins.

Goal: plugin authors should only depend on this module + the plugin interfaces
under `archx_setup.plugins.*`, and avoid importing internal implementation
details from the core codebase.
"""

from __future__ import annotations

from archx_setup.core import Command, Context, Options
from archx_setup.util import (
    CommandRunner,
    RunResult,
    expand_path,
    sh_join,
    xdg_config_home,
)

__all__ = [
    "Command",
    "Context",
    "Options",
    "CommandRunner",
    "RunResult",
    "expand_path",
    "sh_join",
    "xdg_config_home",
]


