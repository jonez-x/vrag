import builtins
from pathlib import Path

import pytest

from vrag.config import Config, RerankConfig
from vrag.engine import Engine
from vrag.retrieve import rerank
from vrag.retrieve.rerank import Reranker, RerankerUnavailable, SentenceTransformersCrossEncoder

ROOT = Path(__file__).resolve().parents[1]


class FakeCrossEncoder:
    """Scores a passage by how often it contains `favourite`; records every call."""

    def __init__(self, favourite: str):
        self.favourite = favourite
        self.calls: list[tuple[str, list[str]]] = []

    def score(self, query, passages):
        self.calls.append((query, passages))
        return [float(p.lower().count(self.favourite)) for p in passages]


def _write(tmp_path, **bodies):
    for t, b in bodies.items():
        (tmp_path / f"{t}.md").write_text(b, encoding="utf-8")
    return tmp_path


def _cfg(top_n=30) -> Config:
    return Config(rerank=RerankConfig(enabled=True, top_n=top_n))


def test_reranker_scores_note_by_best_passage_within_top_n():
    enc = FakeCrossEncoder("roggen")
    r = Reranker(RerankConfig(top_n=2), enc)
    out = r.rerank("q", ["A", "B", "C"], {"A": ["x", "roggen roggen"], "B": ["roggen"], "C": ["roggen" * 3]})
    assert out == {"A": 2.0, "B": 1.0}  # C is past top_n
    assert enc.calls == [("q", ["x", "roggen roggen", "roggen"])]  # one batched call


def test_reranker_skips_notes_without_passages_and_empty_pool():
    enc = FakeCrossEncoder("x")
    r = Reranker(RerankConfig(top_n=5), enc)
    assert r.rerank("q", ["A"], {"A": []}) == {}
    assert r.rerank("q", [], {}) == {}
    assert enc.calls == []


def test_engine_rerank_reorders_and_reports_stage_score(tmp_path):
    vault = _write(tmp_path, A="Brot Brot Brot", B="Brot Roggen", C="Garten")
    off = Engine().index(vault).search("Brot")
    assert [h.note_path for h in off] == ["A.md", "B.md"]
    assert all("rerank" not in h.stage_scores for h in off)

    hits = Engine(_cfg(), cross_encoder=FakeCrossEncoder("roggen")).index(vault).search("Brot")
    assert [h.note_path for h in hits] == ["B.md", "A.md"]
    assert hits[0].stage_scores["rerank"] == 1.0 and hits[0].score == 1.0
    assert "bm25" in hits[0].stage_scores  # first-stage scores stay for explainability


def test_engine_rerank_keeps_tail_in_first_stage_order(tmp_path):
    vault = _write(tmp_path, A="Brot Brot Brot Brot", B="Brot Brot Roggen", C="Brot Roggen Roggen Roggen")
    hits = Engine(_cfg(top_n=1), cross_encoder=FakeCrossEncoder("roggen")).index(vault).search("Brot")
    assert [h.note_path for h in hits][0] == "A.md"  # only A was reranked
    assert "rerank" in hits[0].stage_scores
    assert all("rerank" not in h.stage_scores for h in hits[1:])


def test_engine_reuses_loaded_model_across_reindex(tmp_path, monkeypatch):
    vault = _write(tmp_path, A="Brot")
    loads = []
    monkeypatch.setattr(rerank, "SentenceTransformersCrossEncoder", lambda m: loads.append(m) or FakeCrossEncoder("brot"))
    eng = Engine(_cfg())
    eng.index(vault)
    eng.index(vault)
    assert loads == ["BAAI/bge-reranker-v2-m3"]
    eng.config.rerank.enabled = False
    eng.index(vault)
    assert eng._reranker is None


def test_missing_extra_raises_clear_error(monkeypatch):
    real_import = builtins.__import__

    def fake_import(name, *a, **kw):
        if name.startswith("sentence_transformers"):
            raise ImportError("no module")
        return real_import(name, *a, **kw)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(RerankerUnavailable, match="uv sync --extra rerank"):
        SentenceTransformersCrossEncoder("BAAI/bge-reranker-v2-m3")


def test_engine_falls_back_without_extra(tmp_path, monkeypatch, capsys):
    def unavailable(model):
        raise RerankerUnavailable("the `rerank` extra is not installed")

    monkeypatch.setattr(rerank, "SentenceTransformersCrossEncoder", unavailable)
    vault = _write(tmp_path, A="Brot Brot", B="Brot Roggen")
    eng = Engine(_cfg()).index(vault)
    hits = eng.search("Brot")
    assert [h.note_path for h in hits] == ["A.md", "B.md"]
    assert all("rerank" not in h.stage_scores for h in hits)
    assert eng.warnings and "reranking disabled" in eng.warnings[0]
    assert "reranking disabled" in capsys.readouterr().err


def test_engine_rerank_on_sample_vault():
    cfg = Config.load(ROOT / "config.toml")
    cfg.rerank.enabled = True
    hits = Engine(cfg, cross_encoder=FakeCrossEncoder("sauerteig")).index(ROOT / "vaults/sample").search("Sauerteig")
    assert hits and "rerank" in hits[0].stage_scores
