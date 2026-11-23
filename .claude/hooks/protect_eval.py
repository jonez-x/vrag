#!/usr/bin/env python3
"""PreToolUse hook: keeps the self-improving loop honest.

- Blocks any write/edit inside eval/ and vaults/ (the referee + test data).
- Blocks every access to the holdout split (read, write, or shell).

Humans can bypass it deliberately:  VRAG_ALLOW_EVAL_EDIT=1 claude
Note: this is a guardrail against accidental gaming, not a security boundary.
"""

import json
import os
import sys

PROTECTED_WRITE = ("eval/", "vaults/")
HOLDOUT = "holdout"
WRITE_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}


def block(msg: str) -> None:
    print(f"[protect_eval] {msg}", file=sys.stderr)
    sys.exit(2)  # exit 2 = block the tool call, stderr is shown to Claude


def main() -> None:
    if os.environ.get("VRAG_ALLOW_EVAL_EDIT") == "1":
        return
    data = json.load(sys.stdin)
    tool = data.get("tool_name", "")
    inp = data.get("tool_input", {}) or {}
    root = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())

    path = inp.get("file_path") or inp.get("notebook_path") or inp.get("path") or ""
    rel = os.path.relpath(path, root).replace(os.sep, "/") if path else ""

    if HOLDOUT in rel or (tool == "Bash" and HOLDOUT in inp.get("command", "")):
        block("The holdout split is off-limits for the loop. Optimise on eval/dev.jsonl only.")

    if tool in WRITE_TOOLS and rel.startswith(PROTECTED_WRITE):
        block(f"{rel} is protected: eval/ and vaults/ are the referee. Change the engine, not the test.")


if __name__ == "__main__":
    main()
