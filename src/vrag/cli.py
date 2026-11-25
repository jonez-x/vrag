"""vrag command line."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

from . import __version__
from .config import Config
from .engine import Engine
from .evaluate import run_eval

DEFAULT_VAULT = "vaults/sample"  # the repo's sample vault: eval default, and the last resort from a clone
NO_VAULT = """vrag: which vault? Pass its folder once, vrag remembers it:
  vrag tui ~/Notes
  vrag search "your query" --vault ~/Notes
(or set VRAG_VAULT, or run vrag inside the vault folder)"""


def _config(args) -> Config:
    # an explicit --config must exist: silently falling back to defaults hides typos and wrong cwds
    if args.config is None:
        return Config.load("config.toml")
    if not Path(args.config).is_file():
        sys.exit(f"vrag: config file not found: {args.config}")
    return Config.load(args.config)


def _abs(path: str) -> str:
    return str(Path(path).expanduser().resolve())


def find_vault(args, remember: bool = False) -> str | None:
    """The vault to use: --vault, $VRAG_VAULT, the current folder if it is an Obsidian vault, the last one used.

    With ``remember``, a vault given on the command line becomes the remembered one.
    """
    from .ui.state import VaultRegistry  # no Textual import: state.py is plain Python

    given = args.vault or os.environ.get("VRAG_VAULT")
    if given:
        path = _abs(given)
        if not Path(path).is_dir():
            sys.exit(f"vrag: vault folder not found: {given}")
        if remember and args.vault:
            VaultRegistry.for_user().activate(path)
        return path
    if Path(".obsidian").is_dir():
        return _abs(".")
    active = VaultRegistry.for_user().active
    if active and Path(active).is_dir():
        return active
    return _abs(DEFAULT_VAULT) if Path(DEFAULT_VAULT).is_dir() else None


def _vault_or_exit(args, remember: bool = False) -> str:
    vault = find_vault(args, remember)
    if vault is None:
        sys.exit(NO_VAULT)
    return vault


def cmd_search(args) -> int:
    hits = Engine(_config(args)).index(_vault_or_exit(args, remember=True)).search(args.query, k=args.k)
    if args.json:
        print(json.dumps([asdict(h) | {"anchor": h.anchor} for h in hits], ensure_ascii=False, indent=2))
        return 0
    if not hits:
        print("no results")
    for i, h in enumerate(hits, 1):
        print(f"{i}. {h.anchor}  ({h.score:.2f})\n   {h.snippet}\n")
    return 0


def cmd_eval(args) -> int:
    # eval is about the pipeline, not your notes: always the sample vault unless --vault says otherwise
    engine = Engine(_config(args)).index(args.vault or DEFAULT_VAULT)
    split = Path(args.eval_dir) / f"{args.split}.jsonl"
    result = run_eval(engine, split)
    out = Path(args.eval_dir) / "results" / ("latest.json" if args.split == "dev" else f"{args.split}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {k: v for k, v in result.items() if k != "failures"}
    summary["failed_queries"] = len(result["failures"])
    print(json.dumps(summary, indent=2))
    return 0


def cmd_tui(args) -> int:
    from .ui.app import run  # Textual is only imported when the TUI is used

    args.vault = getattr(args, "vault_arg", None) or args.vault
    # the TUI remembers whatever it opens; None → it asks for a vault on its Vaults tab
    run(config_path=args.config or "config.toml", vault=find_vault(args))
    return 0


def cmd_mcp(args) -> int:
    from .mcp_server import run

    return run(args.mcp_vaults or [_vault_or_exit(args)], _config(args))


def main(argv: list[str] | None = None) -> int:
    # --config / --vault work before and after the subcommand: `vrag --vault X search q` == `vrag search q --vault X`
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--config", default=argparse.SUPPRESS, help="config file (default: ./config.toml if present)")
    with_vault = argparse.ArgumentParser(add_help=False)
    with_vault.add_argument("--vault", "-v", default=argparse.SUPPRESS, metavar="PATH",
                            help="vault folder (default: the last one used)")

    p = argparse.ArgumentParser(prog="vrag", description="Local-first retrieval for Obsidian vaults. "
                                "Without a command, opens the terminal UI.")
    # own actions, not `parents`: argparse shares parent actions, and a default set here would leak into them
    p.add_argument("--config", default=None, help="config file (default: ./config.toml if present)")
    p.add_argument("--vault", "-v", default=None, metavar="PATH", help="vault folder (default: the last one used)")
    p.set_defaults(func=cmd_tui)
    p.add_argument("--version", action="version", version=f"vrag {__version__}")
    sub = p.add_subparsers(dest="cmd", metavar="{tui,search,mcp,eval}")

    t = sub.add_parser("tui", help="open the terminal UI (default)", parents=[common, with_vault])
    t.add_argument("vault_arg", nargs="?", metavar="VAULT", help="vault folder to open (remembered)")
    t.set_defaults(func=cmd_tui)

    s = sub.add_parser("search", help="search a vault", parents=[common, with_vault])
    s.add_argument("query")
    s.add_argument("-k", type=int, default=None)
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_search)

    m = sub.add_parser("mcp", help="read-only MCP server over stdio (for Claude Code & co.)", parents=[common])
    m.add_argument("--vault", "-v", dest="mcp_vaults", action="append", metavar="[NAME=]PATH",
                   help="vault to expose; repeat for several (default: the last one used)")
    m.set_defaults(func=cmd_mcp)

    e = sub.add_parser("eval", help="score the pipeline on an eval split", parents=[common, with_vault])
    e.add_argument("--split", default="dev", choices=["dev", "holdout"])
    e.add_argument("--eval-dir", default="eval")
    e.set_defaults(func=cmd_eval)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
