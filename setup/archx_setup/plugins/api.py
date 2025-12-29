from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, Sequence

from archx_setup.core import Command, Context


@dataclass(frozen=True)
class CommandHandler:
    kind: str
    backend: str | None = None  # None => default handler when no backend is specified


class CommandPlugin(Protocol):
    """
    A command plugin converts a raw command object (dict) into an executable Command.

    A plugin must:
    - declare which command (kind, backend) pairs it handles
    - validate its command syntax
    - implement its execution via the returned Command
    """

    name: str

    def handlers(self) -> Sequence[CommandHandler]: ...

    def is_available(self, ctx: Context) -> tuple[bool, str | None]: ...

    def from_dict(self, raw: dict[str, Any], ctx: Context) -> Command: ...


