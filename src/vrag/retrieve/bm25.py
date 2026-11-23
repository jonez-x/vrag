"""Dependency-free BM25 (Okapi)."""

from __future__ import annotations

import math
import re
from collections import Counter

from ..config import BM25Config

TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def tokenize(text: str, stemming: bool = False) -> list[str]:
    tokens = TOKEN_RE.findall(text.lower())
    # stemming: hook for the loop — intentionally not implemented in the baseline
    return tokens


class BM25Index:
    def __init__(self, docs: list[str], cfg: BM25Config):
        self.cfg = cfg
        self.tfs = [Counter(tokenize(d, cfg.stemming)) for d in docs]
        self.lens = [sum(tf.values()) for tf in self.tfs]
        self.avgdl = (sum(self.lens) / len(self.lens)) if self.lens else 0.0
        df: Counter = Counter()
        for tf in self.tfs:
            df.update(tf.keys())
        n = len(docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def scores(self, query: str) -> list[float]:
        k1, b = self.cfg.k1, self.cfg.b
        q = tokenize(query, self.cfg.stemming)
        out = []
        for tf, dl in zip(self.tfs, self.lens):
            s = 0.0
            for t in q:
                f = tf.get(t)
                if f:
                    s += self.idf[t] * f * (k1 + 1) / (f + k1 * (1 - b + b * dl / self.avgdl))
            out.append(s)
        return out
