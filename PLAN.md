# Roadmap — one PR per step

Status: `- [ ]` open · `- [x]` done · `- [!]` blocked: reason

- [x] **1 · `feat/foundation`**
  - Scope: Sample vault, eval set (dev/holdout), engine API, BM25 baseline, `vrag search` / `vrag eval`, tests
  - Done when: Baseline score recorded in README
- [ ] **2 · `loop/run-01`**
  - Scope: First loop run, BM25-only (chunking, stemming, params)
  - Done when: Run PR with score table
- [ ] **3 · `feat/dense`**
  - Scope: Ollama `bge-m3` embeddings, local vector store (sqlite-vec), RRF fusion
  - Done when: Hybrid beats BM25 on dev
- [ ] **4 · `feat/graph`**
  - Scope: Wikilink neighbour boost
  - Done when: Toggleable, measured
- [ ] **5 · `feat/rerank`**
  - Scope: Cross-encoder `bge-reranker-v2-m3` (optional extra)
  - Done when: Toggleable, measured
- [ ] **6 · `feat/tui`**
  - Scope: Textual app: Search (per-stage score breakdown), Vaults, Settings (edits `config.toml`), Eval (score history) · Obsidian theme + logo from `ui/logo.py`
  - Done when: Demo GIF in README
- [ ] **7 · `feat/mcp`**
  - Scope: `vrag mcp` stdio server: `search_vault`, `read_note`, `related_notes`, `list_vaults` (read-only)
  - Done when: Works in Claude Code
- [ ] **8 · `loop/run-02`**
  - Scope: Loop over the full pipeline
  - Done when: Holdout Recall@5 ≥ 0.95
- [ ] **9 · `release/v0.1`**
  - Scope: PyPI, README with recall-over-iterations chart, demo GIF
  - Done when: Tagged

PR 6 and 7 only depend on the engine API from PR 1 and can run in parallel (separate git worktrees).
