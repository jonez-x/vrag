"""Headless TUI tests via Textual's Pilot."""

import asyncio
from pathlib import Path

import pytest
from textual.widgets import DataTable, Input, Sparkline, Static, Switch, TabbedContent

from vrag.engine import Hit
from vrag.ui.app import VragApp, render_breakdown, stage_columns
from vrag.ui.state import History

ROOT = Path(__file__).resolve().parents[1]
VAULT = str(ROOT / "vaults" / "sample")


@pytest.fixture
def make_app(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text((ROOT / "config.toml").read_text(encoding="utf-8"), encoding="utf-8")

    def make(**kw) -> VragApp:
        opts = dict(config_path=config, state_dir=tmp_path / ".vrag", eval_dir=ROOT / "eval", eval_vault=VAULT)
        return VragApp(**(opts | kw))

    return make


def drive(app: VragApp, script) -> None:
    async def main():
        async with app.run_test(size=(140, 40)) as pilot:
            await script(pilot)

    asyncio.run(main())


def text_of(app: VragApp, selector: str) -> str:
    return str(app.query_one(selector, Static).render())


def test_stage_columns_and_breakdown_are_generic():
    hits = [
        Hit("a.md", "H", "snip", 2.0, {"bm25": 4.0, "dense": 0.5}),
        Hit("b.md", "", "snip", 1.0, {"bm25": 2.0, "graph": 0.1}),
    ]
    assert stage_columns(hits) == ["bm25", "dense", "graph"]
    text = render_breakdown(hits[1], hits).plain
    assert "b.md" in text and "graph" in text and "dense" in text and "—" in text
    assert "█" * 10 + "░" * 10 in text  # bm25 2.0 vs best 4.0 → half bar


def test_search_shows_hits_with_stage_scores(make_app):
    async def script(pilot):
        app = pilot.app
        assert app.query_one("#query", Input).has_focus
        await pilot.press(*"overfitting")
        table = app.query_one("#results", DataTable)
        assert table.row_count > 0
        labels = [str(c.label) for c in table.columns.values()]
        assert labels[:4] == ["#", "Note", "Heading", "Score"] and "bm25" in labels
        assert "bm25" in text_of(app, "#detail")
        await pilot.press("tab", "down")  # moving the cursor updates the breakdown
        assert app.hits[1].note_path in text_of(app, "#detail")

    drive(make_app(vault=VAULT), script)


def test_tab_bindings_switch_screens(make_app):
    async def script(pilot):
        tabs = pilot.app.query_one(TabbedContent)
        for key, tab in [("f2", "vaults"), ("f3", "settings"), ("f4", "eval"), ("f1", "search")]:
            await pilot.press(key)
            assert tabs.active == tab
        await pilot.press("f3", "escape")
        assert tabs.active == "search" and pilot.app.query_one("#query", Input).has_focus

    drive(make_app(vault=VAULT), script)


def test_settings_save_preserves_comments_and_reindexes(make_app):
    app = make_app(vault=VAULT)

    async def script(pilot):
        await pilot.press("f3")
        app.query_one("#cfg-search-k", Input).value = "2"
        app.query_one("#cfg-chunking-prefix_title", Switch).value = True
        await pilot.press("ctrl+s")
        assert app.config.search.k == 2 and app.config.chunking.prefix_title
        await pilot.press("f1", *"pasta")
        assert app.query_one("#results", DataTable).row_count <= 2

        app.query_one("#cfg-bm25-k1", Input).value = "abc"  # invalid → not written
        await pilot.press("ctrl+s")
        assert app.config.bm25.k1 == 1.5

    drive(app, script)
    text = app.config_path.read_text(encoding="utf-8")
    assert "k = 2                      # results returned" in text
    assert "prefix_title = true" in text and "# vrag retrieval pipeline config." in text
    assert "k1 = 1.5" in text


def test_vaults_add_switch_and_missing(make_app, tmp_path):
    other = tmp_path / "other"
    other.mkdir()
    (other / "Note.md").write_text("# Hallo\nWelt", encoding="utf-8")
    app = make_app(vault=VAULT)

    async def script(pilot):
        await pilot.press("f2")
        app.query_one("#vault-path", Input).value = str(other)
        await pilot.click("#vault-add")
        assert app.registry.active == str(other) and len(app.engine.notes) == 1
        assert app.query_one("#vault-table", DataTable).row_count == 2

        app.query_one("#vault-path", Input).value = str(tmp_path / "nope")
        await pilot.click("#vault-add")
        assert app.registry.active == str(other)  # rejected, nothing changed

    drive(app, script)
    assert make_app().registry.active == str(other)  # remembered in .vrag/


def test_eval_runs_dev_split_and_records_history(make_app, tmp_path):
    app = make_app(vault=VAULT)

    async def script(pilot):
        await pilot.press("f4")
        assert "No eval runs yet" in text_of(app, "#eval-summary")
        for _ in range(2):
            await pilot.press("ctrl+r")
            await app.workers.wait_for_complete()
            await pilot.pause()
        assert app.query_one("#history", DataTable).row_count == 2
        assert len(app.query_one("#recall-spark", Sparkline).data) == 2
        summary = text_of(app, "#eval-summary")
        assert "Recall@5" in summary and "(+0.0000)" in summary and "dev split" in summary

    drive(app, script)
    records = History(tmp_path / ".vrag").load()
    assert [r.split for r in records] == ["dev", "dev"]
    assert records[0].recall_at_5 == records[1].recall_at_5 > 0
