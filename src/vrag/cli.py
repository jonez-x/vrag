"""vrag command line."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from .config import Config
from .engine import Engine
from .evaluate import run_eval

DEFAULT_VAULT = "vaults/sample"


def _engine(args) -> Engine:
    return Engine(Config.load(args.config)).index(args.vault)


def cmd_search(args) -> int:
    hits = _engine(args).search(args.query, k=args.k)
    if args.json:
        print(json.dumps([asdict(h) | {"anchor": h.anchor} for h in hits], ensure_ascii=False, indent=2))
        return 0
    if not hits:
        print("no results")
    for i, h in enumerate(hits, 1):
        print(f"{i}. {h.anchor}  ({h.score:.2f})\n   {h.snippet}\n")
    return 0


def cmd_eval(args) -> int:
    split = Path(args.eval_dir) / f"{args.split}.jsonl"
    result = run_eval(_engine(args), split)
    out = Path(args.eval_dir) / "results" / ("latest.json" if args.split == "dev" else f"{args.split}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {k: v for k, v in result.items() if k != "failures"}
    summary["failed_queries"] = len(result["failures"])
    print(json.dumps(summary, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="vrag", description="Local-first retrieval for Obsidian vaults")
    p.add_argument("--config", default="config.toml")
    p.add_argument("--vault", default=DEFAULT_VAULT)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("search", help="search a vault")
    s.add_argument("query")
    s.add_argument("-k", type=int, default=None)
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_search)

    e = sub.add_parser("eval", help="score the pipeline on an eval split")
    e.add_argument("--split", default="dev", choices=["dev", "holdout"])
    e.add_argument("--eval-dir", default="eval")
    e.set_defaults(func=cmd_eval)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
