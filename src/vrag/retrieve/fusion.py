"""Rank fusion of per-stage scores."""

from __future__ import annotations

from collections.abc import Hashable, Sequence


def best_per_group(scores: Sequence[float], groups: Sequence[Hashable]) -> list[tuple[Hashable, int]]:
    """Groups (e.g. notes) ordered by their best-scoring member, as (group, member index).

    Members with score <= 0 count as not retrieved.
    """
    order = sorted((i for i, s in enumerate(scores) if s > 0), key=lambda i: scores[i], reverse=True)
    out, seen = [], set()
    for i in order:
        if groups[i] not in seen:
            seen.add(groups[i])
            out.append((groups[i], i))
    return out


def rrf(rankings: Sequence[Sequence[Hashable]], k: int = 60,
        weights: Sequence[float] | None = None) -> dict[Hashable, float]:
    """Reciprocal Rank Fusion: sum over rankings of weight / (k + rank), rank 1-based."""
    fused: dict[Hashable, float] = {}
    for ranking, w in zip(rankings, weights or [1.0] * len(rankings)):
        for r, key in enumerate(ranking, 1):
            fused[key] = fused.get(key, 0.0) + w / (k + r)
    return fused
