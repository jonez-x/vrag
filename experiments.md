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
