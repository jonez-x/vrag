"""Read-only MCP server over stdio: exposes vaults to agents (Claude Code, Cursor, …).

Speaks the MCP stdio transport directly (newline-delimited JSON-RPC 2.0) instead of
pulling in the `mcp` SDK — four read-only tools don't justify its dependency tree.
Only notes the engine indexed are ever served; nothing is read from the request's path.
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path, PurePosixPath
from typing import IO, Any

from . import __version__
from .config import Config
from .engine import Engine
from .vault import Note

PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")  # newest first
MAX_K = 50


class ToolError(Exception):
    """Raised for bad tool input; reported to the client as an `isError` result."""


@dataclass
class Vault:
    name: str
    root: Path
    config: Config
    _engine: Engine | None = field(default=None, repr=False)
    _allowed: set[str] = field(default_factory=set, repr=False)

    @property
    def engine(self) -> Engine:
        if self._engine is None:
            eng = Engine(self.config).index(self.root)
            # defence in depth: drop anything (e.g. a symlinked note) that resolves outside the vault
            root = self.root.resolve()
            self._allowed = {p for p in eng.notes if (root / p).resolve().is_relative_to(root)}
            self._engine = eng
        return self._engine

    @property
    def notes(self) -> dict[str, Note]:
        eng = self.engine
        return {p: n for p, n in eng.notes.items() if p in self._allowed}


def parse_vault_spec(spec: str) -> tuple[str, Path]:
    """`name=path` or just `path` (name = directory name)."""
    name, sep, path = spec.partition("=")
    if not sep:
        name, path = "", spec
    root = Path(path).expanduser()
    return (name or root.resolve().name), root


def _guard_root(root: Path) -> None:
    root = root.resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Vault not found: {root}")
    # never let the server see the eval referee (holdout split), even by misconfiguration
    for p in (root, *root.parents):
        if p.name == "eval" and (p / "dev.jsonl").exists():
            raise ValueError(f"Refusing to serve an eval directory as a vault: {root}")
    if (root / "eval" / "dev.jsonl").exists():
        raise ValueError(f"Refusing to serve a directory that contains eval/: {root}")


class VaultTools:
    """The four read-only tools. Plain methods so they can be tested without a transport."""

    def __init__(self, vaults: dict[str, Vault]):
        if not vaults:
            raise ValueError("at least one vault is required")
        for v in vaults.values():
            _guard_root(v.root)
        self.vaults = vaults

    @classmethod
    def from_specs(cls, specs: list[str], config: Config) -> VaultTools:
        vaults: dict[str, Vault] = {}
        for spec in specs:
            name, root = parse_vault_spec(spec)
            if name in vaults:
                raise ValueError(f"duplicate vault name: {name}")
            vaults[name] = Vault(name, root, config)
        return cls(vaults)

    # -- helpers --------------------------------------------------------------

    def _vault(self, name: str | None) -> Vault:
        if not name:
            if len(self.vaults) == 1:
                return next(iter(self.vaults.values()))
            raise ToolError(f"several vaults are open, pass `vault` (one of: {', '.join(self.vaults)})")
        if name not in self.vaults:
            raise ToolError(f"unknown vault {name!r} (open: {', '.join(self.vaults)})")
        return self.vaults[name]

    @staticmethod
    def _resolve(notes: dict[str, Note], ref: str) -> Note | None:
        """Find a note by vault-relative path (with or without .md) or by title (wikilink style)."""
        ref = ref.strip().replace("\\", "/")
        if not ref:
            return None
        if ref in notes:
            return notes[ref]
        if f"{ref}.md" in notes:
            return notes[f"{ref}.md"]
        low = ref.removesuffix(".md").lower()
        by_path = [n for p, n in notes.items() if p.removesuffix(".md").lower() == low]
        if by_path:
            return by_path[0]
        by_title = [n for n in notes.values() if n.title.lower() == low]
        return min(by_title, key=lambda n: n.path) if by_title else None

    def _note(self, vault: Vault, ref: str) -> Note:
        if not isinstance(ref, str) or not ref.strip():
            raise ToolError("`note` must be a non-empty string")
        pure = PurePosixPath(ref.replace("\\", "/"))
        if pure.is_absolute() or ".." in pure.parts or (len(ref) > 1 and ref[1] == ":"):
            raise ToolError("`note` must be a path relative to the vault root")
        note = self._resolve(vault.notes, ref)
        if note is None:
            raise ToolError(f"note not found in vault {vault.name!r}: {ref}")
        return note

    # -- tools ----------------------------------------------------------------

    def list_vaults(self) -> dict[str, Any]:
        return {"vaults": [{"name": v.name, "path": str(v.root.resolve()), "notes": len(v.notes)}
                           for v in self.vaults.values()]}

    def search_vault(self, query: str, k: int = 5, vault: str | None = None) -> dict[str, Any]:
        if not isinstance(query, str) or not query.strip():
            raise ToolError("`query` must be a non-empty string")
        if not isinstance(k, int) or isinstance(k, bool) or k < 1:
            raise ToolError("`k` must be a positive integer")
        v = self._vault(vault)
        allowed = v.notes
        hits = [h for h in v.engine.search(query, k=min(k, MAX_K)) if h.note_path in allowed]
        return {"vault": v.name, "query": query,
                "hits": [asdict(h) | {"anchor": h.anchor, "title": allowed[h.note_path].title} for h in hits]}

    def read_note(self, note: str, vault: str | None = None) -> dict[str, Any]:
        v = self._vault(vault)
        n = self._note(v, note)
        return {"vault": v.name, "path": n.path, "title": n.title, "tags": n.tags,
                "frontmatter": _jsonable(n.meta), "links": n.links, "content": n.body}

    def related_notes(self, note: str, vault: str | None = None) -> dict[str, Any]:
        v = self._vault(vault)
        notes = v.notes
        n = self._note(v, note)
        outgoing: dict[str, Note] = {}
        unresolved: list[str] = []
        for target in n.links:
            t = self._resolve(notes, target)
            if t is None:
                if target not in unresolved:
                    unresolved.append(target)
            elif t.path != n.path:
                outgoing.setdefault(t.path, t)
        backlinks = {o.path: o for o in notes.values()
                     if o.path != n.path and any(self._resolve(notes, t) is n for t in o.links)}
        related = []
        for path in sorted(outgoing.keys() | backlinks.keys()):
            direction = ("both" if path in outgoing and path in backlinks
                         else "outgoing" if path in outgoing else "backlink")
            related.append({"path": path, "title": notes[path].title, "direction": direction})
        return {"vault": v.name, "path": n.path, "related": related, "unresolved_links": unresolved}


def _jsonable(obj: Any) -> Any:
    return json.loads(json.dumps(obj, default=str))


# -- MCP protocol --------------------------------------------------------------

_VAULT_PROP = {"type": "string", "description": "Vault name from list_vaults; optional if only one vault is open."}
_NOTE_PROP = {"type": "string", "description": "Vault-relative note path (e.g. 'Kochen/Shakshuka.md') or note title."}
_READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}

TOOLS: list[dict[str, Any]] = [
    {
        "name": "search_vault",
        "description": "Search an Obsidian vault. Returns note-level, deduplicated hits with the best "
                       "matching heading, a snippet and per-stage scores.",
        "inputSchema": {"type": "object", "properties": {
            "query": {"type": "string", "description": "Natural-language or keyword query."},
            "k": {"type": "integer", "minimum": 1, "maximum": MAX_K, "default": 5,
                  "description": "Number of notes to return."},
            "vault": _VAULT_PROP,
        }, "required": ["query"], "additionalProperties": False},
    },
    {
        "name": "read_note",
        "description": "Read one note's full markdown body plus frontmatter, tags and outgoing wikilinks.",
        "inputSchema": {"type": "object", "properties": {"note": _NOTE_PROP, "vault": _VAULT_PROP},
                        "required": ["note"], "additionalProperties": False},
    },
    {
        "name": "related_notes",
        "description": "Notes connected to a note via [[wikilinks]]: outgoing links and backlinks.",
        "inputSchema": {"type": "object", "properties": {"note": _NOTE_PROP, "vault": _VAULT_PROP},
                        "required": ["note"], "additionalProperties": False},
    },
    {
        "name": "list_vaults",
        "description": "List the vaults this server exposes, with their note counts.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
]
for _t in TOOLS:
    _t["annotations"] = _READ_ONLY


class Server:
    def __init__(self, tools: VaultTools):
        self.tools = tools

    def handle(self, msg: Any) -> dict[str, Any] | None:
        """Handle one JSON-RPC message; returns the response, or None for notifications."""
        if not isinstance(msg, dict) or msg.get("jsonrpc") != "2.0" or not isinstance(msg.get("method"), str):
            if isinstance(msg, dict) and "method" not in msg:
                return None  # a response to us — we never send requests, ignore
            return _error(msg.get("id") if isinstance(msg, dict) else None, -32600, "Invalid Request")
        method, params, is_request = msg["method"], msg.get("params") or {}, "id" in msg
        if not is_request:
            return None  # notifications/initialized, notifications/cancelled, …
        rid = msg["id"]
        try:
            if method == "initialize":
                return _result(rid, self._initialize(params))
            if method == "ping":
                return _result(rid, {})
            if method == "tools/list":
                return _result(rid, {"tools": TOOLS})
            if method == "tools/call":
                return _result(rid, self._call(params))
            return _error(rid, -32601, f"Method not found: {method}")
        except _InvalidParams as e:
            return _error(rid, -32602, str(e))
        except Exception as e:  # keep the server alive whatever happens
            print(f"[vrag mcp] internal error in {method}: {e!r}", file=sys.stderr)
            return _error(rid, -32603, "Internal error")

    @staticmethod
    def _initialize(params: dict) -> dict[str, Any]:
        requested = params.get("protocolVersion")
        version = requested if requested in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0]
        return {
            "protocolVersion": version,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "vrag", "version": __version__},
            "instructions": "Read-only access to the user's Obsidian vault(s). Use search_vault to find "
                            "notes, read_note to read one, related_notes to follow [[wikilinks]].",
        }

    def _call(self, params: dict) -> dict[str, Any]:
        name, args = params.get("name"), params.get("arguments") or {}
        if name not in {t["name"] for t in TOOLS}:
            raise _InvalidParams(f"Unknown tool: {name}")
        if not isinstance(args, dict):
            raise _InvalidParams("`arguments` must be an object")
        try:
            data = getattr(self.tools, name)(**args)
        except TypeError as e:  # missing / unexpected arguments
            return _tool_result({"error": f"bad arguments for {name}: {e}"}, error=True)
        except ToolError as e:
            return _tool_result({"error": str(e)}, error=True)
        return _tool_result(data)

    def serve(self, stdin: IO[str], stdout: IO[str]) -> None:
        for line in stdin:
            if not line.strip():
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                resp = _error(None, -32700, "Parse error")
            else:
                resp = self.handle(msg)
            if resp is not None:
                stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
                stdout.flush()


class _InvalidParams(Exception):
    pass


def _result(rid: Any, result: dict) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": rid, "result": result}


def _error(rid: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": message}}


def _tool_result(data: dict, error: bool = False) -> dict[str, Any]:
    text = json.dumps(data, ensure_ascii=False, indent=2)
    return {"content": [{"type": "text", "text": text}], "structuredContent": data, "isError": error}


def run(specs: list[str], config: Config) -> int:
    try:
        tools = VaultTools.from_specs(specs, config)
    except (FileNotFoundError, ValueError) as e:
        print(f"[vrag mcp] {e}", file=sys.stderr)
        return 1
    # stdout is the protocol channel: keep it UTF-8 and line-buffered, never print to it
    sys.stdin.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)  # type: ignore[union-attr]
    print(f"[vrag mcp] serving {', '.join(f'{v.name}={v.root}' for v in tools.vaults.values())}",
          file=sys.stderr)
    Server(tools).serve(sys.stdin, sys.stdout)
    return 0
