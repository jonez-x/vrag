"""vrag terminal UI: Search · Vaults · Settings · Eval.

Uses only the public engine API (``Engine.index`` / ``Engine.search``). Stage
scores are rendered generically from ``Hit.stage_scores``, so new pipeline
stages (dense, graph, rerank) show up without UI changes.
"""

from __future__ import annotations

from pathlib import Path

from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.timer import Timer
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Input,
    Label,
    Sparkline,
    Static,
    Switch,
    TabbedContent,
    TabPane,
)

from ..config import Config
from ..engine import Engine, Hit
from ..evaluate import run_eval
from .config_edit import coerce, config_values, save_changes
from .logo import OBSIDIAN_THEME, Logo
from .state import STATE_DIR, EvalRecord, History, VaultRegistry, enabled_stages, git_commit

BAR_WIDTH = 20
SLOW_STAGES = ("dense", "rerank")  # a search costs ~0.3–1.5 s: wait for a typing pause instead of every key
DEBOUNCE_S = 0.35


def stage_columns(hits: list[Hit]) -> list[str]:
    """Union of stage names across hits, in first-seen order."""
    seen: dict[str, None] = {}
    for h in hits:
        seen.update(dict.fromkeys(h.stage_scores))
    return list(seen)


def render_breakdown(hit: Hit, hits: list[Hit]) -> Text:
    """Hit detail: anchor, snippet and one bar per stage (relative to the best hit)."""
    out = Text()
    out.append(hit.anchor, style="bold #A88BFA")
    out.append(f"\nscore {hit.score:.3f}\n\n", style="dim")
    out.append(hit.snippet + "\n\n")
    stages = stage_columns(hits)
    width = max((len(s) for s in stages), default=0)
    for stage in stages:
        value = hit.stage_scores.get(stage)
        best = max((abs(h.stage_scores.get(stage, 0.0)) for h in hits), default=0.0) or 1.0
        out.append(f"{stage:<{width}} ", style="bold")
        if value is None:
            out.append("·" * BAR_WIDTH + "      —\n", style="dim")
            continue
        filled = round(BAR_WIDTH * abs(value) / best)
        out.append("█" * filled, style="#8A5CF5")
        out.append("░" * (BAR_WIDTH - filled), style="#3A3A3A")
        out.append(f" {value:8.3f}\n")
    return out


def _delta(cur: float, prev: float | None) -> Text:
    if prev is None:
        return Text("")
    d = cur - prev
    style = "#4ADE80" if d > 0 else "#FB464C" if d < 0 else "dim"
    return Text(f" ({d:+.4f})", style=style)


class VragApp(App):
    TITLE = "vrag"
    CSS = """
    #topbar { height: 3; padding: 0 1; background: $panel; }
    #topbar Logo { margin-top: 0; }
    #status { width: 1fr; content-align: right middle; height: 2; color: $text-muted; }
    TabbedContent { height: 1fr; }
    #query { margin: 1 0 0 0; }
    #search-body { height: 1fr; }
    #results { width: 3fr; height: 1fr; }
    #detail { width: 2fr; height: 1fr; padding: 1 2; background: $surface; border-left: wide $primary 30%; }
    .row { height: auto; margin: 0 0 1 0; }
    .row Input { width: 1fr; }
    .row Button { margin-left: 1; }
    .section { text-style: bold; color: $secondary; margin: 1 0 0 0; }
    .field { height: 3; }
    .field Label { width: 18; padding: 1 1 0 2; }
    .field Input { width: 40; }
    #vault-table, #history { height: 1fr; }
    #eval-summary { height: auto; padding: 1 1; }
    #recall-spark { height: 3; margin: 0 1 1 1; }
    """
    BINDINGS = [
        Binding("f1", "tab('search')", "Search"),
        Binding("f2", "tab('vaults')", "Vaults"),
        Binding("f3", "tab('settings')", "Settings"),
        Binding("f4", "tab('eval')", "Eval"),
        Binding("ctrl+s", "save_settings", "Save settings"),
        Binding("ctrl+r", "run_eval", "Run eval"),
        Binding("escape", "focus_query", "Focus search", show=False),
        Binding("ctrl+q", "quit", "Quit"),
    ]

    def __init__(
        self,
        config_path: str | Path = "config.toml",
        vault: str | None = None,
        state_dir: str | Path = STATE_DIR,
        eval_dir: str | Path = "eval",
        eval_vault: str = "vaults/sample",
    ):
        super().__init__()
        self.config_path = Path(config_path)
        self.config = Config.load(self.config_path)
        self.registry = VaultRegistry(state_dir, fallback=eval_vault)
        if vault:
            self.registry.activate(vault)
        self.history = History(state_dir)
        self.eval_split = Path(eval_dir) / "dev.jsonl"  # TUI only ever runs the dev split
        self.eval_vault = eval_vault
        self.engine = Engine(self.config)
        self.hits: list[Hit] = []
        self.index_error = ""
        self._search_timer: Timer | None = None

    # ── layout ──────────────────────────────────────────────────────────
    def compose(self) -> ComposeResult:
        with Horizontal(id="topbar"):
            yield Logo()
            yield Static(id="status")
        with TabbedContent(initial="search"):
            with TabPane("Search", id="search"):
                yield Input(placeholder="Search your vault…  (Esc focuses here)", id="query")
                with Horizontal(id="search-body"):
                    yield DataTable(id="results", cursor_type="row", zebra_stripes=True)
                    yield Static("Type to search.", id="detail")
            with TabPane("Vaults", id="vaults"):
                with Horizontal(classes="row"):
                    yield Input(placeholder="/path/to/vault", id="vault-path")
                    yield Button("Add & open", id="vault-add", variant="primary")
                    yield Button("Remove", id="vault-remove", variant="error")
                yield DataTable(id="vault-table", cursor_type="row")
            with TabPane("Settings", id="settings"):
                with VerticalScroll():
                    yield from self._settings_fields()
                    with Horizontal(classes="row"):
                        yield Button("Save  ctrl+s", id="settings-save", variant="primary")
                        yield Button("Revert", id="settings-revert")
            with TabPane("Eval", id="eval"):
                with Vertical():
                    with Horizontal(classes="row"):
                        yield Button("Run dev eval  ctrl+r", id="eval-run", variant="primary")
                    yield Static(id="eval-summary")
                    yield Sparkline([], id="recall-spark")
                    yield DataTable(id="history", cursor_type="row", zebra_stripes=True)
        yield Footer()

    def _settings_fields(self) -> ComposeResult:
        for section, values in config_values(self.config).items():
            yield Label(f"[{section}]", classes="section")
            for key, value in values.items():
                with Horizontal(classes="field"):
                    yield Label(key)
                    wid = f"cfg-{section}-{key}"
                    if isinstance(value, bool):
                        yield Switch(value=value, id=wid)
                    else:
                        yield Input(str(value), id=wid)

    def on_mount(self) -> None:
        self.register_theme(OBSIDIAN_THEME)
        self.theme = "obsidian"
        self.query_one("#vault-table", DataTable).add_columns(" ", "Vault", "Status")
        self.query_one("#history", DataTable).add_columns(
            "When (UTC)", "Commit", "Stages", "Recall@5", "MRR@10", "ms/query"
        )
        self.reindex()
        self.refresh_history()
        self.query_one("#query", Input).focus()

    # ── engine ──────────────────────────────────────────────────────────
    def reindex(self) -> None:
        self.engine = Engine(self.config)
        self.index_error = ""
        if self.registry.active:
            try:
                self.engine.index(self.registry.active)
            except (FileNotFoundError, OSError) as e:
                self.index_error = str(e)
                self.notify(self.index_error, severity="error")
        self.refresh_status()
        self.refresh_vaults()
        self.run_search(self.query_one("#query", Input).value)

    def refresh_status(self) -> None:
        stages = " + ".join(enabled_stages(self.config)) or "no stages"
        vault = self.registry.active or "no vault"
        if self.index_error:
            info = Text(f"{vault} · not indexed", style="#FB464C")
        else:
            info = Text(f"{vault} · {len(self.engine.notes)} notes · {len(self.engine.chunks)} chunks")
        self.query_one("#status", Static).update(Text.assemble(info, "\n", (stages, "#A88BFA")))

    # ── search ──────────────────────────────────────────────────────────
    @on(Input.Changed, "#query")
    def _query_changed(self, event: Input.Changed) -> None:
        self._cancel_pending_search()
        if any(s in SLOW_STAGES for s in enabled_stages(self.config)):
            self._search_timer = self.set_timer(DEBOUNCE_S, self._run_pending_search)
        else:
            self.run_search(event.value)

    @on(Input.Submitted, "#query")
    def _query_submitted(self, event: Input.Submitted) -> None:
        self._cancel_pending_search()  # Enter searches right away, also when debounced
        self.run_search(event.value)

    def _run_pending_search(self) -> None:
        self._search_timer = None
        self.run_search(self.query_one("#query", Input).value)

    def _cancel_pending_search(self) -> None:
        if self._search_timer is not None:
            self._search_timer.stop()
            self._search_timer = None

    def run_search(self, query: str) -> None:
        self.hits = self.engine.search(query) if query.strip() else []
        table = self.query_one("#results", DataTable)
        table.clear(columns=True)
        stages = stage_columns(self.hits)
        table.add_columns("#", "Note", "Heading", "Score", *stages)
        for i, h in enumerate(self.hits, 1):
            cells = [f"{h.stage_scores[s]:.3f}" if s in h.stage_scores else "—" for s in stages]
            table.add_row(str(i), h.note_path, h.heading or "—", f"{h.score:.3f}", *cells, key=str(i - 1))
        detail = self.query_one("#detail", Static)
        if self.hits:
            detail.update(render_breakdown(self.hits[0], self.hits))
        else:
            detail.update("No results." if query.strip() else "Type to search.")

    @on(DataTable.RowHighlighted, "#results")
    def _hit_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.row_key.value is not None and self.hits:
            hit = self.hits[int(event.row_key.value)]
            self.query_one("#detail", Static).update(render_breakdown(hit, self.hits))

    def action_focus_query(self) -> None:
        self.query_one(TabbedContent).active = "search"
        self.query_one("#query", Input).focus()

    def action_tab(self, tab: str) -> None:
        self.query_one(TabbedContent).active = tab

    # ── vaults ──────────────────────────────────────────────────────────
    def refresh_vaults(self) -> None:
        table = self.query_one("#vault-table", DataTable)
        table.clear()
        for v in self.registry.vaults:
            active = v == self.registry.active
            if active and not self.index_error:
                status = f"{len(self.engine.notes)} notes indexed"
            else:
                status = "ok" if Path(v).is_dir() else "missing"
            table.add_row("●" if active else " ", v, status, key=v)

    @on(Button.Pressed, "#vault-add")
    @on(Input.Submitted, "#vault-path")
    def _add_vault(self) -> None:
        field = self.query_one("#vault-path", Input)
        path = field.value.strip()
        if not path:
            return
        path = str(Path(path).expanduser())
        if not Path(path).is_dir():
            self.notify(f"Not a directory: {path}", severity="error")
            return
        field.value = ""
        self.registry.activate(path)
        self.reindex()

    @on(DataTable.RowSelected, "#vault-table")
    def _open_vault(self, event: DataTable.RowSelected) -> None:
        self.registry.activate(str(event.row_key.value))
        self.reindex()

    @on(Button.Pressed, "#vault-remove")
    def _remove_vault(self) -> None:
        table = self.query_one("#vault-table", DataTable)
        if not self.registry.vaults:
            return
        key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value
        self.registry.remove(str(key))
        self.reindex()

    # ── settings ────────────────────────────────────────────────────────
    def read_settings(self) -> dict[str, dict]:
        """Values currently in the form that differ from the loaded config."""
        changes: dict[str, dict] = {}
        for section, values in config_values(self.config).items():
            for key, current in values.items():
                widget = self.query_one(f"#cfg-{section}-{key}")
                raw = widget.value
                new = raw if isinstance(widget, Switch) else coerce(raw, current)
                if new != current:
                    changes.setdefault(section, {})[key] = new
        return changes

    @on(Button.Pressed, "#settings-save")
    def action_save_settings(self) -> None:
        try:
            changes = self.read_settings()
        except ValueError as e:
            self.notify(f"Invalid value: {e}", severity="error")
            return
        if not changes:
            self.notify("No changes.")
            return
        self.config = save_changes(self.config_path, changes)
        n = sum(len(v) for v in changes.values())
        self.notify(f"Saved {n} setting(s) to {self.config_path}")
        self.reindex()

    @on(Button.Pressed, "#settings-revert")
    def revert_settings(self) -> None:
        for section, values in config_values(self.config).items():
            for key, value in values.items():
                widget = self.query_one(f"#cfg-{section}-{key}")
                widget.value = value if isinstance(widget, Switch) else str(value)

    # ── eval ────────────────────────────────────────────────────────────
    @on(Button.Pressed, "#eval-run")
    def action_run_eval(self) -> None:
        if not self.eval_split.exists():
            self.notify(f"Eval split not found: {self.eval_split}", severity="error")
            return
        self.query_one("#eval-run", Button).disabled = True
        self.query_one("#eval-summary", Static).update("Running dev eval…")
        self._eval_worker()

    @work(thread=True, exclusive=True, group="eval")
    def _eval_worker(self) -> None:
        # Eval always uses the eval vault, independent of the vault being browsed.
        try:
            engine = Engine(self.config).index(self.eval_vault)
            result = run_eval(engine, self.eval_split)
            record = EvalRecord.from_result(result, self.config, commit=git_commit())
            self.history.append(record)
            self.call_from_thread(self._eval_done, result)
        except Exception as e:  # surface any failure in the UI instead of crashing
            self.call_from_thread(self._eval_failed, str(e))

    def _eval_done(self, result: dict) -> None:
        self.query_one("#eval-run", Button).disabled = False
        self.refresh_history(result.get("failures"))

    def _eval_failed(self, message: str) -> None:
        self.query_one("#eval-run", Button).disabled = False
        self.query_one("#eval-summary", Static).update(Text(f"Eval failed: {message}", style="#FB464C"))

    def refresh_history(self, failures: list[dict] | None = None) -> None:
        records = self.history.load()
        table = self.query_one("#history", DataTable)
        table.clear()
        for r in reversed(records):
            table.add_row(
                r.timestamp.replace("T", " ")[:19], r.commit or "—", "+".join(r.stages) or "—",
                f"{r.recall_at_5:.4f}", f"{r.mrr_at_10:.4f}", f"{r.latency_ms:.2f}",
            )
        self.query_one("#recall-spark", Sparkline).data = [r.recall_at_5 for r in records]
        summary = self.query_one("#eval-summary", Static)
        if not records:
            summary.update("No eval runs yet — press ctrl+r to score the dev split.")
            return
        last = records[-1]
        prev = records[-2] if len(records) > 1 else None
        text = Text.assemble(
            ("Recall@5 ", "bold"), f"{last.recall_at_5:.4f}",
            _delta(last.recall_at_5, prev.recall_at_5 if prev else None),
            ("   MRR@10 ", "bold"), f"{last.mrr_at_10:.4f}",
            _delta(last.mrr_at_10, prev.mrr_at_10 if prev else None),
            (f"   {len(records)} run(s) · dev split · n={last.n}", "dim"),
        )
        if failures:
            text.append(f"\n\n{len(failures)} failed queries:", style="bold")
            for f in failures:
                text.append(f"\n  ✗ {f['query']}", style="#E0AF68")
                text.append(f"  want {', '.join(f['relevant'])}", style="dim")
        summary.update(text)


def run(config_path: str = "config.toml", vault: str | None = None) -> None:
    VragApp(config_path=config_path, vault=vault).run()
