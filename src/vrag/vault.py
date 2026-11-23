"""Load an Obsidian vault: notes, frontmatter, wikilinks."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")
IGNORED_DIRS = {".obsidian", ".trash", ".git"}


@dataclass
class Note:
    path: str  # relative to vault root, posix style
    title: str
    body: str  # markdown without frontmatter
    meta: dict = field(default_factory=dict)
    links: list[str] = field(default_factory=list)  # link targets (note titles)

    @property
    def tags(self) -> list[str]:
        tags = self.meta.get("tags") or []
        return [tags] if isinstance(tags, str) else list(tags)


def parse_note(rel_path: str, text: str) -> Note:
    meta: dict = {}
    m = FRONTMATTER_RE.match(text)
    if m:
        try:
            meta = yaml.safe_load(m.group(1)) or {}
        except yaml.YAMLError:
            meta = {}
        text = text[m.end():]
    links = [t.strip() for t in WIKILINK_RE.findall(text)]
    title = Path(rel_path).stem
    return Note(path=rel_path, title=title, body=text, meta=meta, links=links)


def load_vault(root: str | Path) -> list[Note]:
    root = Path(root)
    if not root.is_dir():
        raise FileNotFoundError(f"Vault not found: {root}")
    notes = []
    for p in sorted(root.rglob("*.md")):
        if IGNORED_DIRS & set(p.relative_to(root).parts):
            continue
        rel = p.relative_to(root).as_posix()
        notes.append(parse_note(rel, p.read_text(encoding="utf-8")))
    return notes
