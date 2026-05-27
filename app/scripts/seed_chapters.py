"""Parse the consolidated chapter notes markdown and seed `chapters` + `chunks` tables.

Run once after install:
    python scripts/seed_chapters.py

Idempotent: re-runs delete existing chapters/chunks rows first.
"""
import re
import sys
from pathlib import Path

# Ensure project root on sys.path when invoked from app/.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import delete

from app.config import settings
from app.db import init_db, session_scope
from app.models import Chapter, Chunk


# Chapter → Book/篇 mapping (per 教材目录)
BOOK_OF_CHAPTER = {}
for n in range(1, 4):
    BOOK_OF_CHAPTER[n] = (1, "基础篇")
for n in range(4, 11):
    BOOK_OF_CHAPTER[n] = (2, "方法篇")
for n in range(11, 18):
    BOOK_OF_CHAPTER[n] = (3, "能力篇")
for n in range(18, 25):
    BOOK_OF_CHAPTER[n] = (4, "实践篇")


# Page-start of each chapter taken from the 教材 TOC (approximate; for display only)
PAGE_OF_CHAPTER = {
    1: 3, 2: 48, 3: 75, 4: 103, 5: 138, 6: 189, 7: 212, 8: 240,
    9: 277, 10: 305, 11: 323, 12: 348, 13: 391, 14: 427, 15: 449, 16: 462,
    17: 487, 18: 535, 19: 570, 20: 606, 21: 643, 22: 685, 23: 716, 24: 745,
}


CHAPTER_HEADING = re.compile(r"^#\s*第\s*(\d+)\s*章\s+(.+?)\s*$")
SECTION_HEADING = re.compile(r"^##\s+(.+?)\s*$")


def parse_consolidated_notes(md: str) -> list[dict]:
    """Return list of chapter dicts: {chapter_no, title, content_md, sections}."""
    lines = md.splitlines()
    chapters = []
    cur_ch: dict | None = None
    cur_section_title: str | None = None
    cur_section_buf: list[str] = []

    def flush_section():
        nonlocal cur_section_title, cur_section_buf
        if cur_ch is not None and cur_section_title is not None and cur_section_buf:
            body = "\n".join(cur_section_buf).strip()
            if body:
                cur_ch["sections"].append({"title": cur_section_title, "body": body})
        cur_section_title = None
        cur_section_buf = []

    def flush_chapter():
        nonlocal cur_ch
        if cur_ch is not None:
            flush_section()
            cur_ch["content_md"] = "\n".join(cur_ch["_raw"]).strip()
            del cur_ch["_raw"]
            chapters.append(cur_ch)
        cur_ch = None

    for line in lines:
        m_ch = CHAPTER_HEADING.match(line)
        if m_ch:
            flush_chapter()
            cur_ch = {
                "chapter_no": int(m_ch.group(1)),
                "title": m_ch.group(2).strip(),
                "sections": [],
                "_raw": [line],
            }
            continue
        if cur_ch is None:
            continue  # skip prelude (TOC etc.)

        cur_ch["_raw"].append(line)
        m_sec = SECTION_HEADING.match(line)
        if m_sec:
            flush_section()
            cur_section_title = m_sec.group(1).strip()
            continue
        if cur_section_title is not None:
            cur_section_buf.append(line)

    flush_chapter()
    return chapters


def main() -> int:
    notes_path = settings.consolidated_notes_path
    if not notes_path.exists():
        print(f"[ERROR] Consolidated notes not found: {notes_path}", file=sys.stderr)
        return 2

    md = notes_path.read_text(encoding="utf-8")
    parsed = parse_consolidated_notes(md)
    if not parsed:
        print("[ERROR] No chapters parsed; check markdown headings (`# 第N章 ...`).", file=sys.stderr)
        return 3

    init_db()

    with session_scope() as s:
        # Wipe previous seed (idempotent).
        s.execute(delete(Chunk).where(Chunk.source == "notes"))
        s.execute(delete(Chapter))
        s.flush()

        for c in parsed:
            book, book_name = BOOK_OF_CHAPTER.get(c["chapter_no"], (0, ""))
            ch = Chapter(
                book=book,
                book_name=book_name,
                chapter_no=c["chapter_no"],
                title=c["title"],
                notes_md_path=str(notes_path.name),
                page_start=PAGE_OF_CHAPTER.get(c["chapter_no"]),
                summary=next((sec["body"] for sec in c["sections"] if sec["title"] == "本章概述"), None),
                content_md=c["content_md"],
            )
            s.add(ch)
            s.flush()  # populate ch.id

            for sec in c["sections"]:
                section_path = f"第{c['chapter_no']}章 {c['title']} > {sec['title']}"
                s.add(Chunk(
                    chapter_id=ch.id,
                    section_path=section_path,
                    content=sec["body"],
                    token_count=len(sec["body"]),
                    source="notes",
                ))

            print(f"  ✓ ch{c['chapter_no']:02d} {c['title']}  ({len(c['sections'])} sections)")

    print(f"\nSeeded {len(parsed)} chapters into {settings.db_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
