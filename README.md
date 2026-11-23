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
