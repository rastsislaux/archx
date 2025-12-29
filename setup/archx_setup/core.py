from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

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

    return Context(
        repo_root=repo_root,
        logger=logger,
        runner=runner,
        decisions=decisions,
        options=options,
    )


