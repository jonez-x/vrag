"""Local TUI state under ``.vrag/`` (gitignored): eval score history + vault list.

Nothing here is ever written to ``eval/`` or ``vaults/``.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from ..config import Config

STATE_DIR = Path(".vrag")
STAGES = ("bm25", "dense", "graph", "rerank")


@dataclass
class EvalRecord:
    timestamp: str
    split: str
    n: int
    recall_at_5: float
    mrr_at_10: float
    latency_ms: float
    stages: list[str] = field(default_factory=list)
    commit: str = ""

    @classmethod
    def from_result(cls, result: dict, cfg: Config, commit: str = "") -> EvalRecord:
        return cls(
            timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            split=result["split"],
            n=result["n"],
            recall_at_5=result["recall@5"],
            mrr_at_10=result["mrr@10"],
            latency_ms=result["latency_ms"],
            stages=enabled_stages(cfg),
            commit=commit,
        )


def enabled_stages(cfg: Config) -> list[str]:
    return [s for s in STAGES if getattr(getattr(cfg, s, None), "enabled", False)]


def git_commit(cwd: str | Path = ".") -> str:
    """Short HEAD hash (+ '*' when dirty), or '' outside a git repo."""
    try:
        run = lambda *a: subprocess.run(  # noqa: E731
            ["git", *a], cwd=cwd, capture_output=True, text=True, timeout=2, check=True
        ).stdout.strip()
        sha = run("rev-parse", "--short", "HEAD")
        return sha + ("*" if run("status", "--porcelain", "--untracked-files=no") else "")
    except (OSError, subprocess.SubprocessError):
        return ""


class History:
    """Append-only JSONL of eval runs at ``<state_dir>/eval_history.jsonl``."""

    def __init__(self, state_dir: str | Path = STATE_DIR):
        self.path = Path(state_dir) / "eval_history.jsonl"

    def load(self) -> list[EvalRecord]:
        if not self.path.exists():
            return []
        records = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                records.append(EvalRecord(**json.loads(line)))
            except (json.JSONDecodeError, TypeError):
                continue  # skip corrupt/foreign lines instead of crashing the UI
        return records

    def append(self, record: EvalRecord) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")


class VaultRegistry:
    """Known vaults + the active one, at ``<state_dir>/vaults.json``."""

    def __init__(self, state_dir: str | Path = STATE_DIR, fallback: str | None = None):
        """``fallback`` is registered (not saved) when no vaults are known yet."""
        self.path = Path(state_dir) / "vaults.json"
        self.vaults: list[str] = []
        self.active: str | None = None
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                self.vaults = [str(v) for v in data.get("vaults", [])]
                self.active = data.get("active")
            except (json.JSONDecodeError, AttributeError):
                pass
        if fallback and not self.vaults:
            self.vaults.append(fallback)
        if self.active not in self.vaults:
            self.active = self.vaults[0] if self.vaults else None

    def add(self, path: str, save: bool = True) -> None:
        if path not in self.vaults:
            self.vaults.append(path)
        if save:
            self.save()

    def remove(self, path: str) -> None:
        if path in self.vaults:
            self.vaults.remove(path)
        if self.active == path:
            self.active = self.vaults[0] if self.vaults else None
        self.save()

    def activate(self, path: str) -> None:
        self.add(path, save=False)
        self.active = path
        self.save()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps({"vaults": self.vaults, "active": self.active}, indent=2), encoding="utf-8"
        )
