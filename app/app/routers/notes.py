from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Chapter


router = APIRouter(prefix="/notes", tags=["notes"])


def chapters_by_book(db: Session) -> list[tuple[int, str, list[Chapter]]]:
    rows = db.scalars(select(Chapter).order_by(Chapter.chapter_no)).all()
    grouped: dict[int, list[Chapter]] = {}
    book_names: dict[int, str] = {}
    for r in rows:
        grouped.setdefault(r.book, []).append(r)
        book_names[r.book] = r.book_name
    return [(book, book_names[book], sorted(grouped[book], key=lambda c: c.chapter_no))
            for book in sorted(grouped.keys())]


@router.get("/", response_class=HTMLResponse)
def list_notes(request: Request, db: Session = Depends(get_db)):
    from app.main import templates
    books = chapters_by_book(db)
    return templates.TemplateResponse(
        request, "notes_index.html",
        {"books": books, "active": None},
    )


@router.get("/{chapter_no}", response_class=HTMLResponse)
def view_chapter(chapter_no: int, request: Request, db: Session = Depends(get_db)):
    from app.main import templates
    ch = db.scalar(select(Chapter).where(Chapter.chapter_no == chapter_no))
    if not ch:
        raise HTTPException(404, f"Chapter {chapter_no} not found — run scripts/seed_chapters.py first.")
    books = chapters_by_book(db)
    return templates.TemplateResponse(
        request, "notes_chapter.html",
        {"books": books, "active": ch, "content_md": ch.content_md or ""},
    )
