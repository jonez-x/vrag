"""Eval harness: Recall@k and MRR@10 on a jsonl split."""

from __future__ import annotations

import json
import time
from pathlib import Path

from .engine import Engine


def recall_at_k(ranked: list[str], relevant: list[str], k: int) -> float:
    return len(set(ranked[:k]) & set(relevant)) / len(relevant)


def mrr_at_k(ranked: list[str], relevant: list[str], k: int = 10) -> float:
    for i, p in enumerate(ranked[:k], 1):
        if p in relevant:
            return 1.0 / i
    return 0.0


def load_split(path: str | Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def run_eval(engine: Engine, split_path: str | Path, k: int = 5) -> dict:
    items = load_split(split_path)
    per_query, t0 = [], time.perf_counter()
    for it in items:
        ranked = [h.note_path for h in engine.search(it["query"], k=10)]
        per_query.append({
            "id": it["id"],
            "query": it["query"],
            "relevant": it["relevant"],
            "retrieved": ranked[:k],
            "recall": recall_at_k(ranked, it["relevant"], k),
            "rr": mrr_at_k(ranked, it["relevant"]),
        })
    n = len(per_query) or 1
    return {
        "split": Path(split_path).stem,
        "n": len(per_query),
        f"recall@{k}": round(sum(q["recall"] for q in per_query) / n, 4),
        "mrr@10": round(sum(q["rr"] for q in per_query) / n, 4),
        "latency_ms": round((time.perf_counter() - t0) * 1000 / n, 2),
        "failures": [q for q in per_query if q["recall"] < 1.0],
    }
