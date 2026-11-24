"""Vault selection on the command line: where the vault comes from, and that it is remembered."""

import json
from pathlib import Path

import pytest

from vrag import cli
from vrag.ui import state

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "vaults" / "sample"


@pytest.fixture
def elsewhere(tmp_path, monkeypatch):
    """A working directory that is neither the repo nor a vault."""
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    return cwd


def search_paths(capsys, *argv) -> list[str]:
    assert cli.main(["search", "Sauerteig", "--json", *argv]) == 0
    return [h["note_path"] for h in json.loads(capsys.readouterr().out)]


def test_vault_option_works_after_the_command_and_is_remembered(elsewhere, capsys):
    assert search_paths(capsys, "--vault", str(SAMPLE))  # after the subcommand
    assert state.VaultRegistry.for_user().active == str(SAMPLE)
    assert search_paths(capsys)  # no --vault: the remembered one, from any directory


def test_vault_option_before_the_command_and_tilde(elsewhere, capsys, monkeypatch):
    monkeypatch.setenv("HOME", str(SAMPLE.parent))
    assert cli.main(["-v", "~/sample", "search", "Sauerteig"]) == 0
    assert state.VaultRegistry.for_user().active == str(SAMPLE)


def test_current_folder_is_used_when_it_is_an_obsidian_vault(tmp_path, monkeypatch, capsys):
    vault = tmp_path / "Notes"
    (vault / ".obsidian").mkdir(parents=True)
    (vault / "Brot.md").write_text("# Brot\nSauerteig füttern.", encoding="utf-8")
    monkeypatch.chdir(vault)
    assert search_paths(capsys) == ["Brot.md"]


def test_env_var_beats_remembered_vault(elsewhere, capsys, monkeypatch, tmp_path):
    other = tmp_path / "other"
    other.mkdir()
    (other / "Brot.md").write_text("# Brot\nSauerteig.", encoding="utf-8")
    state.VaultRegistry.for_user().activate(str(SAMPLE))
    monkeypatch.setenv("VRAG_VAULT", str(other))
    assert search_paths(capsys) == ["Brot.md"]
    assert state.VaultRegistry.for_user().active == str(SAMPLE)  # env is per shell, not remembered


def test_no_vault_known_explains_how_to_pass_one(elsewhere):
    with pytest.raises(SystemExit) as exc:
        cli.main(["search", "x"])
    assert "vrag tui ~/Notes" in str(exc.value.code)


def test_missing_vault_folder_is_an_error(elsewhere):
    with pytest.raises(SystemExit) as exc:
        cli.main(["search", "x", "--vault", "nope"])
    assert "vault folder not found" in str(exc.value.code)


def test_bare_vrag_and_tui_with_path_open_the_tui(elsewhere, monkeypatch):
    opened = []
    monkeypatch.setattr("vrag.ui.app.run", lambda config_path, vault: opened.append(vault))
    cli.main([])
    cli.main(["tui", str(SAMPLE)])
    assert opened == [None, str(SAMPLE)]


def test_eval_ignores_the_remembered_vault(capsys, monkeypatch, tmp_path):
    other = tmp_path / "other"
    other.mkdir()
    state.VaultRegistry.for_user().activate(str(other))
    monkeypatch.chdir(ROOT)
    out = tmp_path / "eval"
    (out).mkdir()
    (out / "dev.jsonl").write_text((ROOT / "eval" / "dev.jsonl").read_text(encoding="utf-8"), encoding="utf-8")
    assert cli.main(["eval", "--eval-dir", str(out)]) == 0
    assert json.loads(capsys.readouterr().out)["recall@5"] > 0  # scored on the sample vault, not `other`


def test_registry_adopts_vault_list_from_working_directory(tmp_path, monkeypatch):
    legacy = tmp_path / "legacy-state"  # conftest points STATE_DIR here
    legacy.mkdir()
    (legacy / "vaults.json").write_text(json.dumps({"vaults": [str(SAMPLE)], "active": str(SAMPLE)}))
    reg = state.VaultRegistry.for_user()
    assert reg.active == str(SAMPLE) and reg.path.exists()
