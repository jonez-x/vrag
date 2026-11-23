# Roadmap — one PR per step

| # | PR | Scope | Done when |
|---|----|-------|-----------|
| 1 | `feat/foundation` | Sample vault, eval set (dev/holdout), engine API, BM25 baseline, `vrag search` / `vrag eval`, tests | Baseline score recorded in README |
| 2 | `loop/run-01` | First loop run, BM25-only (chunking, stemming, params) | Run PR with score table |
| 3 | `feat/dense` | Ollama `bge-m3` embeddings, local vector store (sqlite-vec), RRF fusion | Hybrid beats BM25 on dev |
| 4 | `feat/graph` | Wikilink neighbour boost | Toggleable, measured |
| 5 | `feat/rerank` | Cross-encoder `bge-reranker-v2-m3` (optional extra) | Toggleable, measured |
| 6 | `feat/tui` | Textual app: Search (per-stage score breakdown), Vaults, Settings (edits `config.toml`), Eval (score history) · Obsidian theme + logo from `ui/logo.py` | Demo GIF in README |
| 7 | `feat/mcp` | `vrag mcp` stdio server: `search_vault`, `read_note`, `related_notes`, `list_vaults` (read-only) | Works in Claude Code |
| 8 | `loop/run-02` | Loop over the full pipeline | Holdout Recall@5 ≥ 0.95 |
| 9 | `release/v0.1` | PyPI, README with recall-over-iterations chart, demo GIF | Tagged |

PR 6 and 7 only depend on the engine API from PR 1 and can run in parallel (separate git worktrees).
