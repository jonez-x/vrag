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
        top = max(scores.values(), default=0.0)
        if top <= 0 or boost == 0:
            return {}
        out: dict[str, float] = {}
        for path, nbrs in self.neighbours.items():
            best = max((scores.get(m, 0.0) for m in nbrs), default=0.0)
            if best > 0:
                out[path] = boost * best / top
        return out


def apply_boost(scores: dict[str, float], bonus: dict[str, float]) -> dict[str, float]:
    """Max-normalise first-stage scores and add the graph bonus."""
    top = max(scores.values(), default=0.0) or 1.0
    combined = {p: s / top for p, s in scores.items()}
    for p, b in bonus.items():
        combined[p] = combined.get(p, 0.0) + b
    return combined
