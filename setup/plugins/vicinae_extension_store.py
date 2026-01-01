from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from archx_setup.plugins.api import Command, CommandHandler, Context


def _extensions_root() -> Path:
    # Vicinae stores extensions here by default.
    return Path.home() / ".local" / "share" / "vicinae" / "extensions"


def _is_installed(name: str) -> bool:
    return (_extensions_root() / name).exists()


class VicinaeExtensionStoreCommand:
    def __init__(
        self,
        *,
        names: list[str],
        repo_url: str,
        clone_depth: int,
    ) -> None:
        self.names = names
        self.repo_url = repo_url
        self.clone_depth = clone_depth

    def apply(self, ctx: Context) -> str:
        missing = [n for n in self.names if not _is_installed(n)]

        if not missing:
            return f"Vicinae extensions already installed: {', '.join(self.names)}."

        if ctx.options.dry_run:
            return f"Would install Vicinae extensions: {', '.join(missing)}."

        # Clone once, build missing only.
        with tempfile.TemporaryDirectory(prefix="archx-vicinae-ext-") as tmp:
            tmp_path = Path(tmp)
            clone_cmd = [
                "git",
                "clone",
                "--depth",
                str(self.clone_depth),
                self.repo_url,
                str(tmp_path / "extensions"),
            ]
            ctx.runner.run(clone_cmd, check=True, capture=True)

            base = tmp_path / "extensions" / "extensions"
            if not base.exists():
                raise RuntimeError(f"Unexpected repo layout; missing directory: {base}")

            # Ensure destination root exists (some build scripts may assume it).
            _extensions_root().mkdir(parents=True, exist_ok=True)

            for name in missing:
                ext_dir = base / name
                if not ext_dir.exists():
                    raise RuntimeError(
                        f"Extension {name!r} not found in store repo under {ext_dir}"
                    )
                # Run install/build in the extension directory.
                ctx.runner.run(
                    ["npm", "install"],
                    check=True,
                    capture=True,
                    cwd=ext_dir,
                )
                ctx.runner.run(
                    ["npm", "run", "build"],
                    check=True,
                    capture=True,
                    cwd=ext_dir,
                )

        # Re-check: best-effort confirmation
        still_missing = [n for n in missing if not _is_installed(n)]
        if still_missing:
            return (
                "Built Vicinae extensions, but they are still missing on disk: "
                + ", ".join(still_missing)
                + "."
            )
        return f"Installed Vicinae extensions: {', '.join(missing)}."


@dataclass(frozen=True)
class VicinaeExtensionStorePlugin:
    name: str = "archx.vicinae-extension-store.default"

    def handlers(self) -> Sequence[CommandHandler]:
        return (CommandHandler(kind="vicinae-extension-store", backend=None),)

    def is_available(self, ctx: Context) -> tuple[bool, str | None]:
        if ctx.runner.dry_run:
            return True, None
        if shutil.which("git") is None:
            return False, "`git` not found on PATH"
        if shutil.which("npm") is None:
            return False, "`npm` not found on PATH"
        return True, None

    def from_dict(self, raw: dict[str, Any], ctx: Context) -> Command:
        names = raw.get("names") or raw.get("extensions")
        if isinstance(names, str) and names:
            parsed = [names]
        elif isinstance(names, list) and all(isinstance(x, str) and x for x in names):
            parsed = list(names)
        else:
            raise ValueError("vicinae-extension-store requires 'names' (string or list of strings)")

        # De-dupe while preserving order
        seen: set[str] = set()
        uniq: list[str] = []
        for n in parsed:
            if n in seen:
                continue
            seen.add(n)
            uniq.append(n)

        repo_url = raw.get("repo_url") or raw.get("url") or "https://github.com/vicinaehq/extensions"
        if not isinstance(repo_url, str) or not repo_url:
            raise ValueError("'repo_url' must be a non-empty string if present")

        clone_depth = raw.get("clone_depth", 1)
        if not isinstance(clone_depth, int) or clone_depth < 1:
            raise ValueError("'clone_depth' must be an integer >= 1 if present")

        return VicinaeExtensionStoreCommand(
            names=uniq,
            repo_url=repo_url,
            clone_depth=clone_depth,
        )


PLUGIN = VicinaeExtensionStorePlugin()


