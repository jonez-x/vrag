from pathlib import Path

from vrag.chunking import chunk_note
from vrag.config import ChunkingConfig, Config
from vrag.engine import Engine
from vrag.evaluate import mrr_at_k, recall_at_k
from vrag.vault import parse_note

ROOT = Path(__file__).resolve().parents[1]
NOTE = """---
tags: [ml]
---
Intro text.

# Titel
## Abschnitt A
Siehe [[Andere Notiz]] und [[Dritte#Teil|Alias]].
## Abschnitt B
Mehr Text.
"""


def test_parse_frontmatter_and_links():
    n = parse_note("Ordner/Test.md", NOTE)
    assert n.title == "Test"
    assert n.tags == ["ml"]
    assert n.links == ["Andere Notiz", "Dritte"]
    assert not n.body.startswith("---")


def test_chunking_by_headings():
    chunks = chunk_note(parse_note("Test.md", NOTE), ChunkingConfig())
    assert [c.heading for c in chunks] == ["", "Titel", "Abschnitt A", "Abschnitt B"]


def test_chunking_respects_max_chars():
    long = parse_note("L.md", "x " * 2000)
    assert all(len(c.text) <= 300 for c in chunk_note(long, ChunkingConfig(max_chars=300)))


def test_metrics():
    assert recall_at_k(["a", "b", "c"], ["b", "z"], 2) == 0.5
    assert mrr_at_k(["a", "b"], ["b"]) == 0.5
    assert mrr_at_k(["a"], ["b"]) == 0.0


def test_config_loads_repo_file():
    cfg = Config.load(ROOT / "config.toml")
    assert cfg.bm25.enabled and cfg.search.k == 5


def test_engine_search_on_sample_vault():
    eng = Engine().index(ROOT / "vaults/sample")
    # "Sauerteig füttern" would hit the short daily note first (BM25 length norm) — a known baseline weakness
    hits = eng.search("Anstellgut mit Roggenvollkornmehl", k=3)
    assert hits and hits[0].note_path == "Kochen/Sauerteig ansetzen.md"
    assert len({h.note_path for h in hits}) == len(hits)  # deduplicated
    assert "bm25" in hits[0].stage_scores


def test_tokenize_drops_german_stopwords():
    from vrag.retrieve.bm25 import tokenize

    assert tokenize("Wann muss die Kette getauscht werden?") == [
        "wann", "muss", "die", "kette", "getauscht", "werden"
    ]
    assert tokenize("Wann muss die Kette getauscht werden?", stopwords=True) == [
        "kette", "getauscht"
    ]


def test_stopwords_cover_question_words_and_modals():
    from vrag.retrieve.bm25 import tokenize

    for q in ("wann", "wieso", "weshalb", "woher", "wohin", "wozu", "darf", "sollen", "könnte"):
        assert tokenize(f"{q} Fahrrad", stopwords=True) == ["fahrrad"], q


def test_split_compound_uses_corpus_vocabulary():
    from vrag.retrieve.bm25 import split_compound, stem_german

    assert split_compound("fahrradkette", {"fahrrad", "kette"}) == ["fahrrad", "kette"]
    vocab = {stem_german(t) for t in ("fahrrad", "kette", "alte", "klausur", "ketten", "verschleiß")}
    assert split_compound("altklausuren", vocab, stem=True) == ["alt", "klausur"]
    assert split_compound("kettenverschleiß", vocab, stem=True) == [stem_german("ketten"), stem_german("verschleiß")]
    assert split_compound("fahrrad", vocab, stem=True) == []  # short / not a compound of known terms
    assert split_compound("wanderschuhe", vocab, stem=True) == []


def test_decompound_matches_compound_query_to_parts():
    from vrag.config import BM25Config
    from vrag.retrieve.bm25 import BM25Index

    docs = ["Die Kette am Fahrrad ölen", "Brot backen mit Sauerteig"]
    on = BM25Index(docs, BM25Config(stemming=True, stopwords=True, decompound=True))
    off = BM25Index(docs, BM25Config(stemming=True, stopwords=True, decompound=False))
    assert on.scores("Fahrradkette")[0] > 0 and on.scores("Fahrradkette")[1] == 0
    assert off.scores("Fahrradkette") == [0.0, 0.0]


def test_acronyms_from_capitalised_runs():
    from vrag.config import BM25Config
    from vrag.retrieve.bm25 import BM25Index, acronyms

    assert acronyms("Prüfung in Machine Learning am Montag") == ["ml"]
    assert acronyms("Reciprocal Rank Fusion") == ["rr", "rf", "rrf"]
    assert acronyms("die Kette ölen") == []
    docs = ["Klausur in Machine Learning", "Brot backen"]
    on = BM25Index(docs, BM25Config(acronyms=True))
    assert on.scores("ML")[0] > 0 and BM25Index(docs, BM25Config(acronyms=False)).scores("ML") == [0.0, 0.0]


def test_stem_german_conflates_inflections():
    from vrag.retrieve.bm25 import stem_german, tokenize

    assert stem_german("langen") == stem_german("lange")
    assert stem_german("kontexten") == stem_german("kontexte")
    assert stem_german("günstiges") == stem_german("günstig")
    assert stem_german("intervallen") == "intervall"
    assert stem_german("1000er") == stem_german("1000") == "1000"  # "1000er" matches "1000 m"
    toks = tokenize("Die langen Kontexte", stemming=True, stopwords=True)
    assert toks == tokenize("lange Kontexten", stemming=True) and len(toks) == 2


def test_builtin_defaults_match_config_toml():
    # An installed vrag without a config.toml must score like the repo default.
    assert Config() == Config.load(ROOT / "config.toml")
    assert Config.load(ROOT / "missing.toml") == Config()
