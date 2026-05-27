"""Quiz: chapter / mixed / review modes.

A quiz session is held in URL query state (no server-side session needed):
    /quiz/start?mode=chapter&chapter_id=4&n=10  → first question
    /quiz/answer (POST) with all session params + qid + user_answer
        → returns HTMX fragment: feedback + next question (or "results" link)
"""
from __future__ import annotations

import json
import random
from datetime import datetime, date

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select, func, and_
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Card, Chapter, Mistake, Question, QuestionAttempt, StudySession
from sqlalchemy import case


router = APIRouter(prefix="/quiz", tags=["quiz"])


# ---------- helpers ----------

def _verified_questions(db: Session, *, chapter_id: int | None = None):
    stmt = select(Question).where(Question.verified == True)  # noqa: E712
    if chapter_id:
        stmt = stmt.where(Question.chapter_id == chapter_id)
    return stmt


def _pick_questions(db: Session, *, mode: str, chapter_id: int | None, n: int, exclude: list[int]):
    """Return up to n Question rows according to mode."""
    if mode == "chapter":
        if not chapter_id:
            return []
        stmt = _verified_questions(db, chapter_id=chapter_id)
    elif mode == "mixed":
        stmt = _verified_questions(db)
    elif mode == "review":
        # Pull from mistakes that aren't yet mastered.
        stmt = (
            select(Question)
            .join(Mistake, Mistake.question_id == Question.id)
            .where(Mistake.mastered == False)  # noqa: E712
            .where(Question.verified == True)  # noqa: E712
        )
        if chapter_id:
            stmt = stmt.where(Question.chapter_id == chapter_id)
    elif mode == "weak":
        # Find lowest-accuracy chapters (with at least 3 attempts),
        # then pick questions from those chapters that haven't been answered correctly recently.
        per_ch = db.execute(
            select(
                Question.chapter_id,
                func.count(QuestionAttempt.id).label("attempts"),
                func.sum(case((QuestionAttempt.correct == True, 1), else_=0)).label("correct"),  # noqa: E712
            )
            .join(QuestionAttempt, QuestionAttempt.question_id == Question.id)
            .where(Question.verified == True)  # noqa: E712
            .group_by(Question.chapter_id)
        ).all()
        scored = []
        for cid, attempts, correct in per_ch:
            attempts = int(attempts or 0)
            correct = int(correct or 0)
            if attempts >= 3 and cid is not None:
                acc = correct / attempts
                scored.append((cid, acc, attempts))
        scored.sort(key=lambda r: r[1])  # ascending accuracy
        weak_chapter_ids = [r[0] for r in scored[:5]]  # bottom 5 chapters
        if not weak_chapter_ids:
            # fallback: pick all verified
            stmt = _verified_questions(db)
        else:
            stmt = _verified_questions(db).where(Question.chapter_id.in_(weak_chapter_ids))
    else:
        return []

    if exclude:
        stmt = stmt.where(~Question.id.in_(exclude))

    rows = list(db.scalars(stmt).all())
    random.shuffle(rows)
    return rows[:n]


def _mistake_to_card_payload(q: Question) -> tuple[str, str]:
    """Build (front, back) text for an auto-created flashcard from a wrong-answered question."""
    opts = "\n".join(q.options or [])
    front = f"{q.stem}\n\n{opts}"
    explanation = q.explanation or ""
    back = f"答案: {q.answer}\n\n{explanation}".strip()
    return front, back


def _record_mistake_and_card(db: Session, q: Question):
    """Upsert Mistake; create flashcard if not already present for this question."""
    m = db.scalar(select(Mistake).where(Mistake.question_id == q.id))
    if m is None:
        m = Mistake(question_id=q.id, wrong_count=1, last_wrong_at=datetime.utcnow(), mastered=False)
        db.add(m)
    else:
        m.wrong_count += 1
        m.last_wrong_at = datetime.utcnow()
        m.mastered = False  # if user got it wrong again, reset mastered

    # Create a flashcard once per question (idempotent on tag).
    tag = f"q{q.id}"
    existing = db.scalar(
        select(Card).where(Card.tags.is_not(None)).where(func.json_extract(Card.tags, "$").contains(tag))
    )
    # SQLite JSON-contains via json_extract isn't great; fall back to manual scan if needed.
    if existing is None:
        # Manual scan: look for any card whose tags list contains "q{id}"
        all_with_tags = db.scalars(select(Card).where(Card.tags.is_not(None))).all()
        for c in all_with_tags:
            if isinstance(c.tags, list) and tag in c.tags:
                existing = c
                break

    if existing is None:
        front, back = _mistake_to_card_payload(q)
        db.add(Card(
            chapter_id=q.chapter_id,
            front=front,
            back=back,
            tags=["错题", tag],
            source="imported",
            due=datetime.utcnow(),
        ))


def _mark_mistake_mastered(db: Session, q: Question):
    m = db.scalar(select(Mistake).where(Mistake.question_id == q.id))
    if m is not None:
        m.mastered = True


def _bump_session(db: Session, *, questions_delta: int = 0, cards_delta: int = 0):
    today = date.today()
    ss = db.scalar(select(StudySession).where(StudySession.date == today))
    if ss is None:
        ss = StudySession(date=today, minutes=0, cards_reviewed=0, questions_done=0)
        db.add(ss)
    ss.questions_done = (ss.questions_done or 0) + questions_delta
    ss.cards_reviewed = (ss.cards_reviewed or 0) + cards_delta


# ---------- routes ----------

@router.get("/", response_class=HTMLResponse)
def quiz_index(request: Request, db: Session = Depends(get_db)):
    from app.main import templates

    chapters = db.scalars(select(Chapter).order_by(Chapter.chapter_no)).all()
    # Counts per chapter of verified MCQs.
    per_chapter = dict(db.execute(
        select(Question.chapter_id, func.count())
        .where(and_(Question.verified == True, Question.type == "mcq"))  # noqa: E712
        .group_by(Question.chapter_id)
    ).all())
    total_verified = sum(per_chapter.values())
    pending_review = db.scalar(
        select(func.count()).select_from(Mistake).where(Mistake.mastered == False)  # noqa: E712
    ) or 0

    return templates.TemplateResponse(
        request, "quiz_index.html",
        {
            "chapters": chapters,
            "per_chapter": per_chapter,
            "total_verified": total_verified,
            "pending_review": pending_review,
        },
    )


@router.get("/start", response_class=HTMLResponse)
def quiz_start(
    request: Request,
    mode: str = Query("chapter"),
    chapter_id: int | None = Query(None),
    n: int = Query(10, ge=1, le=75),
    db: Session = Depends(get_db),
):
    from app.main import templates

    if mode not in ("chapter", "mixed", "review", "weak"):
        raise HTTPException(400, "mode must be chapter | mixed | review | weak")

    pool = _pick_questions(db, mode=mode, chapter_id=chapter_id, n=n, exclude=[])
    if not pool:
        msg = {
            "chapter": "本章还没有审核通过的题目。先去 /questions/ 生成 + /questions/review 审核。",
            "mixed": "题库里还没有审核通过的题目。",
            "review": "🎉 没有待复习的错题。",
            "weak": "还没有足够的刷题数据(各章需 ≥3 次尝试)。先去混合模式刷题。",
        }.get(mode, "no questions")
        return templates.TemplateResponse(
            request, "quiz_empty.html",
            {"message": msg, "mode": mode},
        )

    qids = [q.id for q in pool]
    first = pool[0]

    return templates.TemplateResponse(
        request, "quiz_session.html",
        {
            "mode": mode,
            "chapter_id": chapter_id,
            "queue": qids,
            "queue_json": json.dumps(qids),
            "index": 0,
            "total": len(qids),
            "score": 0,
            "q": first,
        },
    )


@router.post("/answer", response_class=HTMLResponse)
def quiz_answer(
    request: Request,
    qid: int = Form(...),
    user_answer: str = Form(""),
    mode: str = Form(...),
    queue: str = Form(...),
    index: int = Form(...),
    score: int = Form(...),
    chapter_id: int | None = Form(None),
    time_spent_sec: int = Form(0),
    db: Session = Depends(get_db),
):
    from app.main import templates

    q = db.get(Question, qid)
    if not q:
        raise HTTPException(404, "question not found")

    correct = user_answer.strip().upper() == (q.answer or "").strip().upper()

    # Record attempt.
    db.add(QuestionAttempt(
        question_id=q.id,
        user_answer=user_answer,
        correct=correct,
        time_spent_sec=time_spent_sec,
        mode=mode,
    ))

    # Mistake handling.
    if not correct:
        _record_mistake_and_card(db, q)
    elif mode == "review":
        _mark_mistake_mastered(db, q)

    _bump_session(db, questions_delta=1)
    db.commit()

    # Determine next.
    qids = json.loads(queue)
    next_index = index + 1
    new_score = score + (1 if correct else 0)

    next_q = None
    if next_index < len(qids):
        next_q = db.get(Question, qids[next_index])

    return templates.TemplateResponse(
        request, "_quiz_feedback.html",
        {
            "q": q,
            "user_answer": user_answer,
            "correct": correct,
            "next_q": next_q,
            "mode": mode,
            "chapter_id": chapter_id,
            "queue": queue,
            "queue_json": queue,
            "index": next_index,
            "total": len(qids),
            "score": new_score,
        },
    )


@router.get("/next-fragment", response_class=HTMLResponse)
@router.post("/next-fragment", response_class=HTMLResponse)
async def quiz_next_fragment(
    request: Request,
    qid: int = Query(...),
    mode: str = Query(...),
    index: int = Query(...),
    score: int = Query(...),
    chapter_id: int | None = Query(None),
    db: Session = Depends(get_db),
):
    """Re-render the question fragment for the next item. queue passed via form body (HTMX hx-vals)."""
    from app.main import templates

    # queue comes via form body (HTMX hx-vals as JSON object → form-encoded as queue=<json>)
    form = await request.form() if request.method == "POST" else {}
    queue_raw = form.get("queue") or request.query_params.get("queue") or "[]"
    try:
        qids = json.loads(queue_raw)
    except json.JSONDecodeError:
        qids = []

    q = db.get(Question, qid)
    if not q:
        raise HTTPException(404)

    return templates.TemplateResponse(
        request, "_quiz_question.html",
        {
            "q": q,
            "mode": mode,
            "chapter_id": chapter_id,
            "queue": queue_raw,
            "queue_json": queue_raw,
            "index": index,
            "score": score,
            "total": len(qids),
        },
    )


@router.get("/results", response_class=HTMLResponse)
def quiz_results(
    request: Request,
    total: int = Query(...),
    score: int = Query(...),
    mode: str = Query("mixed"),
):
    from app.main import templates
    return templates.TemplateResponse(
        request, "quiz_results.html",
        {"total": total, "score": score, "mode": mode},
    )
