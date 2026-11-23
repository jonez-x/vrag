import importlib.util
from pathlib import Path

import pytest
from rich.segment import Segment
from rich.style import Style

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "docs" / "demo.gif"


def _demo():
    pytest.importorskip("PIL", reason="Pillow is script-only: uv run --with pillow pytest tests/test_demo_gif.py")
    spec = importlib.util.spec_from_file_location("demo_gif", ROOT / "scripts" / "demo_gif.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_demo_gif_is_committed_and_small():
    assert DEMO.read_bytes()[:6] == b"GIF89a"
    assert DEMO.stat().st_size < 5_000_000
    assert "docs/demo.gif" in (ROOT / "README.md").read_text()


def test_cell_colors_resolve_reverse_and_defaults():
    demo = _demo()
    assert demo.cell_colors(None) == (demo.DEFAULT_FG, demo.DEFAULT_BG)
    fg, bg = demo.cell_colors(Style(color="#ff0000", bgcolor="#000000", reverse=True))
    assert (fg, bg) == ((0, 0, 0), (255, 0, 0))


def test_render_paints_cells_and_blocks():
    demo = _demo()
    fonts = demo.load_fonts()
    lines = [[Segment("█", Style(color="#ff0000")), Segment("a", Style(color="#00ff00", bgcolor="#0000ff"))]]
    lines += [[]] * (demo.SIZE[1] - 1)
    img = demo.render(lines, fonts)
    cw = img.width // demo.SIZE[0]
    ch = img.height // demo.SIZE[1]
    assert img.getpixel((cw // 2, ch // 2)) == (255, 0, 0)  # full block fills its cell
    assert img.getpixel((cw + 1, 1)) == (0, 0, 255)  # background of the second cell
    assert img.getpixel((img.width - 1, img.height - 1)) == demo.DEFAULT_BG
