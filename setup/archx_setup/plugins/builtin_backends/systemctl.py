from __future__ import annotations

import logging
from dataclasses import dataclass

from archx_setup.util import CommandRunner


@dataclass(frozen=True)
class SystemctlBackend:
    runner: CommandRunner
    logger: logging.Logger

    def is_enabled(self, unit: str) -> bool:
        # systemctl is-enabled exits 0 if enabled
        res = self.runner.run(["systemctl", "is-enabled", unit], sudo=False, check=False)
        return res.returncode == 0

    def enable(self, unit: str, *, now: bool = False) -> None:
        args = ["systemctl", "enable"]
        if now:
            args.append("--now")
        args.append(unit)
        self.runner.run(args, sudo=True, check=True)



