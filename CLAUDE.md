# vrag — notes for Claude Code

Local-first retrieval for Obsidian vaults. One engine, three surfaces:
TUI (humans) · CLI `--json` (scripts + the self-improving loop) · MCP server (agents).

## Commands
```bash
uv sync                                  # install
uv run pytest -q                         # tests — must stay green
uv run vrag eval                         # dev-split score → eval/results/latest.json
uv run vrag search "query" --json        # one query
uv run vrag tui                          # terminal UI (PR 6)
```

## Layout
```
src/vrag/
  config.py      Config dataclasses, loaded from config.toml
  vault.py       Note loading: frontmatter, headings, [[wikilinks]]
  chunking.py    Markdown-aware chunking
  retrieve/      One module per pipeline stage (bm25, dense, graph, rerank)
  engine.py      Engine.index() / Engine.search() — the only public API
  evaluate.py    Recall@k, MRR, eval runner
  cli.py         argparse entry point
  ui/            Textual TUI + Obsidian theme + logo
eval/            dev.jsonl (loop may read) · holdout.jsonl (loop may NOT touch)
vaults/sample/   Public test vault — never put private notes here
```

## Conventions
- Python 3.11+, type hints, dataclasses, no global state.
- Every pipeline stage is toggleable in `config.toml`; defaults must keep evals reproducible.
- Search results are note-level and deduplicated; each `Hit` carries per-stage scores for explainability.
- Keep dependencies small; heavy models are optional extras and must fail gracefully when absent.
- One PR = one concern. Follow `PLAN.md` order.

## Hard rules
- `eval/` and `vaults/` are read-only for agents (enforced by `.claude/hooks/protect_eval.py`).
- Never read or run the holdout split. Humans run it: `VRAG_ALLOW_EVAL_EDIT=1 uv run vrag eval --split holdout`.
- When running the improvement loop, follow `LOOP.md` exactly.
