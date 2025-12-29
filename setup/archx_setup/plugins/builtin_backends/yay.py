from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass

from archx_setup.util import CommandRunner


@dataclass(frozen=True)
class YayBackend:
    runner: CommandRunner
    logger: logging.Logger

    def is_installed(self, package: str) -> bool:
        # Installed packages (including AUR-built ones) are still tracked by pacman.
        res = self.runner.run(["pacman", "-Qi", package], sudo=False, check=False)
        return res.returncode == 0

    def install(self, package: str) -> None:
        # In dry-run, we don't require yay to be present.
        if not self.runner.dry_run and shutil.which("yay") is None:
            raise RuntimeError(
                "yay backend requested but `yay` is not installed or not on PATH. "
                "Run the essentials step that installs yay, or install yay manually."
            )

        self.runner.run(
            ["yay", "-S", "--noconfirm", "--needed", package],
            sudo=False,
            check=True,
        )



