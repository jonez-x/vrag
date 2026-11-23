from vrag.config import Config
from vrag.ui.state import EvalRecord, History, VaultRegistry, enabled_stages


def test_history_roundtrip(tmp_path):
    h = History(tmp_path / ".vrag")
    assert h.load() == []
    result = {"split": "dev", "n": 40, "recall@5": 0.8, "mrr@10": 0.7, "latency_ms": 0.1}
    h.append(EvalRecord.from_result(result, Config(), commit="abc1234"))
    with h.path.open("a") as f:
        f.write("not json\n")
    [rec] = h.load()
    assert rec.recall_at_5 == 0.8 and rec.stages == ["bm25"] and rec.commit == "abc1234"


def test_enabled_stages_follow_config():
    cfg = Config()
    cfg.graph.enabled = True
    assert enabled_stages(cfg) == ["bm25", "graph"]


def test_vault_registry(tmp_path):
    reg = VaultRegistry(tmp_path, fallback="vaults/sample")
    assert reg.vaults == ["vaults/sample"] and reg.active == "vaults/sample"
    reg.activate("/notes/work")
    reg = VaultRegistry(tmp_path, fallback="vaults/sample")
    assert reg.vaults == ["vaults/sample", "/notes/work"] and reg.active == "/notes/work"
    reg.remove("/notes/work")
    assert reg.active == "vaults/sample"
