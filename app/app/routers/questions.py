"""Question bank: generation trigger UI + verification review."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select, func, update, delete
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Chapter, Question


router = APIRouter(prefix="/questions", tags=["questions"])


@router.get("/", response_class=HTMLResponse)
def index(request: Request, db: Session = Depends(get_db)):
    from app.main import templates
    chapters = db.scalars(select(Chapter).order_by(Chapter.chapter_no)).all()

    # Stats per chapter.
    counts_total = dict(db.execute(
        select(Question.chapter_id, func.count()).group_by(Question.chapter_id)
    ).all())
    counts_verified = dict(db.execute(
        select(Question.chapter_id, func.count()).where(Question.verified == True).group_by(Question.chapter_id)
    ).all())

    rows = []
    for ch in chapters:
        total = counts_total.get(ch.id, 0)
        verified = counts_verified.get(ch.id, 0)
        rows.append({"ch": ch, "total": total, "verified": verified, "pending": total - verified})

    grand_total = sum(r["total"] for r in rows)
    grand_verified = sum(r["verified"] for r in rows)

    return templates.TemplateResponse(
        request, "questions_index.html",
        {"rows": rows, "grand_total": grand_total, "grand_verified": grand_verified},
    )


@router.get("/review", response_class=HTMLResponse)
def review(request: Request,
           chapter_id: int | None = Query(None),
           db: Session = Depends(get_db)):
    from app.main import templates
    stmt = select(Question).where(Question.verified == False)  # noqa: E712
    if chapter_id:
        stmt = stmt.where(Question.chapter_id == chapter_id)
    stmt = stmt.order_by(Question.id).limit(1)
    q = db.scalar(stmt)
    pending = db.scalar(
        select(func.count()).select_from(Question).where(Question.verified == False)  # noqa: E712
    ) or 0
    chapters = db.scalars(select(Chapter).order_by(Chapter.chapter_no)).all()
    return templates.TemplateResponse(
        request, "questions_review.html",
        {"q": q, "pending": pending, "chapter_id": chapter_id, "chapters": chapters},
    )


@router.post("/{qid}/verify")
def verify(qid: int, action: str = Form(...), db: Session = Depends(get_db),
           chapter_id: int | None = Form(None)):
    q = db.get(Question, qid)
    if not q:
        raise HTTPException(404)
    if action == "approve":
        q.verified = True
        db.commit()
    elif action == "reject":
        db.delete(q)
        db.commit()
    else:
        raise HTTPException(400, "action must be approve or reject")

    next_url = "/questions/review"
    if chapter_id:
        next_url += f"?chapter_id={chapter_id}"
    return RedirectResponse(next_url, status_code=303)
