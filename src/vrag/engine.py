"""Engine: the single public API used by CLI, TUI and MCP server."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .chunking import Chunk, chunk_note
from .config import Config
from .retrieve.bm25 import BM25Index
from .vault import Note, load_vault


@dataclass
class Hit:
    note_path: str
    heading: str
    snippet: str
    score: float
    stage_scores: dict[str, float] = field(default_factory=dict)  # per-stage breakdown

    @property
    def anchor(self) -> str:
        return f"{self.note_path}#{self.heading}" if self.heading else self.note_path


class Engine:
    def __init__(self, config: Config | None = None):
        self.config = config or Config()
        self.notes: dict[str, Note] = {}
        self.chunks: list[Chunk] = []
        self._bm25: BM25Index | None = None

    def index(self, vault: str | Path) -> Engine:
        notes = load_vault(vault)
        self.notes = {n.path: n for n in notes}
        self.chunks = [c for n in notes for c in chunk_note(n, self.config.chunking)]
        if self.config.bm25.enabled:
            self._bm25 = BM25Index([c.text for c in self.chunks], self.config.bm25)
        return self

    def search(self, query: str, k: int | None = None) -> list[Hit]:
        k = k or self.config.search.k
        if not self.chunks or self._bm25 is None:
            return []
        scores = self._bm25.scores(query)
        ranked = sorted(range(len(self.chunks)), key=lambda i: scores[i], reverse=True)

        hits: list[Hit] = []
        seen: set[str] = set()
        for i in ranked:
            if scores[i] <= 0:
                break
            c = self.chunks[i]
            if c.note_path in seen:  # note-level dedup: best chunk wins
                continue
            seen.add(c.note_path)
            hits.append(Hit(c.note_path, c.heading, _snippet(c.text), scores[i], {"bm25": scores[i]}))
            if len(hits) >= k:
                break
        return hits


def _snippet(text: str, n: int = 240) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= n else flat[: n - 1] + "…"
