from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence


class EchoCommand:
    def __init__(self, message: str) -> None:
        self.message = message

    def apply(self, ctx) -> str:
        # ctx is archx_setup.core.Context
        ctx.logger.info("%s", self.message)
        return f"Echoed: {self.message}"


@dataclass(frozen=True)
class EchoPlugin:
    name: str = "example.echo"

    def handlers(self):
        # kind="echo" with no backend selection
        from archx_setup.plugins.api import CommandHandler

        return (CommandHandler(kind="echo", backend=None),)

    def is_available(self, ctx) -> tuple[bool, str | None]:
        return True, None

    def from_dict(self, raw: dict[str, Any], ctx):
        msg = raw.get("message") or raw.get("msg")
        if not isinstance(msg, str) or not msg:
            raise ValueError("echo command requires 'message'")
        return EchoCommand(msg)


# The loader looks for PLUGIN (preferred) or get_plugin()
PLUGIN = EchoPlugin()


