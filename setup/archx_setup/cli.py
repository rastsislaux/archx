from __future__ import annotations

import argparse
import logging
from pathlib import Path

from archx_setup.config_loader import load_config_file
from archx_setup.core import Options, build_context
from archx_setup.plugins.factory import CommandFactory
from archx_setup.plugins.loader import load_plugins
from archx_setup.util import xdg_config_home


def _discover_config_files(config_dir: Path) -> list[Path]:
    exts = {".json", ".toml", ".yaml", ".yml"}
    files = [p for p in config_dir.rglob("*") if p.is_file() and p.suffix.lower() in exts]
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
        help="Directory containing config files (loaded recursively). Supported: *.json, *.toml, *.yaml, *.yml",
    )
    parser.add_argument(
        "--plugins-dir",
        action="append",
        type=Path,
        default=[],
        help="Directory containing additional command plugins (*.py). Can be specified multiple times. "
        "Also supports ARCHX_SETUP_PLUGINS_DIRS and ~/.config/archx-setup/plugins.",
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

    loaded_plugins = load_plugins(plugin_dirs=list(args.plugins_dir))
    for err in loaded_plugins.errors:
        logger.warning("%s", err)
    factory = CommandFactory(loaded_plugins.plugins)
    # Info-level visibility into plugin wiring (useful for debugging command resolution).
    plugins_sorted = sorted(
        loaded_plugins.plugins,
        key=lambda p: (getattr(p, "name", ""), p.__class__.__name__),
    )
    logger.info("Loaded %d command plugins:", len(plugins_sorted))
    for p in plugins_sorted:
        plugin_name = getattr(p, "name", "?")
        try:
            handlers = p.handlers()
        except Exception as e:
            logger.info("- %s: failed to list handlers: %s", plugin_name, e)
            continue

        pairs = ", ".join(f"{h.kind}/{h.backend}" for h in handlers)
        ok, reason = p.is_available(ctx)
        if ok:
            logger.info("- %s for %s", plugin_name, pairs)
        else:
            logger.info(
                "- %s for %s [UNAVAILABLE: %s]",
                plugin_name,
                pairs,
                reason or "unknown reason",
            )
    logger.debug("Registered command handlers: %s", ", ".join(factory.registered_handlers))

    files = _discover_config_files(config_dir)
    if not files:
        logger.warning("No config files found under %s (supported: *.json, *.toml, *.yaml, *.yml)", config_dir)
        return 0

    logger.info("")
    logger.info("=== Configuring ({} files) ===".format(len(files)))
    for path in files:
        rel = path.relative_to(config_dir)
        try:
            loaded = load_config_file(path)
        except Exception as e:
            logger.error("Failed to load config @ %s: %s", rel.as_posix(), e)
            return 2
        desc = loaded.description or rel.as_posix()
        ver = loaded.version if loaded.version is not None else "?"
        logger.info("# %s v%s @ %s", desc, ver, rel.as_posix())
        for i, raw in enumerate(loaded.commands, start=1):
            try:
                cmd = factory.from_dict(raw, ctx)
            except Exception as e:
                raise RuntimeError(f"Invalid command in {path} (index {i}): {e}") from e
            msg = cmd.apply(ctx)
            if i == len(loaded.commands):
                logger.info("└─ %s", msg)
            else:
                logger.info("├─ %s", msg)

    logger.info("Done.")
    return 0


