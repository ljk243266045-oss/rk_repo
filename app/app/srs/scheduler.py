"""Thin FSRS wrapper for fsrs >= 6.x.

The fsrs 6.x API:
    Scheduler().review_card(card, Rating, review_datetime=...) -> (Card, ReviewLog)
    State enum: Learning=1, Review=2, Relearning=3 (no 0)
    Rating enum: Again=1, Hard=2, Good=3, Easy=4
    Card fields: card_id, state, step, stability(None initially), difficulty(None initially),
                 due, last_review
    ReviewLog fields: card_id, rating, review_datetime, review_duration

We persist state on our own Card ORM row and replay it into a fresh fsrs.Card on each review.
We treat our DB sentinel `state == 0` (default for never-reviewed) as "new card" → State.Learning.
"""
from datetime import datetime, timezone
from typing import Tuple

from fsrs import Scheduler, Card as FCard, Rating, State


_scheduler = Scheduler()


_RATING_MAP = {
    1: Rating.Again,
    2: Rating.Hard,
    3: Rating.Good,
    4: Rating.Easy,
}


def _to_fcard(stability: float, difficulty: float, state: int, step: int,
              last_review: datetime | None, due: datetime) -> FCard:
    fcard = FCard()
    # State: 1/2/3 valid; 0 (our DB default for new) → Learning.
    try:
        fcard.state = State(state) if state in (1, 2, 3) else State.Learning
    except ValueError:
        fcard.state = State.Learning
    fcard.step = step
    fcard.stability = stability if stability and stability > 0 else None
    fcard.difficulty = difficulty if difficulty and difficulty > 0 else None
    fcard.due = due if due.tzinfo else due.replace(tzinfo=timezone.utc)
    if last_review is not None:
        fcard.last_review = last_review if last_review.tzinfo else last_review.replace(tzinfo=timezone.utc)
    return fcard


def grade(
    *,
    stability: float,
    difficulty: float,
    state: int,
    step: int,
    last_review: datetime | None,
    due: datetime,
    rating: int,
    review_datetime: datetime | None = None,
) -> Tuple[dict, dict]:
    """Apply a rating; return (new_card_state, review_log) as plain dicts.

    review_log fields are computed for our DB (FSRS 6.x ReviewLog is minimal).
    """
    if review_datetime is None:
        review_datetime = datetime.now(timezone.utc)
    elif review_datetime.tzinfo is None:
        review_datetime = review_datetime.replace(tzinfo=timezone.utc)

    fcard_before = _to_fcard(stability, difficulty, state, step, last_review, due)
    state_before = int(fcard_before.state.value)

    elapsed_days = 0.0
    if last_review is not None:
        last = last_review if last_review.tzinfo else last_review.replace(tzinfo=timezone.utc)
        elapsed_days = max(0.0, (review_datetime - last).total_seconds() / 86400.0)

    fcard, _review_log = _scheduler.review_card(
        fcard_before, _RATING_MAP[rating], review_datetime=review_datetime
    )

    scheduled_days = max(0.0, (fcard.due - review_datetime).total_seconds() / 86400.0) if fcard.due else 0.0

    new_state = {
        "stability": float(fcard.stability or 0.0),
        "difficulty": float(fcard.difficulty or 0.0),
        "state": int(fcard.state.value),
        "step": int(fcard.step or 0),
        "due": fcard.due.replace(tzinfo=None) if fcard.due else review_datetime.replace(tzinfo=None),
        "last_review": review_datetime.replace(tzinfo=None),
    }

    log = {
        "rating": rating,
        "state_before": state_before,
        "state_after": new_state["state"],
        "stability_after": new_state["stability"],
        "difficulty_after": new_state["difficulty"],
        "elapsed_days": elapsed_days,
        "scheduled_days": scheduled_days,
    }
    return new_state, log
