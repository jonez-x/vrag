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

## Retrieval quality

| Version | Pipeline | Recall@5 (dev) | MRR@10 (dev) |
|---|---|---|---|
| baseline | BM25, heading chunks | _tbd_ | _tbd_ |

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
