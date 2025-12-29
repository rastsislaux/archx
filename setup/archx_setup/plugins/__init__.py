"""
Plugin system for archx-setup commands.

Plugins are loaded at runtime and registered by the CLI.
"""

from archx_setup.plugins.api import CommandPlugin
from archx_setup.plugins.factory import CommandFactory
from archx_setup.plugins.loader import PluginLoadResult, load_plugins

__all__ = ["CommandPlugin", "CommandFactory", "PluginLoadResult", "load_plugins"]


