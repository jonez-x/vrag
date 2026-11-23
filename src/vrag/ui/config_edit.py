"""Comment-preserving edits of config.toml (used by the Settings screen).

config.toml is flat: ``[section]`` tables holding scalar ``key = value`` lines.
We rewrite only the value token of a line and keep everything else — comments,
blank lines, ordering, alignment of trailing comments — byte for byte. Keys that
don't exist yet are appended at the end of their section (sections at the end
of the file). Arrays, inline tables and multi-line strings are not supported;
this is enough for the scalars defined in ``vrag.config``.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import fields, is_dataclass
from pathlib import Path

from ..config import Config

_SECTION = re.compile(r"^\s*\[([A-Za-z0-9_.-]+)\]\s*(#.*)?$")
_KEY = re.compile(r"^(\s*)([A-Za-z0-9_-]+)(\s*=\s*)(.*)$")


def format_value(value: bool | int | float | str) -> str:
    """Render a Python scalar as a TOML value."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _split_value_comment(rest: str) -> tuple[str, str]:
    """Split ``value   # comment`` into (value, '   # comment'), respecting strings."""
    quote: str | None = None
    escaped = False
    for i, ch in enumerate(rest):
        if quote:
            if escaped:
                escaped = False
            elif ch == "\\" and quote == '"':
                escaped = True
            elif ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch == "#":
            value = rest[:i].rstrip()
            return value, rest[len(value):]
    return rest.rstrip(), ""


def set_value(text: str, section: str, key: str, value: bool | int | float | str) -> str:
    """Return ``text`` with ``[section].key`` set to ``value``; comments are kept."""
    lines = text.splitlines(keepends=True)
    rendered = format_value(value)
    current: str | None = None
    last_in_section: int | None = None

    for i, line in enumerate(lines):
        body = line.rstrip("\r\n")
        if m := _SECTION.match(body):
            current = m.group(1)
            if current == section:
                last_in_section = i
            continue
        if current != section:
            continue
        if body.strip():
            last_in_section = i
        if (m := _KEY.match(body)) and m.group(2) == key:
            old, comment = _split_value_comment(m.group(4))
            # keep trailing comments aligned when the value length changes
            if comment and comment.startswith(" "):
                pad = max(1, len(old) + len(comment) - len(comment.lstrip(" ")) - len(rendered))
                comment = " " * pad + comment.lstrip(" ")
            newline = line[len(body):]
            lines[i] = f"{m.group(1)}{key}{m.group(3)}{rendered}{comment}{newline}"
            return "".join(lines)

    new_line = f"{key} = {rendered}\n"
    if last_in_section is None:  # section missing → append it
        out = "".join(lines)
        if out and not out.endswith("\n"):
            out += "\n"
        return out + f"\n[{section}]\n" + new_line
    if not lines[last_in_section].endswith("\n"):
        lines[last_in_section] += "\n"
    lines.insert(last_in_section + 1, new_line)
    return "".join(lines)


def config_values(cfg: Config) -> dict[str, dict[str, bool | int | float | str]]:
    """Flatten a Config into {section: {key: value}} (dataclass field order)."""
    out: dict[str, dict] = {}
    for f in fields(cfg):
        section = getattr(cfg, f.name)
        if is_dataclass(section):
            out[f.name] = {sf.name: getattr(section, sf.name) for sf in fields(section)}
    return out


def coerce(raw: str, like: bool | int | float | str) -> bool | int | float | str:
    """Parse user input into the type of the default value; raises ValueError."""
    raw = raw.strip()
    if isinstance(like, bool):
        if raw.lower() in {"true", "1", "yes", "on"}:
            return True
        if raw.lower() in {"false", "0", "no", "off"}:
            return False
        raise ValueError(f"expected true/false, got {raw!r}")
    if isinstance(like, int):
        return int(raw)
    if isinstance(like, float):
        return float(raw)
    return raw


def save_changes(path: str | Path, changes: dict[str, dict[str, bool | int | float | str]]) -> Config:
    """Apply ``changes`` to the file at ``path`` and return the reloaded Config."""
    path = Path(path)
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    for section, values in changes.items():
        for key, value in values.items():
            text = set_value(text, section, key, value)
    tomllib.loads(text)  # never write a file we can't read back
    path.write_text(text, encoding="utf-8")
    return Config.load(path)
