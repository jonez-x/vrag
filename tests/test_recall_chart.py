import importlib.util
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _chart():
    spec = importlib.util.spec_from_file_location("recall_chart", ROOT / "scripts" / "recall_chart.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_chart_svgs_are_valid_and_up_to_date():
    chart = _chart()
    for theme in chart.THEMES:
        svg = chart.render(theme)
        root = ET.fromstring(svg)
        assert root.tag.endswith("svg")
        # 2 metrics × 2 series × 3 steps markers, plus 2 legend markers
        assert len(root.findall(".//{http://www.w3.org/2000/svg}circle")) == 14
        assert (ROOT / "docs" / f"recall-{theme}.svg").read_text() == svg, \
            "docs/ is stale: run `uv run python scripts/recall_chart.py`"


def test_chart_data_ends_at_current_dev_scores():
    data = _chart().DATA
    assert data["Recall@5"]["default (BM25)"][-1] == 1.0
    assert data["MRR@10"]["default (BM25)"][-1] == 0.9208
    assert data["MRR@10"]["full (BM25 + dense + graph)"][-1] == 0.9875
