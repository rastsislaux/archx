from __future__ import annotations

import os
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


def xdg_config_home() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))


def expand_path(s: str) -> Path:
    # Expand ~ and $VARS
    return Path(os.path.expandvars(os.path.expanduser(s)))


def repo_root_from_setup_dir(setup_dir: Path) -> Path:
    # repo_root/setup/...
    return setup_dir.parent


def sh_join(args: Sequence[str]) -> str:
    return shlex.join(list(args))


def can_write_path(p: Path) -> bool:
    parent = p if p.is_dir() else p.parent
    try:
        return os.access(parent, os.W_OK)
    except OSError:
        return False


@dataclass(frozen=True)
class RunResult:
    args: list[str]
    returncode: int
    stdout: str
    stderr: str


class CommandRunner:
    def __init__(self, *, dry_run: bool, logger) -> None:
        self._dry_run = dry_run
        self._logger = logger

    def run(
        self,
        args: Iterable[str],
        *,
        sudo: bool = False,
        check: bool = False,
        capture: bool = True,
    ) -> RunResult:
        argv = list(args)
        if sudo:
            argv = ["sudo", *argv]

        # Keep low-level process logs at DEBUG so high-level output can stay
        # "one log line per declarative command".
        self._logger.debug("RUN %s", sh_join(argv))
        if self._dry_run:
            return RunResult(args=argv, returncode=0, stdout="", stderr="")

        cp = subprocess.run(
            argv,
            text=True,
            capture_output=capture,
            check=False,  # we handle below to include logs
        )
        if check and cp.returncode != 0:
            raise RuntimeError(
                f"Command failed ({cp.returncode}): {sh_join(argv)}\n{cp.stderr}"
            )
        return RunResult(
            args=argv,
            returncode=cp.returncode,
            stdout=cp.stdout or "",
            stderr=cp.stderr or "",
        )


