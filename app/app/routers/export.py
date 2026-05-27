"""Export endpoints — Anki-compatible CSV (flashcards) + questions JSON dump."""
from __future__ import annotations

import csv
import io
import json
from datetime import datetime

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Card, Chapter, Question


router = APIRouter(prefix="/export", tags=["export"])


@router.get("/anki.csv")
def export_anki_csv(db: Session = Depends(get_db)):
    """Anki-importable CSV. Import in Anki: File > Import, select "Comma" separator,
    set Field 1 = Front, Field 2 = Back, Field 3 = Tags."""
    cards = db.scalars(
        select(Card)
        .join(Chapter, Chapter.id == Card.chapter_id, isouter=True)
        .order_by(Card.id)
    ).all()

    buf = io.StringIO()
    w = csv.writer(buf, quoting=csv.QUOTE_ALL)
    for c in cards:
        tags = list(c.tags or [])
        if c.chapter_id:
            ch = db.get(Chapter, c.chapter_id)
            if ch:
                tags.append(f"ch{ch.chapter_no:02d}")
                tags.append(ch.book_name.replace(" ", "_"))
        w.writerow([c.front, c.back, " ".join(tags)])

    fname = f"ruankao_cards_{datetime.now().strftime('%Y%m%d')}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@router.get("/questions.json")
def export_questions_json(db: Session = Depends(get_db)):
    """All verified questions as JSON (backup / migration purposes)."""
    qs = db.scalars(select(Question).where(Question.verified == True).order_by(Question.id)).all()  # noqa: E712
    payload = []
    for q in qs:
        payload.append({
            "id": q.id,
            "chapter_id": q.chapter_id,
            "type": q.type,
            "stem": q.stem,
            "options": q.options,
            "answer": q.answer,
            "explanation": q.explanation,
            "difficulty": q.difficulty,
            "source": q.source,
        })
    fname = f"ruankao_questions_{datetime.now().strftime('%Y%m%d')}.json"
    return StreamingResponse(
        iter([json.dumps(payload, ensure_ascii=False, indent=2)]),
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )
