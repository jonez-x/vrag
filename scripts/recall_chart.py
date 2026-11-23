"""Render the recall-over-iterations chart for the README (light + dark SVG).

    uv run python scripts/recall_chart.py

Standard library only. Numbers are dev-split scores from PROGRESS.md.
"""

from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

STEPS = ["baseline", "loop/run-01", "loop/run-02"]
# metric → series → one score per step
DATA = {
    "Recall@5": {
        "default (BM25)": [0.8375, 0.95, 1.0],
        "full (BM25 + dense + graph)": [0.925, 1.0, 1.0],
    },
    "MRR@10": {
        "default (BM25)": [0.7424, 0.8833, 0.9208],
        "full (BM25 + dense + graph)": [0.8521, 0.9425, 0.9875],
    },
}
Y_MIN, Y_MAX = 0.7, 1.0

THEMES = {
    "light": {
        "surface": "#ffffff", "text": "#1f2328", "muted": "#59636e", "grid": "#d1d9e0",
        "series": ["#2a78d6", "#eb6834"],
    },
    "dark": {
        "surface": "#0d1117", "text": "#f0f6fc", "muted": "#9198a1", "grid": "#3d444d",
        "series": ["#3987e5", "#d95926"],
    },
}

W, H = 820, 330
PANEL_W, PANEL_TOP, PANEL_H = 320, 84, 190
PANEL_X = [64, 64 + PANEL_W + 80]
FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"


def _text(x: float, y: float, s: str, fill: str, size: int = 12, anchor: str = "start",
          weight: str = "normal") -> str:
    return (f'<text x="{x:.1f}" y="{y:.1f}" fill="{fill}" font-size="{size}" '
            f'text-anchor="{anchor}" font-weight="{weight}">{escape(s)}</text>')


def render(theme: str) -> str:
    t = THEMES[theme]
    series_names = list(next(iter(DATA.values())))
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" font-family="{FONT}" role="img" '
        f'aria-labelledby="title desc">',
        '<title id="title">vrag retrieval quality over loop iterations (dev split)</title>',
        '<desc id="desc">' + escape("; ".join(
            f"{metric} {name}: " + ", ".join(f"{s} {v}" for s, v in zip(STEPS, vals))
            for metric, series in DATA.items() for name, vals in series.items())) + "</desc>",
        f'<rect width="{W}" height="{H}" rx="6" fill="{t["surface"]}"/>',
        _text(24, 32, "Retrieval quality over loop iterations", t["text"], 16, weight="600"),
        _text(24, 52, "dev split, 40 queries · held-out split not yet checked", t["muted"], 12),
    ]
    # legend
    lx = W - 24
    for i, name in reversed(list(enumerate(series_names))):
        w = 7 * len(name) + 30
        lx -= w
        c = t["series"][i]
        out.append(f'<line x1="{lx}" y1="28" x2="{lx + 16}" y2="28" stroke="{c}" stroke-width="2"/>')
        out.append(f'<circle cx="{lx + 8}" cy="28" r="4" fill="{c}" stroke="{t["surface"]}" stroke-width="2"/>')
        out.append(_text(lx + 22, 32, name, t["muted"], 12))

    def ypos(v: float) -> float:
        return PANEL_TOP + PANEL_H * (Y_MAX - v) / (Y_MAX - Y_MIN)

    for px, (metric, series) in zip(PANEL_X, DATA.items()):
        out.append(_text(px, PANEL_TOP - 14, metric, t["text"], 13, weight="600"))
        for g in (0.7, 0.8, 0.9, 1.0):
            y = ypos(g)
            out.append(f'<line x1="{px}" y1="{y:.1f}" x2="{px + PANEL_W}" y2="{y:.1f}" '
                       f'stroke="{t["grid"]}" stroke-width="1"/>')
            out.append(_text(px - 8, y + 4, f"{g:.1f}", t["muted"], 11, "end"))
        xs = [px + 20 + i * (PANEL_W - 40) / (len(STEPS) - 1) for i in range(len(STEPS))]
        for x, step in zip(xs, STEPS):
            out.append(_text(x, PANEL_TOP + PANEL_H + 22, step, t["muted"], 11, "middle"))
        for i, vals in enumerate(series.values()):
            c = t["series"][i]
            pts = " ".join(f"{x:.1f},{ypos(v):.1f}" for x, v in zip(xs, vals))
            out.append(f'<polyline points="{pts}" fill="none" stroke="{c}" stroke-width="2" '
                       'stroke-linejoin="round" stroke-linecap="round"/>')
            for x, v in zip(xs, vals):
                out.append(f'<circle cx="{x:.1f}" cy="{ypos(v):.1f}" r="4" fill="{c}" '
                           f'stroke="{t["surface"]}" stroke-width="2"/>')
            # Direct labels on the first and last point only; nudge apart when they'd collide.
            other = list(series.values())[1 - i]
            for j in (0, len(vals) - 1):
                y = ypos(vals[j])
                if abs(ypos(other[j]) - y) < 14:
                    y += -10 if vals[j] >= other[j] else 16
                elif j == 0:
                    y += 18 if vals[j] < other[j] else -10
                else:
                    y += -10
                if j == len(vals) - 1 and vals[j] == other[j] and i == 1:
                    continue  # identical end values: one label is enough
                out.append(_text(xs[j], y, f"{vals[j]:.3g}" if vals[j] < 1 else "1.0",
                                 t["text"], 11, "middle"))
    out.append("</svg>")
    return "\n".join(out) + "\n"


def main() -> None:
    DOCS.mkdir(exist_ok=True)
    for theme in THEMES:
        (DOCS / f"recall-{theme}.svg").write_text(render(theme))


if __name__ == "__main__":
    main()
