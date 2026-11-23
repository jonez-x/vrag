"""Record docs/demo.gif: drive the TUI headless and rasterise each screen with Pillow.

    uv run --with pillow python scripts/demo_gif.py

Pillow is only needed here, so it is not a project dependency. The script presses
keys through Textual's pilot, renders the screen to Rich segments after every step
(the same way ``App.export_screenshot`` does) and paints those cells onto an image.
"""

from __future__ import annotations

import asyncio
import io
import os
import shutil
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from rich.cells import cell_len
from rich.console import Console
from rich.segment import Segment
from rich.style import Style

from vrag.ui.app import VragApp

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "demo.gif"
SIZE = (120, 32)  # terminal cells
FONT_SIZE = 14
FONTS = [  # (regular, bold), first pair whose regular face exists wins
    (("/System/Library/Fonts/Menlo.ttc", 0), ("/System/Library/Fonts/Menlo.ttc", 1)),
    (("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 0),
     ("/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf", 0)),
]
DEFAULT_FG = (224, 224, 224)
DEFAULT_BG = (30, 30, 30)
TYPE_MS, SHORT_MS, HOLD_MS = 70, 900, 1800

# Block elements as (x0, y0, x1, y1) fractions of the cell, drawn as rectangles so
# borders and score bars join up without font gaps.
BLOCKS = {
    "█": (0, 0, 1, 1), "▀": (0, 0, 1, 0.5), "▄": (0, 0.5, 1, 1),
    "▌": (0, 0, 0.5, 1), "▐": (0.5, 0, 1, 1), "▔": (0, 0, 1, 0.125),
    "▁": (0, 0.875, 1, 1), "▊": (0, 0, 0.75, 1), "▎": (0, 0, 0.25, 1),
    "▏": (0, 0, 0.125, 1), "▕": (0.875, 0, 1, 1),
}
SHADES = {"░": 0.25, "▒": 0.5, "▓": 0.75}


Fonts = tuple[ImageFont.FreeTypeFont, ImageFont.FreeTypeFont]


def load_fonts() -> Fonts:
    for (path, index), (bold_path, bold_index) in FONTS:
        if Path(path).exists():
            regular = ImageFont.truetype(path, FONT_SIZE, index=index)
            bold = ImageFont.truetype(bold_path, FONT_SIZE, index=bold_index) if Path(bold_path).exists() else regular
            return regular, bold
    default = ImageFont.load_default(FONT_SIZE)
    return default, default


def screen_lines(app: VragApp) -> list[list[Segment]]:
    width, height = app.size
    console = Console(width=width, height=height, file=io.StringIO(), force_terminal=True,
                      color_system="truecolor", record=True, legacy_windows=False, safe_box=False)
    console.print(app.screen._compositor.render_update(full=True, screen_stack=app._background_screens))
    return list(Segment.split_and_crop_lines(console._record_buffer, width, pad=True))[:height]


def _rgb(color, default: tuple[int, int, int]) -> tuple[int, int, int]:
    return tuple(color.get_truecolor()) if color is not None and not color.is_default else default


def _mix(a: tuple[int, ...], b: tuple[int, ...], t: float) -> tuple[int, int, int]:
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def cell_colors(style: Style | None) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    style = style or Style()
    fg, bg = _rgb(style.color, DEFAULT_FG), _rgb(style.bgcolor, DEFAULT_BG)
    if style.reverse:
        fg, bg = bg, fg
    if style.dim:
        fg = _mix(bg, fg, 0.6)
    return fg, bg


def render(lines: list[list[Segment]], fonts: Fonts) -> Image.Image:
    font = fonts[0]
    cw = round(font.getlength("M"))
    ascent, descent = font.getmetrics()
    ch = ascent + descent + 2
    img = Image.new("RGB", (SIZE[0] * cw, SIZE[1] * ch), DEFAULT_BG)
    draw = ImageDraw.Draw(img)
    for row, segments in enumerate(lines):
        y, col = row * ch, 0
        for seg in segments:
            if seg.control:
                continue
            fg, bg = cell_colors(seg.style)
            face = fonts[1] if seg.style and seg.style.bold else font
            for char in seg.text:
                w = cell_len(char)
                if not w:  # zero-width joiners etc.
                    continue
                x = col * cw
                draw.rectangle((x, y, x + w * cw - 1, y + ch - 1), fill=bg)
                if char in BLOCKS:
                    x0, y0, x1, y1 = BLOCKS[char]
                    draw.rectangle((x + x0 * cw, y + y0 * ch, x + x1 * cw - 1, y + y1 * ch - 1), fill=fg)
                elif char in SHADES:
                    draw.rectangle((x, y, x + cw - 1, y + ch - 1), fill=_mix(bg, fg, SHADES[char]))
                elif not char.isspace():
                    draw.text((x, y + 1), char, font=face, fill=fg)
                col += w
    return img


async def record() -> list[tuple[Image.Image, int]]:
    fonts = load_fonts()
    frames: list[tuple[Image.Image, int]] = []

    with tempfile.TemporaryDirectory() as tmp:
        config = Path(tmp) / "config.toml"
        shutil.copy(ROOT / "config.toml", config)
        app = VragApp(config_path=config, vault="vaults/sample", state_dir=Path(tmp) / ".vrag",
                      eval_dir="eval", eval_vault="vaults/sample")
        async with app.run_test(size=SIZE) as pilot:

            async def snap(ms: int) -> None:
                await pilot.pause()
                frames.append((render(screen_lines(app), fonts), ms))

            async def type_query(text: str) -> None:
                for char in text:
                    await pilot.press(char)
                    await snap(TYPE_MS)

            await snap(SHORT_MS)
            await type_query("wie verhindere ich overfitting")
            await snap(HOLD_MS)
            await pilot.press("tab")  # into the results table: breakdown of the top hit
            await snap(HOLD_MS)
            for _ in range(2):
                await pilot.press("down")
                await snap(HOLD_MS)

            await pilot.press("escape")
            app.query_one("#query").value = ""
            await snap(SHORT_MS)
            await type_query("fahrradkette ölen")
            await pilot.press("tab")
            await snap(HOLD_MS)

            await pilot.press("f4", "ctrl+r")
            await app.workers.wait_for_complete()
            await snap(HOLD_MS)
            await pilot.press("f3")
            await snap(HOLD_MS)
            await pilot.press("f2")
            await snap(HOLD_MS)
    return frames


def main() -> None:
    os.chdir(ROOT)  # relative paths keep local directories out of the images
    frames = asyncio.run(record())
    # one shared palette from the held frames, so every tab's colours are in it
    held = [img for img, ms in frames if ms == HOLD_MS]
    sheet = Image.new("RGB", (held[0].width, held[0].height * len(held)))
    for i, img in enumerate(held):
        sheet.paste(img, (0, i * img.height))
    palette = sheet.quantize(colors=128, method=Image.Quantize.MEDIANCUT)
    images = [img.quantize(palette=palette, dither=Image.Dither.NONE) for img, _ in frames]
    OUT.parent.mkdir(exist_ok=True)
    images[0].save(OUT, save_all=True, append_images=images[1:], duration=[ms for _, ms in frames],
                   loop=0, optimize=True, disposal=1)
    print(f"{OUT.relative_to(ROOT)}: {len(images)} frames, {OUT.stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
