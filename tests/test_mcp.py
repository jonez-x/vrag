import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from vrag.config import Config
from vrag.mcp_server import TOOLS, Server, ToolError, Vault, VaultTools

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "vaults/sample"


def write(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


@pytest.fixture
def vault(tmp_path) -> Path:
    root = tmp_path / "vault"
    write(root, "A.md", "---\ntags: [x]\n---\n# A\nLinks to [[B]] and [[Sub/C|see C]] and [[Missing]].\n")
    write(root, "B.md", "# B\nBack to [[A#A]]. Sauerteig braucht Roggenmehl.\n")
    write(root, "Sub/C.md", "# C\nNo links here.\n")
    write(root, "D.md", "# D\nAlso points at [[a]].\n")
    write(root, ".obsidian/Hidden.md", "# hidden\n")
    (tmp_path / "secret.md").write_text("top secret", encoding="utf-8")
    return root


@pytest.fixture
def tools(vault) -> VaultTools:
    return VaultTools.from_specs([str(vault)], Config())


def test_list_vaults(tools, vault):
    assert tools.list_vaults() == {"vaults": [{"name": "vault", "path": str(vault.resolve()), "notes": 4}]}


def test_search_vault(tools):
    res = tools.search_vault("Sauerteig Roggenmehl", k=3)
    assert res["hits"][0]["note_path"] == "B.md"
    assert res["hits"][0]["title"] == "B"
    assert "bm25" in res["hits"][0]["stage_scores"]


def test_search_vault_validates_input(tools):
    with pytest.raises(ToolError):
        tools.search_vault("  ")
    with pytest.raises(ToolError):
        tools.search_vault("x", k=0)


def test_read_note_by_path_and_title(tools):
    by_path = tools.read_note("Sub/C.md")
    assert by_path["path"] == "Sub/C.md" and "No links here." in by_path["content"]
    assert tools.read_note("Sub/C")["path"] == "Sub/C.md"
    a = tools.read_note("a")  # title lookup is case-insensitive
    assert a["path"] == "A.md" and a["tags"] == ["x"] and a["links"] == ["B", "Sub/C", "Missing"]
    assert not a["content"].startswith("---")


@pytest.mark.parametrize("ref", ["../secret.md", "/etc/passwd", "Sub/../../secret.md", "C:\\x.md",
                                 "..\\secret", str(Path("/tmp/secret.md"))])
def test_read_note_rejects_traversal(tools, ref):
    with pytest.raises(ToolError):
        tools.read_note(ref)


def test_read_note_never_serves_unindexed_files(tools):
    for ref in (".obsidian/Hidden.md", "Hidden", "secret", "nope.md"):
        with pytest.raises(ToolError):
            tools.read_note(ref)


@pytest.mark.skipif(sys.platform == "win32", reason="symlinks need privileges on Windows")
def test_symlink_outside_vault_is_not_served(tmp_path, vault):
    (vault / "Leak.md").symlink_to(tmp_path / "secret.md")
    t = VaultTools.from_specs([str(vault)], Config())
    with pytest.raises(ToolError):
        t.read_note("Leak.md")
    assert all(h["note_path"] != "Leak.md" for h in t.search_vault("top secret")["hits"])


def test_related_notes(tools):
    res = tools.related_notes("A.md")
    assert res["related"] == [
        {"path": "B.md", "title": "B", "direction": "both"},
        {"path": "D.md", "title": "D", "direction": "backlink"},
        {"path": "Sub/C.md", "title": "C", "direction": "outgoing"},
    ]
    assert res["unresolved_links"] == ["Missing"]
    assert tools.related_notes("Sub/C")["related"] == [{"path": "A.md", "title": "A", "direction": "backlink"}]


def test_related_notes_on_sample_vault():
    t = VaultTools.from_specs([str(SAMPLE)], Config())
    res = t.related_notes("Grundlagenausdauer")
    assert {"path": "Sport/Intervalltraining.md", "title": "Intervalltraining", "direction": "both"} \
        in res["related"]


def test_multiple_vaults_require_name(vault):
    t = VaultTools.from_specs([f"mine={vault}", f"sample={SAMPLE}"], Config())
    with pytest.raises(ToolError):
        t.read_note("A.md")
    assert t.read_note("A.md", vault="mine")["path"] == "A.md"
    with pytest.raises(ToolError):
        t.read_note("A.md", vault="nope")
    with pytest.raises(ValueError):
        VaultTools.from_specs([f"x={vault}", f"x={SAMPLE}"], Config())


def test_refuses_eval_dir_and_missing_vault(tmp_path):
    with pytest.raises(ValueError):
        VaultTools({"e": Vault("e", ROOT / "eval", Config())})
    with pytest.raises(ValueError):
        VaultTools({"r": Vault("r", ROOT, Config())})
    with pytest.raises(FileNotFoundError):
        VaultTools({"m": Vault("m", tmp_path / "missing", Config())})


def test_server_protocol(tools):
    s = Server(tools)
    init = s.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                     "params": {"protocolVersion": "2025-03-26", "capabilities": {}}})
    assert init["result"]["protocolVersion"] == "2025-03-26"
    assert s.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    listed = s.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})["result"]["tools"]
    assert {t["name"] for t in listed} == {"search_vault", "read_note", "related_notes", "list_vaults"}
    assert all(t["annotations"]["readOnlyHint"] for t in listed)
    assert s.handle({"jsonrpc": "2.0", "id": 3, "method": "nope"})["error"]["code"] == -32601
    bad = s.handle({"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "write_note"}})
    assert bad["error"]["code"] == -32602
    err = s.handle({"jsonrpc": "2.0", "id": 5, "method": "tools/call",
                    "params": {"name": "read_note", "arguments": {"note": "../secret.md"}}})
    assert err["result"]["isError"] is True
    err = s.handle({"jsonrpc": "2.0", "id": 6, "method": "tools/call",
                    "params": {"name": "read_note", "arguments": {"path": "A.md"}}})
    assert err["result"]["isError"] is True


def test_tool_schemas_match_methods():
    import inspect

    for t in TOOLS:
        params = set(inspect.signature(getattr(VaultTools, t["name"])).parameters) - {"self"}
        assert params == set(t["inputSchema"]["properties"])


def test_stdio_roundtrip():
    """Real `vrag mcp` process: initialize → tools/list → tools/call, no network."""
    msgs = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                    "clientInfo": {"name": "pytest", "version": "0"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
         "params": {"name": "search_vault", "arguments": {"query": "Anstellgut mit Roggenvollkornmehl", "k": 3}}},
    ]
    stdin = "".join(json.dumps(m) + "\n" for m in msgs)
    env = os.environ | {"PYTHONIOENCODING": "utf-8"}
    proc = subprocess.run(
        [sys.executable, "-m", "vrag.cli", "--config", str(ROOT / "config.toml"), "mcp", "--vault", str(SAMPLE)],
        input=stdin, capture_output=True, text=True, encoding="utf-8", timeout=30, env=env, cwd=ROOT,
    )
    assert proc.returncode == 0, proc.stderr
    out = [json.loads(line) for line in proc.stdout.splitlines()]
    assert [m["id"] for m in out] == [1, 2, 3]  # no reply to the notification, nothing else on stdout
    assert out[0]["result"]["serverInfo"]["name"] == "vrag"
    assert len(out[1]["result"]["tools"]) == 4
    call = out[2]["result"]
    assert call["isError"] is False
    assert json.loads(call["content"][0]["text"])["hits"][0]["note_path"] == "Kochen/Sauerteig ansetzen.md"
