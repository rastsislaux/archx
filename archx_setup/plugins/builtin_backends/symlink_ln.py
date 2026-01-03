from __future__ import annotations

import logging
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from archx_setup.decisions import DecisionStore
from archx_setup.util import CommandRunner, can_write_path, expand_path


@dataclass(frozen=True)
class SymlinkConflictPolicy:
    mode: str  # "ask" | "replace" | "skip"


@dataclass(frozen=True)
class LnSymlinkBackend:
    runner: CommandRunner
    logger: logging.Logger
    decisions: DecisionStore
    non_interactive: bool
    conflict_policy: SymlinkConflictPolicy

    def _needs_sudo_for_target(self, target: Path) -> bool:
        return not can_write_path(target)

    def _ensure_target_parent_dir(self, target: Path) -> None:
        parent = target.parent
        if parent.exists():
            if not parent.is_dir():
                raise RuntimeError(f"Symlink target parent exists but is not a directory: {parent}")
            return

        sudo = self._needs_sudo_for_target(parent)
        if sudo:
            self.runner.run(["mkdir", "-p", str(parent)], sudo=True, check=True)
        else:
            parent.mkdir(parents=True, exist_ok=True)

    def _remove_target(self, target: Path, *, sudo: bool) -> None:
        # Prefer stdlib removal when possible; fall back to rm when permissions require sudo.
        if not sudo:
            if target.is_symlink() or target.is_file():
                target.unlink(missing_ok=True)
                return
            if target.is_dir():
                shutil.rmtree(target)
                return
        self.runner.run(["rm", "-rf", str(target)], sudo=True, check=True)

    def _abspath_no_resolve(self, p: Path) -> Path:
        # Normalize ".." etc but do NOT resolve symlinks.
        return Path(os.path.abspath(str(p)))

    def _symlink_points_to(self, tgt: Path) -> Path | None:
        # Returns the absolute (but non-resolved) path the symlink points to.
        try:
            raw = os.readlink(tgt)
        except OSError:
            return None
        link = Path(raw)
        if not link.is_absolute():
            link = tgt.parent / link
        return self._abspath_no_resolve(link)

    def _existing_state(self, tgt: Path) -> str:
        if tgt.is_symlink():
            try:
                raw = os.readlink(tgt)
            except OSError:
                raw = "<unreadable>"
            resolved = tgt.resolve(strict=False)
            return f"{tgt} -> {raw} (resolves to {resolved})"
        if tgt.is_dir():
            return f"{tgt} (directory)"
        if tgt.exists():
            return f"{tgt} (file)"
        return f"{tgt} (missing)"

    def _desired_state(self, tgt: Path, src: Path) -> str:
        return f"{tgt} -> {src} (resolves to {src.resolve()})"

    def ensure_symlink(self, *, source: str, target: str) -> str:
        src = expand_path(source)
        tgt = expand_path(target)

        if not src.exists():
            raise RuntimeError(f"Symlink source does not exist: {src}")

        desired_norm = self._abspath_no_resolve(src)
        desired_resolved = src.resolve(strict=False)

        if tgt.is_symlink():
            # First compare the raw symlink target (normalized but not resolved).
            current_link = self._symlink_points_to(tgt)
            if current_link is not None and current_link == desired_norm:
                return f"Symlink {tgt} already points to {src}."

            try:
                current_resolved = tgt.resolve(strict=False)
            except Exception:
                current_resolved = None
            if current_resolved == desired_resolved:
                return f"Symlink {tgt} already points to {src}."

        if not tgt.exists() and not tgt.is_symlink():
            self._ensure_target_parent_dir(tgt)
            sudo = self._needs_sudo_for_target(tgt)
            self.runner.run(["ln", "-sn", str(src), str(tgt)], sudo=sudo, check=True)
            return f"Created symlink {tgt} -> {src}."

        # Conflict: target exists (or wrong symlink)
        decision = self.decisions.get_symlink_decision(target=str(tgt))
        if decision and decision.action == "ignore":
            return f"Symlink {tgt} is ignored (saved decision)."

        existing_state = self._existing_state(tgt)
        desired_state = self._desired_state(tgt, src)

        mode = self.conflict_policy.mode
        if self.non_interactive and mode == "ask":
            mode = "skip"

        if mode == "skip":
            self.logger.warning("Symlink conflict.")
            self.logger.warning("Existing: %s", existing_state)
            self.logger.warning("Desired:  %s", desired_state)
            return f"Skipped symlink {tgt} (conflict)."

        if mode == "replace":
            self._ensure_target_parent_dir(tgt)
            sudo = self._needs_sudo_for_target(tgt)
            self._remove_target(tgt, sudo=sudo)
            self.runner.run(["ln", "-sn", str(src), str(tgt)], sudo=sudo, check=True)
            return f"Replaced symlink {tgt} -> {src}."

        # ask mode
        while True:
            self.logger.warning("Symlink conflict.")
            self.logger.warning("Existing: %s", existing_state)
            self.logger.warning("Desired:  %s", desired_state)
            choice = input(
                "Target exists. Choose: [r]eplace / [s]kip / [i]gnore always / [a]bort: "
            ).strip().lower()

            if choice in {"s", "skip"}:
                return f"Skipped symlink {tgt} (user chose skip)."
            if choice in {"i", "ignore"}:
                self.decisions.set_symlink_ignore(target=str(tgt))
                return f"Symlink {tgt} is ignored (saved decision)."
            if choice in {"r", "replace"}:
                self._ensure_target_parent_dir(tgt)
                sudo = self._needs_sudo_for_target(tgt)
                self._remove_target(tgt, sudo=sudo)
                self.runner.run(["ln", "-sn", str(src), str(tgt)], sudo=sudo, check=True)
                return f"Replaced symlink {tgt} -> {src}."
            if choice in {"a", "abort"}:
                raise RuntimeError(f"Aborted by user due to conflict at {tgt}")



