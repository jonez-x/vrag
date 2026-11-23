import tomllib
from pathlib import Path

import pytest

from vrag.config import Config
from vrag.ui.config_edit import coerce, config_values, format_value, save_changes, set_value

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = """# header comment

[bm25]
enabled = true
k1 = 1.5                   # term saturation
b = 0.75

[dense]
model = "bge-m3"  # a "quoted # hash" stays
"""


def test_set_value_keeps_comments_and_alignment():
    out = set_value(SAMPLE, "bm25", "k1", 1.25)
    assert "k1 = 1.25                  # term saturation\n" in out
    assert out.replace("1.25 ", "1.5  ") == SAMPLE  # nothing else moved


def test_set_value_only_touches_its_section():
    text = "[a]\nenabled = true\n[b]\nenabled = true\n"
    assert set_value(text, "b", "enabled", False) == "[a]\nenabled = true\n[b]\nenabled = false\n"


def test_set_value_strings_and_missing_keys():
    out = set_value(SAMPLE, "dense", "model", 'nomic "v2"')
    assert tomllib.loads(out)["dense"]["model"] == 'nomic "v2"'
    assert '# a "quoted # hash" stays' in out
    out = set_value(out, "bm25", "stemming", True)
    out = set_value(out, "graph", "boost", 0.2)
    data = tomllib.loads(out)
    assert data["bm25"]["stemming"] is True and data["graph"]["boost"] == 0.2
    assert out.index("stemming") < out.index("[dense]")


def test_set_value_roundtrips_repo_config():
    text = (ROOT / "config.toml").read_text(encoding="utf-8")
    for section, values in config_values(Config.load(ROOT / "config.toml")).items():
        for key, value in values.items():
            assert set_value(text, section, key, value) == text  # same value → no diff


def test_format_and_coerce():
    assert format_value(True) == "true" and format_value(3) == "3" and format_value(0.5) == "0.5"
    assert coerce("off", True) is False and coerce(" 7 ", 1) == 7 and coerce("1e-1", 0.0) == 0.1
    with pytest.raises(ValueError):
        coerce("maybe", False)
    with pytest.raises(ValueError):
        coerce("1.5", 1)


def test_save_changes_writes_and_reloads(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text((ROOT / "config.toml").read_text(encoding="utf-8"), encoding="utf-8")
    cfg = save_changes(path, {"bm25": {"k1": 1.2}, "search": {"k": 8}})
    assert cfg.bm25.k1 == 1.2 and cfg.search.k == 8
    assert "# hard cap per chunk" in path.read_text(encoding="utf-8")
