"""Stats dashboard: heatmap + per-chapter accuracy + radar + predicted pass rate."""
from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select, case
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Card, CardReview, Chapter, Mistake, Question, QuestionAttempt, StudySession


router = APIRouter(prefix="/stats", tags=["stats"])


# Exam blueprint weights — approximate share of 综合知识 by book.
BOOK_WEIGHTS = {1: 0.10, 2: 0.40, 3: 0.35, 4: 0.15}

# 4-dimension radar mapping (chapter_no → dimension).
RADAR_DIMS = {
    "规划方法": [4, 5, 6, 7, 8, 9, 10],
    "管理能力": [11, 12, 13, 14, 15, 16, 17],
    "技术基础": [1, 2, 3],
    "实践领域": [18, 19, 20, 21, 22, 23, 24],
}


def _backfill_today_session(db: Session) -> None:
    """If StudySession for today doesn't exist but there are events, create it."""
    today = date.today()
    if db.scalar(select(StudySession).where(StudySession.date == today)) is not None:
        return
    day_start = func.date(CardReview.reviewed_at)
    qday_start = func.date(QuestionAttempt.attempted_at)
    cr = db.scalar(select(func.count()).where(day_start == today.isoformat())) or 0
    qd = db.scalar(select(func.count()).where(qday_start == today.isoformat())) or 0
    if cr or qd:
        db.add(StudySession(date=today, cards_reviewed=cr, questions_done=qd, minutes=0))
        db.commit()


@router.get("/", response_class=HTMLResponse)
def stats_index(request: Request, db: Session = Depends(get_db)):
    from app.main import templates

    _backfill_today_session(db)

    # Last 90 days of heatmap data.
    today = date.today()
    start = today - timedelta(days=89)

    # Aggregate by day from actual event tables (more accurate than StudySession alone).
    card_by_day = dict(db.execute(
        select(func.date(CardReview.reviewed_at), func.count())
        .where(func.date(CardReview.reviewed_at) >= start.isoformat())
        .group_by(func.date(CardReview.reviewed_at))
    ).all())
    q_by_day = dict(db.execute(
        select(func.date(QuestionAttempt.attempted_at), func.count())
        .where(func.date(QuestionAttempt.attempted_at) >= start.isoformat())
        .group_by(func.date(QuestionAttempt.attempted_at))
    ).all())

    heatmap = []
    for i in range(90):
        d = start + timedelta(days=i)
        ds = d.isoformat()
        heatmap.append({
            "date": ds,
            "cards": int(card_by_day.get(ds, 0)),
            "questions": int(q_by_day.get(ds, 0)),
        })

    # Per-chapter accuracy (verified MCQs only).
    chapter_rows = db.execute(
        select(
            Chapter.id, Chapter.chapter_no, Chapter.title,
            func.count(QuestionAttempt.id).label("attempts"),
            func.sum(case((QuestionAttempt.correct == True, 1), else_=0)).label("correct"),  # noqa: E712
        )
        .join(Question, Question.chapter_id == Chapter.id, isouter=True)
        .join(QuestionAttempt, QuestionAttempt.question_id == Question.id, isouter=True)
        .group_by(Chapter.id)
        .order_by(Chapter.chapter_no)
    ).all()

    per_chapter = []
    for cid, cno, title, attempts, correct in chapter_rows:
        attempts = int(attempts or 0)
        correct = int(correct or 0)
        per_chapter.append({
            "chapter_no": cno,
            "title": title,
            "attempts": attempts,
            "correct": correct,
            "accuracy": (correct / attempts * 100) if attempts else None,
        })

    # Totals.
    total_cards = db.scalar(select(func.count()).select_from(Card)) or 0
    total_reviews = db.scalar(select(func.count()).select_from(CardReview)) or 0
    total_attempts = db.scalar(select(func.count()).select_from(QuestionAttempt)) or 0
    total_correct = db.scalar(
        select(func.count()).select_from(QuestionAttempt).where(QuestionAttempt.correct == True)  # noqa: E712
    ) or 0
    open_mistakes = db.scalar(
        select(func.count()).select_from(Mistake).where(Mistake.mastered == False)  # noqa: E712
    ) or 0

    # Streak (consecutive days with activity).
    streak = 0
    cur = today
    while True:
        ds = cur.isoformat()
        if card_by_day.get(ds, 0) + q_by_day.get(ds, 0) > 0:
            streak += 1
            cur = cur - timedelta(days=1)
        else:
            break

    # Radar by 4 dimensions.
    chapter_acc = {r["chapter_no"]: r["accuracy"] for r in per_chapter if r["accuracy"] is not None}
    radar = []
    for dim_name, chs in RADAR_DIMS.items():
        accs = [chapter_acc[c] for c in chs if c in chapter_acc]
        radar.append({"dim": dim_name, "accuracy": sum(accs) / len(accs) if accs else 0,
                      "covered": len(accs), "total": len(chs)})

    # Predicted pass rate (综合知识): weighted by book share, fallback to neutral for untested books.
    book_acc = {}
    for r in per_chapter:
        if r["accuracy"] is None:
            continue
        ch = next((c for c in BOOK_WEIGHTS.keys()), None)  # placeholder
    book_groups: dict[int, list[float]] = {}
    book_of_ch = {r["chapter_no"]: None for r in per_chapter}
    # Need book from Chapter table.
    book_map = dict(db.execute(select(Chapter.chapter_no, Chapter.book)).all())
    for r in per_chapter:
        if r["accuracy"] is not None:
            b = book_map.get(r["chapter_no"])
            if b:
                book_groups.setdefault(b, []).append(r["accuracy"])
    pred = 0.0
    covered_weight = 0.0
    for b, w in BOOK_WEIGHTS.items():
        accs = book_groups.get(b, [])
        if not accs:
            continue
        pred += (sum(accs) / len(accs)) * w
        covered_weight += w
    if covered_weight > 0:
        pred = pred / covered_weight  # rescale to 0-100 ignoring untested books
    # Project to 75-point scale.
    pred_score_75 = pred / 100 * 75
    predicted_pass = pred_score_75 >= 45

    return templates.TemplateResponse(
        request, "stats.html",
        {
            "heatmap": heatmap,
            "per_chapter": per_chapter,
            "radar": radar,
            "pred_pct": pred,
            "pred_score_75": pred_score_75,
            "predicted_pass": predicted_pass,
            "covered_weight": covered_weight * 100,
            "total_cards": total_cards,
            "total_reviews": total_reviews,
            "total_attempts": total_attempts,
            "total_correct": total_correct,
            "overall_accuracy": (total_correct / total_attempts * 100) if total_attempts else None,
            "open_mistakes": open_mistakes,
            "streak": streak,
            "today": today.isoformat(),
        },
    )
