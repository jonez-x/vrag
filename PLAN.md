# Roadmap — one PR per step

Status: `- [ ]` open · `- [x]` done · `- [!]` blocked: reason

- [x] **1 · `feat/foundation`**
  - Scope: Sample vault, eval set (dev/holdout), engine API, BM25 baseline, `vrag search` / `vrag eval`, tests
  - Done when: Baseline score recorded in README
- [x] **2 · `loop/run-01`** — #3
  - Scope: First loop run, BM25-only (chunking, stemming, params)
  - Done when: Run PR with score table
- [x] **3 · `feat/dense`** — #4
  - Scope: Ollama `bge-m3` embeddings, local vector store (sqlite-vec), RRF fusion
  - Done when: Hybrid beats BM25 on dev
- [x] **4 · `feat/graph`** — #7
  - Scope: Wikilink neighbour boost
  - Done when: Toggleable, measured
- [x] **5 · `feat/rerank`** — #8
  - Scope: Cross-encoder `bge-reranker-v2-m3` (optional extra)
  - Done when: Toggleable, measured
- [ ] **6 · `feat/tui`** — app merged in #5; demo GIF still missing (SVG screenshots only)
  - Scope: Textual app: Search (per-stage score breakdown), Vaults, Settings (edits `config.toml`), Eval (score history) · Obsidian theme + logo from `ui/logo.py`
  - Done when: Demo GIF in README
- [x] **7 · `feat/mcp`** — #6
  - Scope: `vrag mcp` stdio server: `search_vault`, `read_note`, `related_notes`, `list_vaults` (read-only)
  - Done when: Works in Claude Code
- [!] **8 · `loop/run-02`** — blocked: loop merged in #9 (dev R@5 1.0 default + full); held-out check must be run by a human
  - Scope: Loop over the full pipeline
  - Done when: Holdout Recall@5 ≥ 0.95
- [ ] **9 · `release/v0.1`**
  - Scope: PyPI, README with recall-over-iterations chart, demo GIF
  - Done when: Tagged

PR 6 and 7 only depend on the engine API from PR 1 and can run in parallel (separate git worktrees).
