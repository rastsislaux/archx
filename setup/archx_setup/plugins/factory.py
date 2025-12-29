from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from archx_setup.core import Command, Context
from archx_setup.plugins.api import CommandHandler, CommandPlugin


@dataclass(frozen=True)
class RegisteredPlugin:
    kind: str
    backend: str | None
    plugin: CommandPlugin


class CommandFactory:
    """
    Registry-backed factory. Core code does not know about concrete command kinds.
    """

    def __init__(self, plugins: Iterable[CommandPlugin]) -> None:
        by_handler: dict[tuple[str, str | None], CommandPlugin] = {}
        for plugin in plugins:
            if not getattr(plugin, "name", None):
                raise ValueError("Plugin is missing required attribute 'name'")
            handlers = plugin.handlers()
            if not handlers:
                raise ValueError(f"Plugin {plugin.name} must handle at least one command handler")
            for h in handlers:
                if not isinstance(h, CommandHandler):
                    raise ValueError(f"Plugin {plugin.name} returned invalid handler: {h!r}")
                if not isinstance(h.kind, str) or not h.kind:
                    raise ValueError(f"Plugin {plugin.name} returned invalid kind: {h.kind!r}")
                if h.backend is not None and (not isinstance(h.backend, str) or not h.backend):
                    raise ValueError(f"Plugin {plugin.name} returned invalid backend: {h.backend!r}")
                key = (h.kind, h.backend)
                if key in by_handler:
                    other = by_handler[key]
                    raise ValueError(
                        f"Duplicate handler for {h.kind}/{h.backend or '<default>'}: "
                        f"{other.name} and {plugin.name}"
                    )
                by_handler[key] = plugin
        self._by_handler = by_handler

    @property
    def registered_kinds(self) -> list[str]:
        kinds = {k for (k, _b) in self._by_handler.keys()}
        return sorted(kinds)

    @property
    def registered_handlers(self) -> list[str]:
        items: list[str] = []
        for (kind, backend) in sorted(
            self._by_handler.keys(),
            key=lambda kb: (kb[0], kb[1] is not None, kb[1] or ""),
        ):
            items.append(f"{kind}/{backend or '<default>'}")
        return items

    def from_dict(self, raw: dict[str, Any], ctx: Context) -> Command:
        kind = raw.get("kind") or raw.get("command")
        if not isinstance(kind, str):
            raise ValueError("Command missing 'kind'")
        backend = raw.get("backend")
        if backend is not None and not isinstance(backend, str):
            raise ValueError("'backend' must be a string if present")

        plugin = self._by_handler.get((kind, backend))
        if plugin is None:
            plugin = self._by_handler.get((kind, None))
        if plugin is None:
            known = ", ".join(self.registered_handlers) if self._by_handler else "(none)"
            raise ValueError(f"Unknown command handler: {kind}/{backend or '<default>'} (known: {known})")

        ok, reason = plugin.is_available(ctx)
        if not ok:
            msg = reason or "plugin is not available in this environment"
            raise RuntimeError(f"Command handler {kind}/{backend or '<default>'} is unavailable: {msg}")

        return plugin.from_dict(raw, ctx)


