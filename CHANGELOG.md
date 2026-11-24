# Changelog

All notable changes to this project. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
versions follow [Semantic Versioning](https://semver.org/). Scores are dev split only (40 queries); the held-out
split has not been checked by a human yet.

## [Unreleased]

### Changed
- A relative `dense.cache_dir` is resolved against the config file's directory, not the working directory, so
  `vrag mcp` started elsewhere reuses the same embedding cache.
- An explicit `--config` that does not exist is now an error instead of silently using the built-in defaults.

## [0.1.0] — unreleased

First release, published on PyPI as `vrag-obsidian` (command and import package: `vrag`).

### Added
- Engine API (`Engine.index()` / `Engine.search()`) with note-level, deduplicated hits and per-stage scores;
  markdown-aware chunking by heading, frontmatter, tags and `[[wikilinks]]` (#1).
- BM25 baseline, `vrag search` (`--json`) and `vrag eval` with Recall@k and MRR, sample vault, dev / held-out eval
  split (#1). Baseline: Recall@5 0.8375, MRR@10 0.7424.
- CI gate: pytest plus a dev-eval comparison against `main`, fails if Recall@5 drops (#2).
- German stopwords and light German stemming for BM25, from the first loop run (#3). Default: 0.95 / 0.8833.
- Optional dense retrieval: Ollama `bge-m3` embeddings, sqlite-vec cache in `.vrag/`, note-level RRF fusion,
  BM25 fallback when Ollama is missing (#4).
- Terminal UI (`vrag tui`): Search with per-stage score breakdown, Vaults, Settings (comment-preserving
  `config.toml` editor), Eval with score history (#5).
- Read-only MCP server (`vrag mcp`) with `search_vault`, `read_note`, `related_notes`, `list_vaults` (#6).
- Optional wikilink neighbour boost (`[graph]`), one hop, min-max normalised (#7).
- Optional cross-encoder reranking with `bge-reranker-v2-m3` (`rerank` extra), falls back when missing (#8).
- Second loop run: full stopword list, corpus-driven compound splitting, acronym terms, BM25 `k1 = 1.2`,
  weighted RRF (`dense_weight = 1.2`) (#9). Default: 1.0 / 0.9208 · full (dense + graph): 1.0 / 0.9875.
- `vrag --version`, PyPI packaging, publish workflow via Trusted Publishing on `v*` tags, recall-over-iterations
  chart and demo GIF in the README.

### Fixed
- Built-in config defaults now match `config.toml`. Without a `config.toml`, an installed vrag used to fall back
  to the pre-loop baseline (dev Recall@5 0.8375 instead of 1.0).

### Known limitations
- All tuning used the 40 dev queries over one small sample vault; overfitting is likely until the held-out split
  is run.
- Reranking is too slow for live TUI search (0.3–1.5 s per query).
- Graph boost has no damping for highly linked hub notes.
- MCP server has no Resources, Prompts or cancellation.

[0.1.0]: https://github.com/jonez-x/vrag/releases/tag/v0.1.0
