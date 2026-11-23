"""Dependency-free BM25 (Okapi)."""

from __future__ import annotations

import math
import re
from collections import Counter

from ..config import BM25Config

TOKEN_RE = re.compile(r"\w+", re.UNICODE)

# Small German function-word list (articles, pronouns, auxiliaries, question words, particles).
GERMAN_STOPWORDS = frozenset("""
aber alle allem allen aller alles als also am an ander andere anderem anderen anderer anderes
auch auf aus bei beim bin bis bist da damit dann das dass dein deine dem den denn der des dich
die dies diese diesem diesen dieser dieses dir doch dort du durch ein eine einem einen einer
eines er es etwas euch euer für gegen gewesen hab habe haben hat hatte hätte ich ihm ihn ihnen
ihr ihre im in ist ja jede jedem jeden jeder jedes kann kein keine können man manche mein meine
meinem meinen meiner mich mir mit muss müssen nach nicht nichts noch nun nur ob oder ohne sehr
sein seine sich sie sind so solche soll sollte sondern sonst um und uns unser unter vom von vor
war waren warum was weil welche welchem welchen welcher welches wenn wer werde werden wie wieder
will wir wird wo wollen zu zum zur über
""".split())


_UMLAUTS = str.maketrans({"ä": "a", "ö": "o", "ü": "u", "ß": "ss"})


def stem_german(token: str) -> str:
    """Light, CISTEM-style suffix stripping: folds umlauts, removes inflection endings."""
    t = token.translate(_UMLAUTS)
    while len(t) > 3:
        if len(t) > 5 and t[-2:] in ("em", "er", "nd"):
            t = t[:-2]
        elif t[-1] in "esnt" and not t[-2].isdigit():
            t = t[:-1]
        else:
            break
    return t


def tokenize(text: str, stemming: bool = False, stopwords: bool = False) -> list[str]:
    tokens = TOKEN_RE.findall(text.lower())
    if stopwords:
        tokens = [t for t in tokens if t not in GERMAN_STOPWORDS]
    if stemming:
        tokens = [stem_german(t) for t in tokens]
    return tokens


class BM25Index:
    def __init__(self, docs: list[str], cfg: BM25Config):
        self.cfg = cfg
        self.tfs = [Counter(self._tokenize(d)) for d in docs]
        self.lens = [sum(tf.values()) for tf in self.tfs]
        self.avgdl = (sum(self.lens) / len(self.lens)) if self.lens else 0.0
        df: Counter = Counter()
        for tf in self.tfs:
            df.update(tf.keys())
        n = len(docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def _tokenize(self, text: str) -> list[str]:
        return tokenize(text, self.cfg.stemming, self.cfg.stopwords)

    def scores(self, query: str) -> list[float]:
        k1, b = self.cfg.k1, self.cfg.b
        q = self._tokenize(query)
        out = []
        for tf, dl in zip(self.tfs, self.lens):
            s = 0.0
            for t in q:
                f = tf.get(t)
                if f:
                    s += self.idf[t] * f * (k1 + 1) / (f + k1 * (1 - b + b * dl / self.avgdl))
            out.append(s)
        return out
