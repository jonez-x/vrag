"""Headless TUI tests via Textual's Pilot."""

import asyncio
from pathlib import Path

import pytest
from textual.containers import VerticalScroll
from textual.widgets import DataTable, Input, Sparkline, Static, Switch, TabbedContent

from vrag.engine import Hit
from vrag.ui.app import VragApp, render_breakdown, stage_columns
from vrag.ui.note_view import NoteScreen, wikilinks_to_markdown
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


def test_slow_stages_debounce_live_search(make_app, tmp_path):
    # dense on, Ollama unreachable → falls back to BM25, but the config still counts as slow
    config = tmp_path / "config.toml"
    text = config.read_text(encoding="utf-8")
    text = text.replace('url = "http://localhost:11434"', 'url = "http://127.0.0.1:9"')
    config.write_text(text.replace("[dense]\nenabled = false", "[dense]\nenabled = true"), encoding="utf-8")

    async def script(pilot):
        app = pilot.app
        assert app.config.dense.enabled
        table = app.query_one("#results", DataTable)
        await pilot.press(*"overfitting")
        assert table.row_count == 0  # no search per keystroke
        await pilot.pause(0.5)
        assert table.row_count > 0  # ran once after the pause
        await pilot.press("ctrl+a", "ctrl+k", *"sauerteig", "enter")
        assert table.row_count > 0 and "sauerteig" in app.hits[0].note_path.lower()
        await pilot.press(*" roggen", "ctrl+o")  # a pending search still runs behind the note view
        await pilot.pause(0.5)
        assert isinstance(app.screen, NoteScreen)
        await pilot.press("escape")
        assert app.query_one("#query", Input).value == "sauerteig roggen" and table.row_count > 0

    drive(make_app(vault=VAULT), script)


def test_wikilinks_render_as_text():
    md = wikilinks_to_markdown("Siehe [[Andere Notiz]] und [[Dritte#Teil|Alias]].")
    assert md == "Siehe *Andere Notiz* und *Alias*."


def test_open_hit_shows_full_note_at_matching_heading(make_app):
    async def script(pilot):
        app = pilot.app
        await pilot.press(*"overfitting", "tab", "enter")
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, NoteScreen)
        hit = app.hits[0]
        note = app.engine.notes[hit.note_path]
        assert screen.note is note and screen.heading == hit.heading
        header = str(screen.query_one("#note-header", Static).render())
        assert note.title in header and note.path in header
        await pilot.press("escape")
        assert not isinstance(app.screen, NoteScreen)
        await pilot.press("escape", "ctrl+o")  # also from the search box: opens the highlighted hit
        await pilot.pause()
        assert isinstance(app.screen, NoteScreen)

    drive(make_app(vault=VAULT), script)


def test_note_view_scrolls_to_matching_section_and_lists_backlinks(make_app, tmp_path):
    vault = tmp_path / "long"
    vault.mkdir()
    filler = "\n".join(f"Zeile {i} mit Fülltext." for i in range(80))
    (vault / "Lang.md").write_text(f"# Lang\n## Anfang\n{filler}\n## Zielabschnitt\nquokka\n", encoding="utf-8")
    (vault / "Verweis.md").write_text("# Verweis\nSiehe [[Lang]].", encoding="utf-8")

    async def script(pilot):
        app = pilot.app
        await pilot.press(*"quokka", "ctrl+o")
        await pilot.pause(0.3)
        screen = app.screen
        assert isinstance(screen, NoteScreen) and screen.heading == "Zielabschnitt"
        assert screen.backlinks == ["Verweis"]
        assert screen.query_one("#note-body", VerticalScroll).scroll_y > 0

    drive(make_app(vault=str(vault)), script)


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

        k1 = app.config.bm25.k1
        app.query_one("#cfg-bm25-k1", Input).value = "abc"  # invalid → not written
        await pilot.press("ctrl+s")
        assert app.config.bm25.k1 == k1

    drive(app, script)
    text = app.config_path.read_text(encoding="utf-8")
    assert "k = 2                      # results returned" in text
    assert "prefix_title = true" in text and "# vrag retrieval pipeline config." in text
    assert f"k1 = {app.config.bm25.k1}" in text


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
