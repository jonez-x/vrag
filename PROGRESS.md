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

## 2026-11-23 — PR 7 `feat/graph`
- **Result:** merged (#7) — `retrieve/graph.py`, one-hop wikilink neighbour boost with min-max normalisation, per-stage `graph` score; off by default, `boost = 0.05`
- **Eval (dev):** default 0.95 / 0.8833 → unchanged · hybrid 1.0 / 0.9425 → 1.0 / 0.9425 (boost 0.05); boost ≥ 0.1 hurts hybrid MRR, boost 0.3 helps BM25 MRR (0.8958)
- **Learnings:** max-only normalisation hurt hybrid (MRR 0.8919); min-max fixed it. Dev has few queries where a linked note is the answer, so the effect is barely measurable.
- **Open problems:** no damping for highly linked hubs; one hop only.

## 2026-11-23 — PR 8 `feat/rerank`
- **Result:** merged (#8) — optional `rerank` extra (cross-encoder `bge-reranker-v2-m3`), `retrieve/rerank.py`, falls back when the extra is missing; off by default
- **Eval (dev, worker-measured locally):** BM25 0.95 / 0.8833 → 0.95 / 0.9125 (~270 ms/query) · hybrid 1.0 / 0.9425 → 1.0 / 0.95 (0.6–1.5 s/query)
- **Learnings:** top_n 10/20/30 score the same on dev; top_n 10 halves latency.
- **Open problems:** too slow for live TUI search; ~2 GB model download; `uv.lock` now pins the extra's packages (CI doesn't install them).

## 2026-11-23 — PR 9 `loop/run-02`
- **Result:** merged (#9) — 6 iterations (5 kept, 1 reverted): full stopword list, corpus-driven compound splitting, weighted RRF (`dense_weight = 1.2`), BM25 `k1 = 1.2`, acronym terms from capitalised word runs
- **Eval (dev):** default 0.95 / 0.8833 → **1.0 / 0.9208** (0 misses) · full (dense + graph) 1.0 / 0.9425 → **1.0 / 0.9875** — orchestrator reproduced both
- **Learnings:** compound splitting fixed "Fahrradkette"; acronyms fixed "ML-Klausur". Splitting before stemming sidesteps the over-truncating stemmer.
- **Open problems:** done criterion (held-out R@5 ≥ 0.95) not checked — human must run it for default and full config. Acronym heuristic and `k1` / `dense_weight` were tuned on 40 dev queries → overfitting risk; acronyms may add noisy terms on other vaults.

## 2026-11-23 — PR 10 `release/v0.1`
- **Result:** merged (#10), tagged `v0.1.0` — PyPI metadata as `vrag-obsidian` (CLI stays `vrag`, `vrag --version`), `publish.yml` (Trusted Publishing on `v*` tags), README rewrite with recall chart (light/dark SVG) and demo GIF (`scripts/demo_gif.py`, Pillow via `uv run --with pillow` only), CHANGELOG; built-in config defaults now match `config.toml`
- **Eval (dev):** default 1.0 / 0.9208 → unchanged
- **Learnings:** first release worker hit the usage limit mid-run; its pushed commits were picked up by a second worker without rework. Renaming the package to `vrag-obsidian` left a stale venv entry point locally — `uv sync --reinstall-package vrag-obsidian` fixes it.
- **Open problems:** PyPI upload needs a one-time pending publisher on pypi.org (project `vrag-obsidian`, repo `jonez-x/vrag`, workflow `publish.yml`, environment `pypi`), then re-run the publish job for `v0.1.0`. Demo GIF shows BM25 only (recorded without Ollama). Held-out split still unchecked.

## 2026-11-24 — PR 11 `fix/config-paths`
- **Result:** merged (#11) — relative `dense.cache_dir` resolves next to the config file (`Config.source` / `Config.resolve()`); an explicit `--config` that doesn't exist exits with an error
- **Eval (dev):** default 1.0 / 0.9208 → unchanged
- **Learnings:** local experiment configs in `.vrag/` had `cache_dir = ".vrag"`, which now means `.vrag/.vrag`; set to `"."`.
- **Open problems:** TUI state (`.vrag/` history + vault list) still lives in the working directory.

## 2026-11-24 — PR 12 `feat/tui-debounce`
- **Result:** merged (#12) — with dense or rerank on, live search waits for a 350 ms typing pause; `Enter` searches at once; BM25-only unchanged
- **Eval (dev):** unchanged (no retrieval change)
- **Learnings:** search stays on the main thread: the sqlite embedding cache connection can't be shared across threads.
- **Open problems:** a slow search still blocks the UI while it runs (only once per pause now).

## 2026-11-24 — PR 13 `feat/tui-note-view`
- **Result:** merged (#13) — `Enter` on a hit / `Ctrl+O` opens the full note (rendered markdown, scrolled to the matched section, tags, links, backlinks)
- **Eval (dev):** unchanged (no retrieval change)
- **Learnings:** `MarkdownViewer` swallows `TableOfContentsUpdated`, so the scroll-to-heading uses a plain `Markdown` in a `VerticalScroll`; a long-note test caught it. A debounced search firing behind the modal is harmless and keeps results in sync with the query box.
- **Open problems:** no "open in Obsidian" key yet. Holdout split still unchecked (hook blocks agents; human run needed).
