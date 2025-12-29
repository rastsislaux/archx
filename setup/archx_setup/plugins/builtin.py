from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from archx_setup.plugins.builtin_backends.pacman import PacmanBackend
from archx_setup.plugins.builtin_backends.shell_bash import BashShellBackend
from archx_setup.plugins.builtin_backends.symlink_ln import LnSymlinkBackend, SymlinkConflictPolicy
from archx_setup.plugins.builtin_backends.systemctl import SystemctlBackend
from archx_setup.plugins.builtin_backends.yay import YayBackend
from archx_setup.core import Command, Context
from archx_setup.plugins.api import CommandHandler, CommandPlugin
from archx_setup.util import expand_path


class PacmanPackageCommand:
    def __init__(self, name: str) -> None:
        self.name = name

    def apply(self, ctx: Context) -> str:
        backend = PacmanBackend(runner=ctx.runner, logger=ctx.logger)
        if backend.is_installed(self.name):
            pretty = self.name[:1].upper() + self.name[1:]
            return f"{pretty} package is already installed."
        backend.install(self.name)
        pretty = self.name[:1].upper() + self.name[1:]
        return f"Installed {pretty} package."


@dataclass(frozen=True)
class PacmanPackagePlugin:
    name: str = "builtin.package.pacman"

    def handlers(self) -> Sequence[CommandHandler]:
        return (CommandHandler(kind="package", backend=None), CommandHandler(kind="package", backend="pacman"))

    def is_available(self, ctx: Context) -> tuple[bool, str | None]:
        if ctx.runner.dry_run:
            return True, None
        if shutil.which("pacman") is None:
            return False, "`pacman` not found on PATH"
        return True, None

    def from_dict(self, raw: dict[str, Any], ctx: Context) -> Command:
        name = raw.get("name") or raw.get("package")
        if not isinstance(name, str) or not name:
            raise ValueError("package command requires 'name'")
        return PacmanPackageCommand(name)


class YayPackageCommand:
    def __init__(self, name: str) -> None:
        self.name = name

    def apply(self, ctx: Context) -> str:
        backend = YayBackend(runner=ctx.runner, logger=ctx.logger)
        if backend.is_installed(self.name):
            pretty = self.name[:1].upper() + self.name[1:]
            return f"{pretty} package is already installed."
        backend.install(self.name)
        pretty = self.name[:1].upper() + self.name[1:]
        return f"Installed {pretty} package."


@dataclass(frozen=True)
class YayPackagePlugin:
    name: str = "builtin.package.yay"

    def handlers(self) -> Sequence[CommandHandler]:
        return (CommandHandler(kind="package", backend="yay"),)

    def is_available(self, ctx: Context) -> tuple[bool, str | None]:
        if ctx.runner.dry_run:
            return True, None
        # yay backend uses pacman for is_installed checks too.
        if shutil.which("pacman") is None:
            return False, "`pacman` not found on PATH (required by yay plugin)"
        if shutil.which("yay") is None:
            return False, "`yay` not found on PATH"
        return True, None

    def from_dict(self, raw: dict[str, Any], ctx: Context) -> Command:
        name = raw.get("name") or raw.get("package")
        if not isinstance(name, str) or not name:
            raise ValueError("package command requires 'name'")
        return YayPackageCommand(name)


class SystemctlServiceCommand:
    def __init__(self, name: str, *, enable_now: bool) -> None:
        self.name = name
        self.enable_now = enable_now

    def apply(self, ctx: Context) -> str:
        backend = SystemctlBackend(runner=ctx.runner, logger=ctx.logger)
        if backend.is_enabled(self.name):
            return f"{self.name} is already enabled."
        backend.enable(self.name, now=self.enable_now)
        return f"Enabled {self.name}."


@dataclass(frozen=True)
class SystemctlServicePlugin:
    name: str = "builtin.service.systemctl"

    def handlers(self) -> Sequence[CommandHandler]:
        return (CommandHandler(kind="service", backend=None), CommandHandler(kind="service", backend="systemctl"))

    def is_available(self, ctx: Context) -> tuple[bool, str | None]:
        if ctx.runner.dry_run:
            return True, None
        if shutil.which("systemctl") is None:
            return False, "`systemctl` not found on PATH"
        return True, None

    def from_dict(self, raw: dict[str, Any], ctx: Context) -> Command:
        name = raw.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError("service command requires 'name'")
        enable_now = bool(raw.get("enable_now", False))
        return SystemctlServiceCommand(name, enable_now=enable_now)


class LnSymlinkCommand:
    def __init__(self, source: str, target: str) -> None:
        self.source = source
        self.target = target

    def apply(self, ctx: Context) -> str:
        # Resolve source relative to repo root if it's not absolute-ish.
        src = self.source
        if not Path(src).is_absolute() and not src.startswith("~"):
            src = str(ctx.repo_root / src)

        backend = LnSymlinkBackend(
            runner=ctx.runner,
            logger=ctx.logger,
            decisions=ctx.decisions,
            non_interactive=ctx.options.non_interactive,
            conflict_policy=SymlinkConflictPolicy(mode=ctx.options.symlink_conflict),
        )
        return backend.ensure_symlink(source=src, target=self.target)


@dataclass(frozen=True)
class LnSymlinkPlugin:
    name: str = "builtin.symlink.ln"

    def handlers(self) -> Sequence[CommandHandler]:
        return (CommandHandler(kind="symlink", backend=None), CommandHandler(kind="symlink", backend="ln"))

    def is_available(self, ctx: Context) -> tuple[bool, str | None]:
        if ctx.runner.dry_run:
            return True, None
        if shutil.which("ln") is None:
            return False, "`ln` not found on PATH"
        return True, None

    def from_dict(self, raw: dict[str, Any], ctx: Context) -> Command:
        source = raw.get("source") or raw.get("real")
        target = raw.get("target") or raw.get("pointer")
        if not isinstance(source, str) or not isinstance(target, str):
            raise ValueError("symlink command requires 'source' and 'target'")
        return LnSymlinkCommand(source, target)


class BashShellCommand:
    def __init__(
        self,
        script: list[str],
        *,
        cwd: str | None,
        sudo: bool,
        stdout: bool,
        stderr: bool,
    ) -> None:
        self.script = script
        self.cwd = cwd
        self.sudo = sudo
        self.stdout = stdout
        self.stderr = stderr

    def apply(self, ctx: Context) -> str:
        backend = BashShellBackend(runner=ctx.runner, logger=ctx.logger)

        cwd_path = Path.home()
        if self.cwd is not None:
            cwd_path = expand_path(self.cwd)

        if ctx.options.dry_run:
            return f"Would run shell script ({len(self.script)} lines)."

        show_output = bool(self.stdout or self.stderr)
        backend.run_script(
            self.script,
            cwd=cwd_path,
            sudo=self.sudo,
            show_output=show_output,
        )
        return f"Ran shell script ({len(self.script)} lines)."


@dataclass(frozen=True)
class BashShellPlugin:
    name: str = "builtin.shell.bash"

    def handlers(self) -> Sequence[CommandHandler]:
        return (CommandHandler(kind="shell", backend=None), CommandHandler(kind="shell", backend="bash"))

    def is_available(self, ctx: Context) -> tuple[bool, str | None]:
        if ctx.runner.dry_run:
            return True, None
        if shutil.which("bash") is None:
            return False, "`bash` not found on PATH"
        return True, None

    def from_dict(self, raw: dict[str, Any], ctx: Context) -> Command:
        script = raw.get("script")
        if isinstance(script, str):
            lines = [script]
        elif isinstance(script, list) and all(isinstance(x, str) for x in script):
            lines = list(script)
        else:
            raise ValueError("shell command requires 'script' (string or list of strings)")

        cwd = raw.get("cwd")
        if cwd is not None and not isinstance(cwd, str):
            raise ValueError("'cwd' must be a string if present")

        sudo = raw.get("sudo", False)
        if not isinstance(sudo, bool):
            raise ValueError("'sudo' must be a boolean if present")

        stdout = raw.get("stdout", False)
        if not isinstance(stdout, bool):
            raise ValueError("'stdout' must be a boolean if present")

        stderr = raw.get("stderr", False)
        if not isinstance(stderr, bool):
            raise ValueError("'stderr' must be a boolean if present")

        return BashShellCommand(
            lines,
            cwd=cwd,
            sudo=sudo,
            stdout=stdout,
            stderr=stderr,
        )


def builtin_plugins() -> list[CommandPlugin]:
    # Keep ordering stable for predictable behavior and logging.
    return [
        PacmanPackagePlugin(),
        YayPackagePlugin(),
        SystemctlServicePlugin(),
        LnSymlinkPlugin(),
        BashShellPlugin(),
    ]


