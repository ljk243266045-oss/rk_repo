"""Markdown chunker.

Splits markdown content into ~300–500 character chunks, respecting H2/H3
boundaries. Each chunk is prefixed with its section breadcrumb so that
the embedding captures hierarchical context (e.g. "第7章 网络环境规划 > 7.2.3 SDN").
"""
from __future__ import annotations

import re
from dataclasses import dataclass


_MAX = 500
_MIN = 120
_OVERLAP = 60

# Match `## title`, `### title` etc.
_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


@dataclass
class Chunk:
    section_path: str
    text: str

    @property
    def token_count(self) -> int:
        return len(self.text)


def _split_long(text: str, prefix: str) -> list[Chunk]:
    """Hard-split a too-long body into ~_MAX-sized windows with overlap."""
    out: list[Chunk] = []
    body = text.strip()
    if not body:
        return out
    i = 0
    while i < len(body):
        window = body[i : i + _MAX]
        out.append(Chunk(section_path=prefix, text=f"{prefix}\n{window}"))
        if i + _MAX >= len(body):
            break
        i += _MAX - _OVERLAP
    return out


def chunk_markdown(md: str, *, root_path: str = "") -> list[Chunk]:
    """Split markdown into chunks, tracking section breadcrumb.

    Chunks always begin with the breadcrumb so embedding captures context.
    """
    chunks: list[Chunk] = []
    # Maintain stack of (level, title)
    stack: list[tuple[int, str]] = []
    buf: list[str] = []

    def flush():
        if not buf:
            return
        path_segments = [root_path] if root_path else []
        path_segments += [t for _, t in stack]
        prefix = " > ".join(s for s in path_segments if s)
        body = "\n".join(buf).strip()
        if not body:
            buf.clear()
            return
        if len(body) <= _MAX:
            chunks.append(Chunk(section_path=prefix, text=f"{prefix}\n{body}"))
        else:
            chunks.extend(_split_long(body, prefix))
        buf.clear()

    for line in md.splitlines():
        m = _HEADING.match(line)
        if m:
            flush()
            level = len(m.group(1))
            title = m.group(2).strip()
            # pop deeper-or-equal headings
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, title))
            continue
        buf.append(line)
    flush()

    # Merge very short adjacent chunks under the same breadcrumb.
    merged: list[Chunk] = []
    for c in chunks:
        if merged and merged[-1].section_path == c.section_path and len(merged[-1].text) < _MIN:
            merged[-1] = Chunk(section_path=c.section_path, text=merged[-1].text + "\n" + c.text)
        else:
            merged.append(c)
    return merged
