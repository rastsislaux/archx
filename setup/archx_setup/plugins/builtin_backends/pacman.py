from __future__ import annotations

import logging
from dataclasses import dataclass

from archx_setup.util import CommandRunner


@dataclass(frozen=True)
class PacmanBackend:
    runner: CommandRunner
    logger: logging.Logger

    def is_installed(self, package: str) -> bool:
        # pacman -Qi exits 0 if installed
        res = self.runner.run(["pacman", "-Qi", package], sudo=False, check=False)
        return res.returncode == 0

    def install(self, package: str) -> None:
        self.runner.run(
            ["pacman", "-S", "--noconfirm", "--needed", package],
            sudo=True,
            check=True,
        )



