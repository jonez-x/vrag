# Self-improving retrieval loop

You are optimising vrag's retrieval quality. The eval is the referee; you change the engine, never the test.

## Objective
Maximise **Recall@5** on `eval/dev.jsonl` (tie-breaker: MRR@10).
Target: Recall@5 ≥ 0.95. Stop early if reached.

## Setup (once per run)
1. `git switch -c loop/run-<NN>` from up-to-date `main`.
2. `uv run pytest -q && uv run vrag eval` → record the baseline as iteration 0 in `experiments.md`.

## Each iteration
1. **Hypothesis first.** Append to `experiments.md`:
   `## Iteration N — <idea>` · why you expect it to help · what you'll change.
2. **Change exactly one thing** (a config value, one stage, one function). Small diffs.
3. `uv run pytest -q` — if red, fix or revert. Never weaken a test.
4. `uv run vrag eval` — read `eval/results/latest.json`.
5. **Decide:**
   - Recall@5 improved, or equal with higher MRR → `git commit -am "loop: <idea> (R@5 x→y)"`.
   - Otherwise → `git checkout -- src/ tests/ config.toml && git clean -fd src/ tests/` (keeps `experiments.md`), commit the log entry as *reverted*.
6. Log the numbers (before → after) and one line of learnings.
7. Look at the **failing queries** in `latest.json` before picking the next idea.

## Budget
- Max **25 iterations** per run, or 3 reverts in a row on the same idea family → switch strategy.
- No new heavy dependency without noting it in the hypothesis.

## Forbidden
- Editing anything in `eval/` or `vaults/`, reading or running the holdout split.
- Special-casing queries, note names or vault content (no lookup tables, no hard-coded answers).
- Changing the metric or the `k` used by the eval.

## Idea backlog (non-binding)
Heading-aware chunk sizes · title/heading prefix · German stemming & compound splitting ·
BM25 parameters · tag/frontmatter fields · dense retrieval (bge-m3) · RRF fusion ·
wikilink graph boost · cross-encoder rerank · query rewriting.

## Finish
Open **one PR** for the run: score table (iteration 0 vs final), the kept changes, and the `experiments.md` diff.
A human runs the holdout before merging.
