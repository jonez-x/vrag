import pytest


@pytest.fixture(autouse=True)
def _isolated_user_dir(tmp_path, monkeypatch):
    # the remembered vault list is per user (~/.config/vrag); tests must never touch the real one
    monkeypatch.setenv("VRAG_HOME", str(tmp_path / "vrag-home"))
    monkeypatch.delenv("VRAG_VAULT", raising=False)
    # VaultRegistry.for_user adopts ./.vrag/vaults.json (a developer's real vaults): look at an empty one instead
    monkeypatch.setattr("vrag.ui.state.STATE_DIR", tmp_path / "legacy-state")
