from __future__ import annotations

import argparse
import logging
from pathlib import Path

from archx_setup.config_loader import load_config_file
from archx_setup.core import CommandFactory, Options, build_context
from archx_setup.util import xdg_config_home


def _discover_json_files(config_dir: Path) -> list[Path]:
    files = [p for p in config_dir.rglob("*.json") if p.is_file()]
    files.sort(key=lambda p: str(p))
    return files


def _setup_logger(verbose: bool) -> logging.Logger:
    logger = logging.getLogger("archx-setup")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.handlers[:] = [handler]
    logger.propagate = False
    return logger


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="archx-setup")
    parser.add_argument(
        "--config-dir",
        type=Path,
        required=True,
        help="Directory containing *.json config files (loaded recursively).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log actions but do not change the system.",
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Never prompt. If a symlink conflicts, default behavior depends on --symlink-conflict (default: skip).",
    )
    parser.add_argument(
        "--symlink-conflict",
        choices=["ask", "replace", "skip"],
        default="ask",
        help="What to do when a symlink target already exists and isn't correct.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Verbose logs.",
    )
    args = parser.parse_args(argv)

    logger = _setup_logger(args.verbose)

    config_dir: Path = args.config_dir
    if not config_dir.exists():
        logger.error("Config dir not found: %s", config_dir)
        return 2

    decisions_path = xdg_config_home() / "archx-setup" / "decisions.json"
    options = Options(
        dry_run=bool(args.dry_run),
        non_interactive=bool(args.non_interactive),
        symlink_conflict=("skip" if args.non_interactive and args.symlink_conflict == "ask" else args.symlink_conflict),
    )

    setup_dir = Path(__file__).resolve().parents[1]  # .../setup
    ctx = build_context(
        setup_dir=setup_dir,
        decisions_path=decisions_path,
        options=options,
        logger=logger,
    )

    files = _discover_json_files(config_dir)
    if not files:
        logger.warning("No *.json config files found under %s", config_dir)
        return 0

    factory = CommandFactory()
    for path in files:
        rel = path.relative_to(config_dir)
        loaded = load_config_file(path)
        desc = loaded.description or rel.as_posix()
        ver = loaded.version if loaded.version is not None else "?"
        logger.info("==> %s v%s @ %s", desc, ver, rel.as_posix())
        for i, raw in enumerate(loaded.commands, start=1):
            try:
                cmd = factory.from_dict(raw)
            except Exception as e:
                raise RuntimeError(f"Invalid command in {path} (index {i}): {e}") from e
            msg = cmd.apply(ctx)
            logger.info("%s", msg)

    logger.info("Done.")
    return 0


