from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
import logging


@dataclass(frozen=True)
class SymlinkDecision:
    # For now we only persist "ignore always" decisions, keyed by target path.
    action: str  # "ignore"


class DecisionStore:
    def __init__(self, path: Path, logger) -> None:
        self._path = path
        self._logger: logging.Logger = logger
        self._data: dict[str, dict] = {}
        self._loaded = False

    def load(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        if not self._path.exists():
            self._data = {}
            return
        try:
            self._data = json.loads(self._path.read_text(encoding="utf-8")) or {}
        except Exception as e:
            self._logger.warning("Failed to read decisions file %s: %s", self._path, e)
            self._data = {}

    def get_symlink_decision(self, *, target: str) -> SymlinkDecision | None:
        self.load()
        raw = self._data.get("symlink", {}).get(target)
        if not isinstance(raw, dict):
            return None
        action = raw.get("action")
        if action == "ignore":
            return SymlinkDecision(action="ignore")
        return None

    def set_symlink_ignore(self, *, target: str) -> None:
        self.load()
        self._data.setdefault("symlink", {})[target] = {"action": "ignore"}
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._data, indent=2) + "\n", encoding="utf-8")
        self._logger.debug("Saved decision: ignore symlink at %s", target)


