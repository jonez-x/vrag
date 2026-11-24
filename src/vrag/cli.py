"""vrag command line."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from . import __version__
from .config import Config
from .engine import Engine
from .evaluate import run_eval

DEFAULT_VAULT = "vaults/sample"


def _config(args) -> Config:
    # an explicit --config must exist: silently falling back to defaults hides typos and wrong cwds
    if args.config is None:
        return Config.load("config.toml")
    if not Path(args.config).is_file():
        sys.exit(f"vrag: config file not found: {args.config}")
    return Config.load(args.config)


def _engine(args) -> Engine:
    return Engine(_config(args)).index(args.vault)


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


def cmd_tui(args) -> int:
    from .ui.app import run  # Textual is only imported when the TUI is used

    # only an explicit --vault overrides the vault remembered in .vrag/
    run(config_path=args.config or "config.toml", vault=None if args.vault == DEFAULT_VAULT else args.vault)
    return 0


def cmd_mcp(args) -> int:
    from .mcp_server import run

    return run(args.mcp_vaults or [args.vault], _config(args))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="vrag", description="Local-first retrieval for Obsidian vaults")
    p.add_argument("--config", default=None, help="config file (default: ./config.toml if present)")
    p.add_argument("--vault", default=DEFAULT_VAULT)
    p.add_argument("--version", action="version", version=f"vrag {__version__}")
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

    t = sub.add_parser("tui", help="open the terminal UI")
    t.set_defaults(func=cmd_tui)

    m = sub.add_parser("mcp", help="read-only MCP server over stdio (for Claude Code & co.)")
    m.add_argument("--vault", dest="mcp_vaults", action="append", metavar="[NAME=]PATH",
                   help="vault to expose; repeat for several (default: top-level --vault)")
    m.set_defaults(func=cmd_mcp)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
