from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from archx_setup.util import CommandRunner


@dataclass(frozen=True)
class BashShellBackend:
    runner: CommandRunner
    logger: logging.Logger

    def run_script(
        self,
        lines: Sequence[str],
        *,
        cwd: Path | None = None,
        sudo: bool = False,
        env: Mapping[str, str] | None = None,
        show_output: bool = False,
    ) -> None:
        # Single bash session so stateful commands (e.g. `cd`) persist.
        script = "set -euo pipefail\n" + "\n".join(lines) + "\n"
        res = self.runner.run(
            ["bash", "-lc", script],
            sudo=sudo,
            check=True,
            capture=(not show_output),
            cwd=cwd,
            env=env,
        )
        if not show_output:
            if res.stdout.strip():
                self.logger.debug("shell stdout:\n%s", res.stdout.rstrip())
            if res.stderr.strip():
                self.logger.debug("shell stderr:\n%s", res.stderr.rstrip())



