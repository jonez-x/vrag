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
uv run vrag tui
```

## Terminal UI

![vrag TUI — search with per-stage score breakdown](docs/tui-search.svg)

| Tab | Key | What it does |
|---|---|---|
| Search | `F1` | Live search as you type; results table plus a per-stage score breakdown (BM25, and later dense / graph / rerank) for the highlighted hit. `Esc` jumps back to the search box. |
| Vaults | `F2` | Add a vault by path, `Enter` on a row opens it, *Remove* drops it. Remembered in `.vrag/vaults.json`. |
| Settings | `F3` | Every `config.toml` option as a form; `Ctrl+S` saves and re-indexes. Only the changed values are rewritten, comments and layout stay. |
| Eval | `F4` | `Ctrl+R` scores the dev split on the sample vault; history with deltas lives in `.vrag/eval_history.jsonl` (gitignored). |

`Ctrl+Q` quits. More screenshots: [Eval](docs/tui-eval.svg) · [Settings](docs/tui-settings.svg) — regenerate with `uv run python scripts/screenshots.py`.

## Retrieval quality

| Version | Pipeline | Recall@5 (dev) | MRR@10 (dev) |
|---|---|---|---|
| baseline | BM25, heading chunks | 0.838 | 0.742 |

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
