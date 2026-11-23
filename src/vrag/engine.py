"""Engine: the single public API used by CLI, TUI and MCP server."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

from .chunking import Chunk, chunk_note
from .config import Config
from .retrieve.bm25 import BM25Index
from .retrieve.dense import DenseIndex, Embedder, EmbedderUnavailable
from .retrieve.fusion import best_per_group, rrf
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
    def __init__(self, config: Config | None = None, embedder: Embedder | None = None):
        self.config = config or Config()
        self.embedder = embedder  # None → OllamaEmbedder from config.dense
        self.notes: dict[str, Note] = {}
        self.chunks: list[Chunk] = []
        self._bm25: BM25Index | None = None
        self._dense: DenseIndex | None = None
        self.warnings: list[str] = []

    def index(self, vault: str | Path) -> Engine:
        notes = load_vault(vault)
        self.notes = {n.path: n for n in notes}
        self.chunks = [c for n in notes for c in chunk_note(n, self.config.chunking)]
        texts = [c.text for c in self.chunks]
        if self.config.bm25.enabled:
            self._bm25 = BM25Index(texts, self.config.bm25)
        if self.config.dense.enabled:
            try:
                self._dense = DenseIndex(texts, self.config.dense, self.embedder)
            except EmbedderUnavailable as e:
                self._dense_unavailable(e)
        return self

    def _dense_unavailable(self, err: EmbedderUnavailable) -> None:
        self._dense = None
        fallback = "falling back to BM25" if self._bm25 else "no retrieval stage left"
        msg = f"vrag: dense retrieval disabled — {err}; {fallback}"
        self.warnings.append(msg)
        print(msg, file=sys.stderr)

    def _stage_scores(self, query: str) -> dict[str, list[float]]:
        stages: dict[str, list[float]] = {}
        if self._bm25 is not None:
            stages["bm25"] = self._bm25.scores(query)
        if self._dense is not None:
            try:
                stages["dense"] = self._dense.scores(query)
            except EmbedderUnavailable as e:  # Ollama went away mid-session
                self._dense_unavailable(e)
        return stages

    def search(self, query: str, k: int | None = None) -> list[Hit]:
        k = k or self.config.search.k
        if not self.chunks:
            return []
        stages = self._stage_scores(query)
        if not stages:
            return []
        # note-level dedup per stage: a note is represented by its best chunk
        paths = [c.note_path for c in self.chunks]
        per_stage = {name: best_per_group(s, paths) for name, s in stages.items()}
        if len(per_stage) == 1:
            ((name, ranking),) = per_stage.items()
            top = [(p, stages[name][i]) for p, i in ranking[:k]]
        else:  # fuse note rankings, so notes with many matching chunks get no extra weight
            fused = rrf([[p for p, _ in r] for r in per_stage.values()], self.config.fusion.rrf_k)
            top = sorted(fused.items(), key=lambda kv: kv[1], reverse=True)[:k]

        best = {name: {p: (rank, i) for rank, (p, i) in enumerate(r)} for name, r in per_stage.items()}
        hits: list[Hit] = []
        for path, score in top:
            found = {name: best[name][path] for name in best if path in best[name]}
            _, i = min(found.values())  # snippet from the stage that ranked this note highest
            c = self.chunks[i]
            breakdown = {name: stages[name][j] for name, (_, j) in found.items()}
            if len(per_stage) > 1:
                breakdown["rrf"] = score
            hits.append(Hit(c.note_path, c.heading, _snippet(c.text), score, breakdown))
        return hits


def _snippet(text: str, n: int = 240) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= n else flat[: n - 1] + "…"
