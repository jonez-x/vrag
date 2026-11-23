"""Cross-encoder reranking of the first-stage top notes (optional `rerank` extra)."""

from __future__ import annotations

from typing import Protocol

from ..config import RerankConfig


class RerankerUnavailable(RuntimeError):
    """Raised when the cross-encoder (extra or model) cannot be loaded."""


class CrossEncoder(Protocol):
    def score(self, query: str, passages: list[str]) -> list[float]: ...


class SentenceTransformersCrossEncoder:
    """Wraps `sentence_transformers.CrossEncoder`; imported lazily so the extra stays optional."""

    def __init__(self, model: str):
        try:
            from sentence_transformers import CrossEncoder as _CE
        except ImportError as e:
            raise RerankerUnavailable("the `rerank` extra is not installed — try `uv sync --extra rerank`") from e
        try:
            self._model = _CE(model)
        except Exception as e:  # download failure, unknown model id, …
            raise RerankerUnavailable(f"could not load reranker model '{model}' ({e})") from e

    def score(self, query: str, passages: list[str]) -> list[float]:
        if not passages:
            return []
        return [float(s) for s in self._model.predict([(query, p) for p in passages])]


class Reranker:
    def __init__(self, cfg: RerankConfig, encoder: CrossEncoder | None = None):
        self.cfg = cfg
        self.model = cfg.model
        self.encoder = encoder or SentenceTransformersCrossEncoder(cfg.model)

    def rerank(self, query: str, candidates: list[str], passages: dict[str, list[str]]) -> dict[str, float]:
        """Score the first `top_n` candidate notes by their best-scoring passage.

        `candidates` are note paths in first-stage order; `passages` maps a note to its
        chunk texts. Returns note → cross-encoder score (notes past `top_n` are absent).
        """
        pool = [p for p in candidates[: self.cfg.top_n] if passages.get(p)]
        pairs = [(p, t) for p in pool for t in passages[p]]
        if not pairs:
            return {}
        scores = self.encoder.score(query, [t for _, t in pairs])
        out: dict[str, float] = {}
        for (p, _), s in zip(pairs, scores):
            out[p] = max(out.get(p, s), s)
        return out
