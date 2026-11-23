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

### Dense retrieval (optional)
Dense search embeds chunks with [Ollama](https://ollama.com) and fuses them with BM25 via note-level RRF.
```bash
ollama pull bge-m3
# config.toml → [dense] enabled = true
```
Embeddings are cached in `.vrag/embeddings.sqlite` (sqlite-vec), so only new or changed chunks get embedded on re-index. If Ollama or the model is missing, vrag prints a warning and falls back to BM25.

### Reranking (optional)
A cross-encoder ([`bge-reranker-v2-m3`](https://huggingface.co/BAAI/bge-reranker-v2-m3)) rescores the top `top_n` notes of the first stage; a note counts with its best chunk.
```bash
uv sync --extra rerank   # sentence-transformers + torch, large
# config.toml → [rerank] enabled = true
```
The model is downloaded from Hugging Face on first use. Without the extra or the model, vrag prints a warning and keeps the first-stage ranking.

## Terminal UI

![vrag TUI — search with per-stage score breakdown](docs/tui-search.svg)

| Tab | Key | What it does |
|---|---|---|
| Search | `F1` | Live search as you type; results table plus a per-stage score breakdown (BM25 / dense / graph / rerank, whichever are on) for the highlighted hit. `Esc` jumps back to the search box. |
| Vaults | `F2` | Add a vault by path, `Enter` on a row opens it, *Remove* drops it. Remembered in `.vrag/vaults.json`. |
| Settings | `F3` | Every `config.toml` option as a form; `Ctrl+S` saves and re-indexes. Only the changed values are rewritten, comments and layout stay. |
| Eval | `F4` | `Ctrl+R` scores the dev split on the sample vault; history with deltas lives in `.vrag/eval_history.jsonl` (gitignored). |

`Ctrl+Q` quits. More screenshots: [Eval](docs/tui-eval.svg) · [Settings](docs/tui-settings.svg) — regenerate with `uv run python scripts/screenshots.py`.

## Use it from Claude Code (MCP)
`vrag mcp` is a read-only [MCP](https://modelcontextprotocol.io) server over stdio. Register it once:
```bash
claude mcp add vrag -- uv run --directory /path/to/vrag vrag mcp --vault /path/to/your/vault
```
Use absolute paths. Repeat `--vault [NAME=]PATH` to expose several vaults. Then run `/mcp` in Claude Code
to check that `vrag` is connected.

| Tool | What it does |
|---|---|
| `search_vault(query, k?, vault?)` | note-level hits with heading, snippet, per-stage scores |
| `read_note(note, vault?)` | full markdown body, frontmatter, tags, outgoing links |
| `related_notes(note, vault?)` | `[[wikilink]]` neighbours: outgoing, backlink or both |
| `list_vaults()` | exposed vaults and note counts |

`note` is a vault-relative path (`Kochen/Shakshuka.md`) or a note title. The server can't write anything,
and it only returns notes it indexed inside the vault. Absolute paths, `..`, symlinks that point
outside the vault and `.obsidian/` are all refused.

## Retrieval quality

| Version | Pipeline | Recall@5 (dev) | MRR@10 (dev) |
|---|---|---|---|
| baseline | BM25, heading chunks | 0.838 | 0.742 |
| `feat/dense` | dense only (`bge-m3`) | 1.000 | 0.967 |
| `feat/dense` | hybrid BM25 + dense, note-level RRF (k=60) | 0.925 | 0.852 |
| `loop/run-01` + `feat/dense` | BM25 + stemming/stopwords (default) | 0.950 | 0.883 |
| `loop/run-01` + `feat/dense` | hybrid BM25 + dense | 1.000 | 0.943 |
| `feat/graph` | BM25 + graph, boost 0.05 / 0.1 / 0.2 | 0.950 | 0.883 |
| `feat/graph` | BM25 + graph, boost 0.3 | 0.950 | 0.896 |
| `feat/graph` | hybrid + graph, boost 0.05 | 1.000 | 0.943 |
| `feat/graph` | hybrid + graph, boost 0.1 / 0.2 / 0.3 | 1.000 / 1.000 / 0.950 | 0.938 / 0.916 / 0.843 |
| `feat/rerank` | BM25 + rerank, top_n 10 / 20 / 30 | 0.950 | 0.913 |
| `feat/rerank` | hybrid + rerank, top_n 10 / 20 / 30 | 1.000 | 0.950 |

The wikilink graph boost is off by default: on dev it is neutral at small boosts and hurts hybrid at larger ones.

Reranking is off by default (optional extra, CI does not install it). It lifts MRR on both pipelines; Recall@5 stays the same.
Latency per query on an Apple-silicon Mac, model already loaded: BM25 < 1 ms → ~270 ms with rerank (only BM25-matching notes get rescored, so top_n barely matters);
hybrid ~23 ms → ~640 / 1080 / 1510 ms at top_n 10 / 20 / 30. The default `top_n = 30` is kept; on this vault top_n 10 scores the same at less than half the latency.

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
