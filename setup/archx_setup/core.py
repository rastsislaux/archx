from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from archx_setup.backends.pacman import PacmanBackend
from archx_setup.backends.symlink_ln import LnSymlinkBackend, SymlinkConflictPolicy
from archx_setup.backends.systemctl import SystemctlBackend
from archx_setup.decisions import DecisionStore
from archx_setup.util import CommandRunner, repo_root_from_setup_dir


class Command(Protocol):
    def apply(self, ctx: "Context") -> str: ...


@dataclass(frozen=True)
class Options:
    dry_run: bool
    non_interactive: bool
    symlink_conflict: str  # ask|replace|skip


@dataclass(frozen=True)
class Context:
    repo_root: Path
    logger: logging.Logger
    runner: CommandRunner
    decisions: DecisionStore
    options: Options
    backends: "Backends"


@dataclass(frozen=True)
class Backends:
    pacman: PacmanBackend
    systemctl: SystemctlBackend
    symlink: LnSymlinkBackend


class PackageCommand:
    def __init__(self, name: str, *, backend: str = "pacman") -> None:
        self.name = name
        self.backend = backend

    def apply(self, ctx: Context) -> str:
        if self.backend != "pacman":
            raise ValueError(f"Unknown package backend: {self.backend}")
        if ctx.backends.pacman.is_installed(self.name):
            pretty = self.name[:1].upper() + self.name[1:]
            return f"{pretty} package is already installed."
        ctx.backends.pacman.install(self.name)
        pretty = self.name[:1].upper() + self.name[1:]
        return f"Installed {pretty} package."


class ServiceCommand:
    def __init__(
        self, name: str, *, enable_now: bool = False, backend: str = "systemctl"
    ) -> None:
        self.name = name
        self.enable_now = enable_now
        self.backend = backend

    def apply(self, ctx: Context) -> str:
        if self.backend != "systemctl":
            raise ValueError(f"Unknown service backend: {self.backend}")
        if ctx.backends.systemctl.is_enabled(self.name):
            return f"{self.name} is already enabled."
        ctx.backends.systemctl.enable(self.name, now=self.enable_now)
        return f"Enabled {self.name}."


class SymlinkCommand:
    def __init__(self, source: str, target: str, *, backend: str = "ln") -> None:
        self.source = source
        self.target = target
        self.backend = backend

    def apply(self, ctx: Context) -> str:
        if self.backend != "ln":
            raise ValueError(f"Unknown symlink backend: {self.backend}")

        # Resolve source relative to repo root if it's not absolute-ish.
        src = self.source
        if not Path(src).is_absolute() and not src.startswith("~"):
            src = str(ctx.repo_root / src)

        return ctx.backends.symlink.ensure_symlink(source=src, target=self.target)


class CommandFactory:
    def from_dict(self, raw: dict[str, Any]) -> Command:
        kind = raw.get("kind") or raw.get("command")
        if not isinstance(kind, str):
            raise ValueError("Command missing 'kind'")

        backend = raw.get("backend")
        if backend is not None and not isinstance(backend, str):
            raise ValueError("'backend' must be a string if present")

        if kind == "package":
            name = raw.get("name") or raw.get("package")
            if not isinstance(name, str) or not name:
                raise ValueError("package command requires 'name'")
            return PackageCommand(name, backend=backend or "pacman")

        if kind == "service":
            name = raw.get("name")
            if not isinstance(name, str) or not name:
                raise ValueError("service command requires 'name'")
            enable_now = bool(raw.get("enable_now", False))
            return ServiceCommand(name, enable_now=enable_now, backend=backend or "systemctl")

        if kind == "symlink":
            source = raw.get("source") or raw.get("real")
            target = raw.get("target") or raw.get("pointer")
            if not isinstance(source, str) or not isinstance(target, str):
                raise ValueError("symlink command requires 'source' and 'target'")
            return SymlinkCommand(source, target, backend=backend or "ln")

        raise ValueError(f"Unknown command kind: {kind}")


def build_context(
    *,
    setup_dir: Path,
    decisions_path: Path,
    options: Options,
    logger: logging.Logger,
) -> Context:
    repo_root = repo_root_from_setup_dir(setup_dir)
    runner = CommandRunner(dry_run=options.dry_run, logger=logger)
    decisions = DecisionStore(decisions_path, logger)

    pacman = PacmanBackend(runner=runner, logger=logger)
    systemctl = SystemctlBackend(runner=runner, logger=logger)
    symlink = LnSymlinkBackend(
        runner=runner,
        logger=logger,
        decisions=decisions,
        non_interactive=options.non_interactive,
        conflict_policy=SymlinkConflictPolicy(mode=options.symlink_conflict),
    )

    return Context(
        repo_root=repo_root,
        logger=logger,
        runner=runner,
        decisions=decisions,
        options=options,
        backends=Backends(pacman=pacman, systemctl=systemctl, symlink=symlink),
    )


