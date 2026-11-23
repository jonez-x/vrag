# Experiments — loop/run-01 (BM25-only)

Dev split only (`uv run vrag eval`). Objective: Recall@5 (tie-breaker MRR@10).

## Iteration 0 — baseline (main)
- Recall@5 0.8375 · MRR@10 0.7424 · 7 failed queries (d01, d08, d09, d11, d13, d17, d32)
- Observations: no stopword handling, so frequent function words ("ich", "die", "wie") dominate
  short queries; no stemming/compound handling ("Fahrradkette" vs "Kette", "Intervallen" vs
  "Intervalltraining"); heading chunks lose the note title context.

## Iteration 1 — prefix note title + heading to each chunk
- Why: section chunks like "## Kette" or "## Tapering" lose the note's topic words
  ("Fahrrad Wartung", "Halbmarathon Plan"); the title is a strong relevance signal.
- Change: `chunking.prefix_title = true` (config only, already implemented).
- Result: Recall@5 0.8375 → 0.8375 · MRR@10 0.7424 → 0.6986 — **reverted**.
- Learning: title tokens repeated in every chunk inflate common words and blur the ranking;
  the failures are vocabulary-mismatch problems, not missing-context problems.

## Iteration 2 — German stopword filtering
- Why: queries are natural-language questions ("Wann muss die …", "Wie reduziere ich das …").
  Function words have low but non-zero IDF and pull short, unrelated chunks to the top
  (e.g. "Gewohnheiten aufbauen" appears for several unrelated questions).
- Change: new `bm25.stopwords` flag; a small built-in German stopword list removed at tokenisation.
- Result: Recall@5 0.8375 → 0.85 · MRR@10 0.7424 → 0.80 — **kept**.
- Learning: big MRR gain; remaining failures are morphology/compounds (Intervallen, Fahrradkette, Vorkochen).

## Iteration 3 — light German stemming
- Why: remaining failures are inflection mismatches: "langen Kontexten" vs "lange Kontexte",
  "Günstiges" vs "Günstig", "reduziere" vs "reduzieren", "Intervallen" vs "Intervall".
- Change: implement the existing `bm25.stemming` hook as a CISTEM-style suffix stripper
  (umlaut folding, strip -em/-er/-nd and -e/-s/-n/-t), dependency-free; enable it in config.
- Result: Recall@5 0.85 → 0.95 · MRR@10 0.80 → 0.8833 — **kept**.
- Learning: inflection was the dominant failure mode; d09, d11, d17, d32 now pass. Remaining:
  d08 ("ML-Klausur" — abbreviation vs "Machine Learning", compound "Altklausuren") and
  d13 ("Fahrradkette" — compound vs heading "Kette"). Both need compound splitting or dense retrieval.

## Stop
Target Recall@5 ≥ 0.95 reached after 3 iterations → stopping early per LOOP.md.

| Iteration | Change | Recall@5 | MRR@10 | Failed | Status |
|---|---|---|---|---|---|
| 0 | baseline (main) | 0.8375 | 0.7424 | 7 | — |
| 1 | `prefix_title = true` | 0.8375 | 0.6986 | 7 | reverted |
| 2 | German stopwords | 0.85 | 0.80 | 6 | kept |
| 3 | German light stemming | 0.95 | 0.8833 | 2 | kept |

---

# Experiments — loop/run-02 (full pipeline)

Dev split only. Two tracked scores per iteration (orchestrator decision, since R@5 ≥ 0.95 was already met):
- **(a) full** — `uv run vrag --config .vrag/full.toml eval`: `config.toml` with dense (bge-m3) + graph (0.05) on,
  rerank off. Target: MRR@10 at Recall@5 = 1.0.
- **(b) default** — `uv run vrag eval` (BM25 + stemming + stopwords; what CI measures). Must never get worse.

A change that worsens (a) or (b) is reverted.

## Iteration 0 — baseline (main @ 713c34e)
- (a) full: Recall@5 1.0 · MRR@10 0.9425 · 0 failed. Not at rank 1: d06, d26 (RRF tie with the
  rank-1 note, lost on order), d13 (rank 2), d08 (rank 5).
- (b) default: Recall@5 0.95 · MRR@10 0.8833 · failed d08, d13. Also not rank 1: d06, d11, d21, d26, d37.
- Observations: in d08 and d13 the top BM25 hit (Kreuzvalidierung, 4.275) matches only the question
  word "wann", which is missing from the stopword list. Ties in RRF are broken by insertion order.
- Result: (a) full 1.0 / 0.9425 → 1.0 / 0.9563 · (b) default 0.95 / 0.8833 → 0.95 / 0.8833 — **kept**.
- Learning: d13 moves to rank 1 in full (spurious "wann" match gone); in default d08/d13 still miss because
  the BM25 vocabulary never matches the compounds ("Fahrradkette" vs "Fahrrad"/"Kette", "Klausur" vs "Altklausuren").

## Iteration 2 — corpus-driven compound splitting (`bm25.decompound`)
- Why: German compounds are the remaining BM25 vocabulary gap: query "Fahrradkette" vs note words
  "Fahrrad" + "Kette"; query "Klausur" vs note word "Altklausuren". Splitting a long token into two
  parts that both occur in the corpus vocabulary bridges this without a dictionary dependency.
- Change: new `bm25.decompound` flag. After stemming, a token of ≥ 7 chars gets its parts added
  (first split where both stemmed parts are corpus terms, head ≥ 3, tail ≥ 4 chars); applied to
  chunks and queries alike, original token kept. On in `config.toml`.
- Result: (a) full 1.0 / 0.9563 → 1.0 / 0.9688 · (b) default 0.95 / 0.8833 → 0.975 / 0.8958 — **kept**.
- Learning: first attempt split the *stemmed* token and failed — the stemmer over-strips ("kette" → "ket",
  "fahrradkette" → "fahrradk"), so splitting must run on the raw token and stem the parts. d13 now passes in default.

## Iteration 3 — right-headed fallback split (tail only)
- Why: d08 still misses in default: "Klausur" should match "Altklausuren", but "alt" is not a corpus
  term, so the two-part split never fires. German compounds are right-headed (an *Alt*klausur is a
  Klausur), so the tail alone is the meaningful part.
- Change: in `split_compound`, if no two-part split exists, return the longest tail of ≥ 5 chars that
  is a corpus term (head ≥ 3 chars). No new flag (same `decompound` stage).
- Result: (a) full 1.0 / 0.9688 → 1.0 / 0.9521 · (b) default 0.975 / 0.8958 → 0.975 / 0.8771 — **reverted**.
- Learning: tail-only splits fire on far too many tokens and add noisy matches; d08 still misses
  (the token "ml" also matches millilitre amounts in recipes). Keep requiring both parts to be corpus terms.
