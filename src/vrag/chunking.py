"""Markdown-aware chunking."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .config import ChunkingConfig
from .vault import Note

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$", re.MULTILINE)


@dataclass
class Chunk:
    id: str
    note_path: str
    heading: str  # "" for the note intro
    text: str  # text that gets indexed


def _sections(body: str) -> list[tuple[str, str]]:
    """Split markdown into (heading, content) sections."""
    matches = list(HEADING_RE.finditer(body))
    if not matches:
        return [("", body)]
    sections = []
    if body[: matches[0].start()].strip():
        sections.append(("", body[: matches[0].start()]))
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        sections.append((m.group(2).strip(), body[m.start():end]))
    return sections


def _split_long(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    parts, buf = [], ""
    for para in re.split(r"\n\s*\n", text):
        if buf and len(buf) + len(para) + 2 > max_chars:
            parts.append(buf)
            buf = ""
        buf = f"{buf}\n\n{para}" if buf else para
        while len(buf) > max_chars:
            parts.append(buf[:max_chars])
            buf = buf[max_chars:]
    if buf:
        parts.append(buf)
    return parts


def chunk_note(note: Note, cfg: ChunkingConfig) -> list[Chunk]:
    sections = _sections(note.body) if cfg.split_on_headings else [("", note.body)]
    chunks = []
    for heading, content in sections:
        if not content.strip():
            continue
        for part in _split_long(content.strip(), cfg.max_chars):
            text = f"{note.title} > {heading}\n{part}" if cfg.prefix_title else part
            chunks.append(Chunk(f"{note.path}#{len(chunks)}", note.path, heading, text))
    return chunks
