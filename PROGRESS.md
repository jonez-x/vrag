# Progress log

One entry per iteration, newest last. Scores are dev split only (`uv run vrag eval`).

Template:

```markdown
## YYYY-MM-DD — PR <#> `<branch>`
- **Result:** merged / open / reverted — one line
- **Eval (dev):** Recall@5 before → after · MRR@10 before → after
- **Learnings:** …
- **Open problems:** …
```

## 2026-11-23 — PR 1 `feat/foundation`
- **Result:** merged (#1) — sample vault, dev/holdout eval set, engine API, BM25 baseline, `vrag search` / `vrag eval`, tests
- **Eval (dev):** Recall@5 — → 0.8375 · MRR@10 — → 0.7424 (baseline)
- **Learnings:** BM25 over heading chunks is a solid starting point; this is the reference for every later PR.
- **Open problems:** none recorded yet; failing queries in `eval/results/latest.json` are the input for `loop/run-01`.
