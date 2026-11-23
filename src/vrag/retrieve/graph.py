"""Wikilink neighbour boost: notes linked to strong hits move up."""

from __future__ import annotations

from ..vault import Note, resolve_note


class LinkGraph:
    """Undirected note graph from [[wikilinks]] (outgoing links and backlinks alike)."""

    def __init__(self, notes: dict[str, Note]):
        self.neighbours: dict[str, set[str]] = {p: set() for p in notes}
        for n in notes.values():
            for ref in n.links:
                t = resolve_note(notes, ref)
                if t is not None and t.path != n.path:
                    self.neighbours[n.path].add(t.path)
                    self.neighbours[t.path].add(n.path)

    def boosts(self, scores: dict[str, float], boost: float) -> dict[str, float]:
        """Per-note bonus: `boost` × the best max-normalised score among its linked notes.

        `scores` are first-stage note scores (any scale). Notes the first stage missed
        can still receive a bonus, so a strong hit can pull in its neighbours.
        """
        norm = normalise(scores)
        if boost == 0:
            return {}
        out: dict[str, float] = {}
        for path, nbrs in self.neighbours.items():
            best = max((norm.get(m, 0.0) for m in nbrs), default=0.0)
            if best > 0:
                out[path] = boost * best
        return out


def normalise(scores: dict[str, float]) -> dict[str, float]:
    """Min-max to (0, 1]: the weakest retrieved note maps to a small positive value, not 0.

    Min-max rather than max-only, because RRF scores are compressed near the top
    (1/61, 1/62, …) and would otherwise all normalise to ≈ 1.
    """
    if not scores:
        return {}
    hi, lo = max(scores.values()), min(scores.values())
    span = hi - lo
    n = len(scores)
    floor = 1.0 / (n + 1)  # keep every retrieved note above "not retrieved"
    if span <= 0:
        return {p: 1.0 for p in scores}
    return {p: floor + (1 - floor) * (s - lo) / span for p, s in scores.items()}


def apply_boost(scores: dict[str, float], bonus: dict[str, float]) -> dict[str, float]:
    """Normalise first-stage scores and add the graph bonus."""
    combined = normalise(scores)
    for p, b in bonus.items():
        combined[p] = combined.get(p, 0.0) + b
    return combined
