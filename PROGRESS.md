# Progress log

One entry per iteration, newest last. Scores are dev split only (`uv run vrag eval`).

Template:

```markdown
## YYYY-MM-DD — PR <#> `<branch>`
- **Result:** merged / open / reverted — one line
- **Eval (dev):** Recall@5 before → after · MRR@10 before → after
- **Learnings:** …
- **Open problems:** …
```

## 2026-11-23 — PR 1 `feat/foundation`
- **Result:** merged (#1) — sample vault, dev/holdout eval set, engine API, BM25 baseline, `vrag search` / `vrag eval`, tests
- **Eval (dev):** Recall@5 — → 0.8375 · MRR@10 — → 0.7424 (baseline)
- **Learnings:** BM25 over heading chunks is a solid starting point; this is the reference for every later PR.
- **Open problems:** none recorded yet; failing queries in `eval/results/latest.json` are the input for `loop/run-01`.

## 2026-11-23 — PR 2 `chore/loop-infra`
- **Result:** merged (#2) — checkbox roadmap, this log, CI gate (pytest + dev eval PR vs. main, fails if Recall@5 < main − 0.005)
- **Eval (dev):** Recall@5 0.8375 → 0.8375 · MRR@10 0.7424 → 0.7424 (no engine change)
- **Learnings:** until `ci.yml` was on main, PRs had no checks at all, so nothing could be auto-merged.
- **Open problems:** CI gate is not a required check in branch protection yet. Comparison is against current `main`, so a stale PR can go red after main improves.

## 2026-11-23 — PR 3 `loop/run-01`
- **Result:** merged (#3) — 3 iterations, stopped at target: title prefix (reverted, MRR dropped), German stopwords (kept), light German stemming (kept)
- **Eval (dev):** Recall@5 0.8375 → 0.95 · MRR@10 0.7424 → 0.8833 · failed queries 7 → 2
- **Learnings:** morphology was the main BM25 gap on German notes. Remaining misses (d08 "ML-Klausur", d13 "Fahrradkette") need compound splitting or dense.
- **Open problems:** merged without the human held-out run (owner authorised merging). Stemmer over-truncates some stems (e.g. "kontext" → "kontex"); harmless so far.

## 2026-11-23 — PR 4 `feat/dense`
- **Result:** merged (#4) — Ollama `bge-m3` embedder, sqlite-vec cache in `.vrag/`, note-level RRF, BM25 fallback when Ollama is missing; off by default (CI has no Ollama)
- **Eval (dev, measured locally before #3):** BM25 0.8375 / 0.7424 · dense only 1.000 / 0.9667 · hybrid 0.925 / 0.8521
- **Eval (dev, main after #3 + #4):** BM25 0.95 / 0.8833 · hybrid **1.000 / 0.9425**
- **Learnings:** fusing at note level beat section level (0.900 / 0.8594). With plain BM25, the BM25 share in fusion pulled good dense hits down; after stemming, hybrid reaches 1.0.
- **Open problems:** dev set looks too easy for dense (dense only = 1.0). `cache_dir` is relative to the working directory.

## 2026-11-23 — PR 5 `feat/tui`
- **Result:** merged (#5) — Textual app: Search (per-stage scores), Vaults, Settings (comment-preserving `config.toml` editor), Eval (history in `.vrag/`)
- **Eval (dev):** unchanged (no retrieval change)
- **Learnings:** the Settings roundtrip test caught `dense.batch_size` missing from `config.toml` after #4; fixed by listing it there.
- **Open problems:** demo GIF missing (SVG screenshots only). F1–F4 may be media keys in macOS terminals. Live search on every keystroke will be slow with dense/rerank.

## 2026-11-23 — PR 6 `feat/mcp`
- **Result:** merged (#6) — `vrag mcp` stdio server with `search_vault`, `read_note`, `related_notes`, `list_vaults`; hand-written JSON-RPC, no new dependency
- **Eval (dev):** unchanged (no retrieval change)
- **Learnings:** verified in Claude Code via `claude -p --mcp-config`: all three tools called, sensible top hits.
- **Open problems:** no Resources/Prompts/cancellation. Without an absolute `--config`, a different working directory silently uses defaults.
