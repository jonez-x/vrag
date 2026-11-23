# vrag

```
█ █ █▀█ ▄▀█ █▀▀
▀▄▀ █▀▄ █▀█ █▄█
```

**Local-first retrieval for Obsidian vaults.** No cloud, no API keys — your notes never leave your machine.

- **Retrieval that's measured, not guessed** — every pipeline change is scored against an eval set; the pipeline is tuned by a self-improving agent loop ([`LOOP.md`](LOOP.md)).
- **Terminal UI** — live search with per-stage score breakdown, vault management, every setting editable.
- **For agents too** — `vrag mcp` exposes your vault to Claude Code, Cursor & co. as read-only MCP tools.

> 🚧 Early development — see [`PLAN.md`](PLAN.md).

## Quickstart
```bash
uv sync
uv run vrag search "wie verhindere ich overfitting" --vault vaults/sample
uv run vrag eval
```

### Dense retrieval (optional)
Dense search embeds chunks with [Ollama](https://ollama.com) and fuses them with BM25 via note-level RRF.
```bash
ollama pull bge-m3
# config.toml → [dense] enabled = true
```
Embeddings are cached in `.vrag/embeddings.sqlite` (sqlite-vec), so only new or changed chunks get embedded on re-index. If Ollama or the model is missing, vrag prints a warning and falls back to BM25.

## Retrieval quality

| Version | Pipeline | Recall@5 (dev) | MRR@10 (dev) |
|---|---|---|---|
| baseline | BM25, heading chunks | 0.838 | 0.742 |
| `feat/dense` | dense only (`bge-m3`) | 1.000 | 0.967 |
| `feat/dense` | hybrid BM25 + dense, note-level RRF (k=60) | 0.925 | 0.852 |

## How the loop works
```
┌─> agent changes ONE thing (chunking, stemming, fusion, …)
│        ↓
│   vrag eval  →  Recall@5, MRR
│        ↓
│   better? → commit + log   ·   worse? → revert + log
└────────┘
```
The eval set and the test vault are write-protected for the agent by a Claude Code hook, and a hidden holdout split catches overfitting.

## License
MIT
