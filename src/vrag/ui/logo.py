"""vrag logo + Obsidian-inspired Textual theme."""

from rich.color import Color
from rich.text import Text
from textual.theme import Theme
from textual.widgets import Static

LOGO = (
    "█ █ █▀█ ▄▀█ █▀▀",
    "▀▄▀ █▀▄ █▀█ █▄█",
)

# Obsidian-like purple gradient (deep → accent → light)
GRADIENT = ("#6C31E3", "#8A5CF5", "#A88BFA")

OBSIDIAN_THEME = Theme(
    name="obsidian",
    primary="#8A5CF5",
    secondary="#A88BFA",
    accent="#6C31E3",
    foreground="#DADADA",
    background="#1E1E1E",
    surface="#262626",
    panel="#2A2A2A",
    success="#4ADE80",
    warning="#E0AF68",
    error="#FB464C",
    dark=True,
)


def _lerp(c1: str, c2: str, t: float) -> str:
    a = Color.parse(c1).get_truecolor()
    b = Color.parse(c2).get_truecolor()
    r, g, bl = (round(x + (y - x) * t) for x, y in zip(a, b))
    return f"#{r:02X}{g:02X}{bl:02X}"


def _color_at(t: float) -> str:
    """Color along the multi-stop gradient, t in [0, 1]."""
    seg = t * (len(GRADIENT) - 1)
    i = min(int(seg), len(GRADIENT) - 2)
    return _lerp(GRADIENT[i], GRADIENT[i + 1], seg - i)


def render_logo() -> Text:
    width = max(len(line) for line in LOGO)
    text = Text()
    for row, line in enumerate(LOGO):
        for col, ch in enumerate(line):
            text.append(ch, style=f"bold {_color_at(col / (width - 1))}")
        if row < len(LOGO) - 1:
            text.append("\n")
    return text


class Logo(Static):
    """Header logo. Usage: yield Logo() in compose()."""

    DEFAULT_CSS = "Logo { width: auto; height: 2; padding: 0 1; }"

    def __init__(self, **kwargs) -> None:
        super().__init__(render_logo(), **kwargs)


if __name__ == "__main__":
    # Quick preview in the terminal: python logo.py
    from rich.console import Console

    Console().print(render_logo())
