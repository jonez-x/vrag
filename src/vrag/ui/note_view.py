"""Full-note view: opened from a search hit, scrolled to the matching heading."""

from __future__ import annotations

import re

from rich.text import Text
from textual import on
from textual._slug import slug
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Footer, Markdown, Static

from ..vault import Note

WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|([^\]]+))?\]\]")


def render_header(note: Note, heading: str, backlinks: list[str]) -> Text:
    out = Text()
    out.append(note.title, style="bold #A88BFA")
    out.append(f"\n{note.path}", style="dim")
    if heading:
        out.append("\nmatch  ", style="bold")
        out.append(heading, style="#A88BFA")
    if note.tags:
        out.append("\n" + "  ".join(f"#{t}" for t in note.tags), style="#8A5CF5")
    if note.links:
        out.append("\nlinks  ", style="bold")
        out.append(", ".join(dict.fromkeys(note.links)))
    if backlinks:
        out.append("\nlinked from  ", style="bold")
        out.append(", ".join(backlinks))
    return out


def wikilinks_to_markdown(body: str) -> str:
    """Show [[Target|Alias]] as emphasised text; Markdown would print the brackets verbatim."""
    return WIKILINK_RE.sub(lambda m: f"*{(m.group(2) or m.group(1)).strip()}*", body)


class NoteScreen(ModalScreen[None]):
    CSS = """
    NoteScreen { align: center middle; }
    #note-box { width: 90%; height: 90%; background: $surface; border: wide $primary 40%; }
    #note-header { height: auto; padding: 1 2; background: $panel; }
    #note-body { height: 1fr; padding: 0 1; }
    """
    BINDINGS = [
        Binding("escape", "dismiss", "Back"),
        Binding("q", "dismiss", "Back", show=False),
    ]

    def __init__(self, note: Note, heading: str = "", backlinks: list[str] | None = None):
        super().__init__()
        self.note = note
        self.heading = heading
        self.backlinks = backlinks or []

    def compose(self) -> ComposeResult:
        with Vertical(id="note-box"):
            yield Static(render_header(self.note, self.heading, self.backlinks), id="note-header")
            with VerticalScroll(id="note-body"):
                yield Markdown(wikilinks_to_markdown(self.note.body))
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#note-body").focus()

    @on(Markdown.TableOfContentsUpdated)
    def _goto_heading(self) -> None:
        # headings exist only once the document is parsed and laid out; jump to the hit's section then
        if self.heading:
            self.call_after_refresh(self.query_one(Markdown).goto_anchor, slug(self.heading))
