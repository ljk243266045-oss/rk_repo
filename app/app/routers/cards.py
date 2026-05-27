from datetime import datetime, date
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Card, CardReview, Chapter, StudySession
from app.srs.scheduler import grade as srs_grade


router = APIRouter(prefix="/cards", tags=["cards"])


def _next_due_card(db: Session) -> Card | None:
    return db.scalar(
        select(Card)
        .where(Card.due <= datetime.utcnow())
        .order_by(Card.due.asc())
        .limit(1)
    )


def _queue_stats(db: Session) -> dict:
    now = datetime.utcnow()
    due_now = db.scalar(select(func.count()).where(Card.due <= now)) or 0
    total = db.scalar(select(func.count()).select_from(Card)) or 0
    new_cards = db.scalar(select(func.count()).where(Card.state == 0)) or 0
    return {"due_now": due_now, "total": total, "new": new_cards}


@router.get("/", response_class=HTMLResponse)
def review_page(request: Request, db: Session = Depends(get_db)):
    from app.main import templates
    card = _next_due_card(db)
    stats = _queue_stats(db)
    return templates.TemplateResponse(
        request, "card_review.html",
        {"card": card, "stats": stats},
    )


@router.post("/grade", response_class=HTMLResponse)
def grade_card(
    request: Request,
    card_id: int = Form(...),
    rating: int = Form(...),
    db: Session = Depends(get_db),
):
    from app.main import templates
    if rating not in (1, 2, 3, 4):
        raise HTTPException(400, "rating must be 1..4")
    card = db.get(Card, card_id)
    if not card:
        raise HTTPException(404, "card not found")

    new_state, log = srs_grade(
        stability=card.stability,
        difficulty=card.difficulty,
        state=card.state,
        step=card.step,
        last_review=card.last_review,
        due=card.due,
        rating=rating,
    )

    card.stability = new_state["stability"]
    card.difficulty = new_state["difficulty"]
    card.state = new_state["state"]
    card.step = new_state["step"]
    card.due = new_state["due"]
    card.last_review = new_state["last_review"]

    db.add(CardReview(card_id=card.id, **log))

    # bump today's StudySession.cards_reviewed
    today = date.today()
    ss = db.scalar(select(StudySession).where(StudySession.date == today))
    if ss is None:
        ss = StudySession(date=today, cards_reviewed=1, questions_done=0, minutes=0)
        db.add(ss)
    else:
        ss.cards_reviewed = (ss.cards_reviewed or 0) + 1
    db.commit()

    next_card = _next_due_card(db)
    stats = _queue_stats(db)
    return templates.TemplateResponse(
        request, "_card_panel.html",
        {"card": next_card, "stats": stats},
    )


@router.get("/new", response_class=HTMLResponse)
def new_card_form(request: Request, db: Session = Depends(get_db)):
    from app.main import templates
    chapters = db.scalars(select(Chapter).order_by(Chapter.chapter_no)).all()
    return templates.TemplateResponse(
        request, "card_new.html",
        {"chapters": chapters},
    )


@router.post("/new")
def create_card(
    front: str = Form(...),
    back: str = Form(...),
    chapter_id: int | None = Form(None),
    tags: str = Form(""),
    db: Session = Depends(get_db),
):
    front = front.strip()
    back = back.strip()
    if not front or not back:
        raise HTTPException(400, "front 和 back 都必填")
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] or None
    card = Card(
        chapter_id=chapter_id if chapter_id else None,
        front=front,
        back=back,
        tags=tag_list,
        source="manual",
        due=datetime.utcnow(),
    )
    db.add(card)
    db.commit()
    return RedirectResponse(url="/cards/", status_code=303)
