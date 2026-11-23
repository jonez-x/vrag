"""Render headless SVG screenshots of the TUI into docs/ (used by the README).

    uv run python scripts/screenshots.py
"""

import asyncio
import os
import shutil
import tempfile
from pathlib import Path

from vrag.ui.app import VragApp

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


async def main() -> None:
    os.chdir(ROOT)  # relative paths keep local directories out of the images
    DOCS.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        config = Path(tmp) / "config.toml"
        shutil.copy(ROOT / "config.toml", config)
        app = VragApp(
            config_path=config,
            vault="vaults/sample",
            state_dir=Path(tmp) / ".vrag",
            eval_dir="eval",
            eval_vault="vaults/sample",
        )
        async with app.run_test(size=(130, 34)) as pilot:
            await pilot.press(*"wie verhindere ich overfitting")
            await pilot.press("tab", "down")
            await pilot.pause()
            app.save_screenshot("tui-search.svg", str(DOCS))

            await pilot.press("f4", "ctrl+r")
            await app.workers.wait_for_complete()
            await pilot.pause()
            app.save_screenshot("tui-eval.svg", str(DOCS))

            await pilot.press("f3")
            await pilot.pause()
            app.save_screenshot("tui-settings.svg", str(DOCS))


if __name__ == "__main__":
    asyncio.run(main())
