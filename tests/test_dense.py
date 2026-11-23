import json
import urllib.error
from pathlib import Path

import pytest

from vrag.config import Config, DenseConfig
from vrag.engine import Engine
from vrag.retrieve import dense
from vrag.retrieve.dense import DenseIndex, EmbedderUnavailable, OllamaEmbedder, VectorStore
from vrag.retrieve.fusion import best_per_group, rrf

ROOT = Path(__file__).resolve().parents[1]
VOCAB = ["sauerteig", "roggen", "anstellgut", "python", "docker", "garten"]


class FakeEmbedder:
    """Deterministic bag-of-keywords vectors; counts calls so caching is testable."""

    model = "fake"

    def __init__(self):
        self.calls: list[list[str]] = []

    def embed(self, texts):
        self.calls.append(texts)
        return [[float(t.lower().count(w)) + 0.01 for w in VOCAB] for t in texts]


class DeadEmbedder:
    model = "dead"

    def embed(self, texts):
        raise EmbedderUnavailable("Ollama not reachable")


def _cfg(tmp_path, bm25=True) -> Config:
    cfg = Config()
    cfg.bm25.enabled = bm25
    cfg.dense = DenseConfig(enabled=True, cache_dir=str(tmp_path))
    return cfg


def test_rrf_rewards_agreement():
    fused = rrf([["a", "b", "c"], ["b", "a", "d"]], k=60)
    assert fused["a"] == fused["b"] == pytest.approx(1 / 61 + 1 / 62)
    assert fused["a"] > fused["c"] and fused["c"] == fused["d"]


def test_rrf_weights_break_ties_toward_heavier_ranking():
    fused = rrf([["a", "b"], ["b", "a"]], k=60, weights=[1.0, 1.2])
    assert fused["b"] > fused["a"]
    assert fused["b"] == pytest.approx(1 / 62 + 1.2 / 61)


def test_best_per_group_dedups_and_skips_zero():
    scores = [0.2, 0.9, 0.5, 0.0]
    groups = ["x", "y", "x", "z"]
    assert best_per_group(scores, groups) == [("y", 1), ("x", 2)]


@pytest.mark.parametrize("has_vec", [True, False])
def test_vector_store_similarity(has_vec):
    store = VectorStore(":memory:")
    store.has_vec = store.has_vec and has_vec  # also exercise the pure-Python fallback
    store.put_many("m", {"a": [1.0, 0.0], "b": [0.0, 1.0], "c": [1.0, 1.0]})
    sims = store.similarities("m", [1.0, 0.0], ["a", "b", "c"])
    assert sims["a"] == pytest.approx(1.0)
    assert sims["b"] == pytest.approx(0.0, abs=1e-6)
    assert sims["c"] == pytest.approx(0.7071, abs=1e-3)
    assert store.get_many("other-model", ["a"]) == {}


def test_dense_index_caches_embeddings(tmp_path):
    docs = ["Sauerteig mit Roggen", "Python und Docker"]
    cfg = DenseConfig(enabled=True, cache_dir=str(tmp_path))
    emb = FakeEmbedder()
    DenseIndex(docs, cfg, emb)
    assert sum(len(c) for c in emb.calls) == 2
    idx = DenseIndex(docs + ["Garten"], cfg, emb)  # new process, same cache file
    assert emb.calls[-1] == ["Garten"]  # only the new chunk is embedded
    scores = idx.scores("docker")
    assert max(range(3), key=scores.__getitem__) == 1


def test_hybrid_search_has_stage_breakdown(tmp_path):
    eng = Engine(_cfg(tmp_path), embedder=FakeEmbedder()).index(ROOT / "vaults/sample")
    hits = eng.search("Anstellgut mit Roggenvollkornmehl", k=3)
    assert hits[0].note_path == "Kochen/Sauerteig ansetzen.md"
    assert {"bm25", "dense", "rrf"} <= hits[0].stage_scores.keys()
    assert hits[0].score == hits[0].stage_scores["rrf"]
    assert len({h.note_path for h in hits}) == len(hits)


def test_dense_only_search(tmp_path):
    eng = Engine(_cfg(tmp_path, bm25=False), embedder=FakeEmbedder()).index(ROOT / "vaults/sample")
    hits = eng.search("anstellgut sauerteig", k=5)
    assert hits and set(hits[0].stage_scores) == {"dense"}
    assert len({h.note_path for h in hits}) == len(hits)


def test_falls_back_to_bm25_when_ollama_missing(tmp_path, capsys):
    eng = Engine(_cfg(tmp_path), embedder=DeadEmbedder()).index(ROOT / "vaults/sample")
    hits = eng.search("Anstellgut mit Roggenvollkornmehl", k=3)
    assert hits[0].note_path == "Kochen/Sauerteig ansetzen.md"
    assert set(hits[0].stage_scores) == {"bm25"}
    assert "falling back to BM25" in capsys.readouterr().err
    assert eng.warnings


def test_ollama_embedder_errors_are_clear(monkeypatch):
    def refuse(*a, **kw):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(dense.urllib.request, "urlopen", refuse)
    with pytest.raises(EmbedderUnavailable, match="ollama serve"):
        OllamaEmbedder("bge-m3", "http://127.0.0.1:9").embed(["x"])


def test_ollama_embedder_parses_response(monkeypatch):
    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps({"embeddings": [[0.1, 0.2]]}).encode()

    seen = {}

    def fake_urlopen(req, timeout):
        seen["body"] = json.loads(req.data)
        return Resp()

    monkeypatch.setattr(dense.urllib.request, "urlopen", fake_urlopen)
    assert OllamaEmbedder("bge-m3").embed(["hallo"]) == [[0.1, 0.2]]
    assert seen["body"] == {"model": "bge-m3", "input": ["hallo"]}
