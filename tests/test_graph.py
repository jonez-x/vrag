from pathlib import Path

import pytest

from vrag.config import Config, GraphConfig
from vrag.engine import Engine
from vrag.retrieve.graph import LinkGraph, apply_boost
from vrag.vault import parse_note

ROOT = Path(__file__).resolve().parents[1]


def _notes(**bodies: str):
    return {f"{t}.md": parse_note(f"{t}.md", b) for t, b in bodies.items()}


def test_link_graph_is_undirected_and_resolves_titles():
    g = LinkGraph(_notes(A="see [[b]] and [[Missing]] and [[A]]", B="plain", C="[[A|alias]]"))
    assert g.neighbours == {"A.md": {"B.md", "C.md"}, "B.md": {"A.md"}, "C.md": {"A.md"}}


def test_boosts_use_best_normalised_neighbour():
    g = LinkGraph(_notes(A="[[B]] [[C]]", B="", C="", D=""))
    bonus = g.boosts({"A.md": 10.0, "B.md": 5.0}, boost=0.2)
    assert bonus["B.md"] == pytest.approx(0.2)  # neighbour A is the top hit
    assert bonus["C.md"] == pytest.approx(0.2)  # not retrieved, pulled in via A
    assert bonus["A.md"] == pytest.approx(0.1)  # best neighbour B has half the top score
    assert "D.md" not in bonus
    assert g.boosts({"A.md": 1.0}, boost=0.0) == {}
    assert g.boosts({}, boost=0.2) == {}


def test_apply_boost_normalises_and_adds():
    out = apply_boost({"A.md": 4.0, "B.md": 2.0}, {"B.md": 0.6, "C.md": 0.1})
    assert out == pytest.approx({"A.md": 1.0, "B.md": 1.1, "C.md": 0.1})


def _write(tmp_path, **bodies):
    for t, b in bodies.items():
        (tmp_path / f"{t}.md").write_text(b, encoding="utf-8")
    return tmp_path


def test_engine_graph_off_has_no_graph_score(tmp_path):
    vault = _write(tmp_path, Sauerteig="Sauerteig Roggen [[Brot]]", Brot="Backofen", Garten="Tomaten")
    hits = Engine().index(vault).search("Sauerteig")
    assert [h.note_path for h in hits] == ["Sauerteig.md"]
    assert "graph" not in hits[0].stage_scores


def test_engine_graph_pulls_in_linked_note(tmp_path):
    vault = _write(tmp_path, Sauerteig="Sauerteig Roggen [[Brot]]", Brot="Backofen", Garten="Tomaten")
    cfg = Config(graph=GraphConfig(enabled=True, boost=0.1))
    hits = Engine(cfg).index(vault).search("Sauerteig")
    assert [h.note_path for h in hits] == ["Sauerteig.md", "Brot.md"]
    assert hits[0].stage_scores["graph"] == 0.0
    assert hits[1].stage_scores == {"graph": pytest.approx(0.1)}
    assert hits[1].snippet == "Backofen"  # graph-only hit shows its first chunk


def test_engine_graph_reorders_close_hits(tmp_path):
    # B and C match equally; only C links to the top hit A, so it wins the tie
    vault = _write(tmp_path, A="Kaffee Kaffee Kaffee", B="Kaffee Tee", C="Kaffee Tee [[A]]", D="Wasser")
    off = Engine().index(vault).search("Kaffee")
    on = Engine(Config(graph=GraphConfig(enabled=True, boost=0.2))).index(vault).search("Kaffee")
    assert on[0].note_path == "A.md"
    assert [h.note_path for h in on].index("C.md") < [h.note_path for h in on].index("B.md")
    assert {h.note_path for h in off} <= {h.note_path for h in on}


def test_engine_graph_on_sample_vault():
    cfg = Config.load(ROOT / "config.toml")
    cfg.graph.enabled = True
    hits = Engine(cfg).index(ROOT / "vaults/sample").search("Sauerteig")
    assert hits and all("graph" in h.stage_scores for h in hits)
