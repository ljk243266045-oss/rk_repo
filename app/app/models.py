from datetime import datetime, date
from typing import Optional
from sqlalchemy import (
    String, Integer, Float, Boolean, Text, Date, DateTime, ForeignKey, JSON, UniqueConstraint, Index
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Chapter(Base):
    __tablename__ = "chapters"

    id: Mapped[int] = mapped_column(primary_key=True)
    book: Mapped[int] = mapped_column(Integer)              # 1..4 (基础/方法/能力/实践)
    book_name: Mapped[str] = mapped_column(String(32))
    chapter_no: Mapped[int] = mapped_column(Integer)        # 1..24
    title: Mapped[str] = mapped_column(String(256))
    notes_md_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    page_start: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    page_end: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content_md: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # full notes markdown

    chunks: Mapped[list["Chunk"]] = relationship(back_populates="chapter", cascade="all,delete")
    cards: Mapped[list["Card"]] = relationship(back_populates="chapter")
    questions: Mapped[list["Question"]] = relationship(back_populates="chapter")


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    chapter_id: Mapped[int] = mapped_column(ForeignKey("chapters.id", ondelete="CASCADE"))
    section_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    content: Mapped[str] = mapped_column(Text)
    token_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    source: Mapped[str] = mapped_column(String(16))   # 'notes' | 'textbook'

    chapter: Mapped[Chapter] = relationship(back_populates="chunks")


class Card(Base):
    __tablename__ = "cards"

    id: Mapped[int] = mapped_column(primary_key=True)
    chapter_id: Mapped[Optional[int]] = mapped_column(ForeignKey("chapters.id"), nullable=True)
    front: Mapped[str] = mapped_column(Text)
    back: Mapped[str] = mapped_column(Text)
    tags: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    source: Mapped[str] = mapped_column(String(16), default="manual")  # manual | ai | imported
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # FSRS state cached on card (latest values)
    stability: Mapped[float] = mapped_column(Float, default=0.0)
    difficulty: Mapped[float] = mapped_column(Float, default=0.0)
    state: Mapped[int] = mapped_column(Integer, default=0)            # FSRS State enum int
    step: Mapped[int] = mapped_column(Integer, default=0)             # learning step index
    last_review: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    due: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    chapter: Mapped[Optional[Chapter]] = relationship(back_populates="cards")
    reviews: Mapped[list["CardReview"]] = relationship(back_populates="card", cascade="all,delete")


Index("ix_cards_due", Card.due)


class CardReview(Base):
    __tablename__ = "card_reviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    card_id: Mapped[int] = mapped_column(ForeignKey("cards.id", ondelete="CASCADE"))
    reviewed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    rating: Mapped[int] = mapped_column(Integer)            # 1=again, 2=hard, 3=good, 4=easy
    state_before: Mapped[int] = mapped_column(Integer, default=0)
    state_after: Mapped[int] = mapped_column(Integer, default=0)
    stability_after: Mapped[float] = mapped_column(Float, default=0.0)
    difficulty_after: Mapped[float] = mapped_column(Float, default=0.0)
    elapsed_days: Mapped[float] = mapped_column(Float, default=0.0)
    scheduled_days: Mapped[float] = mapped_column(Float, default=0.0)

    card: Mapped[Card] = relationship(back_populates="reviews")


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    chapter_id: Mapped[Optional[int]] = mapped_column(ForeignKey("chapters.id"), nullable=True)
    type: Mapped[str] = mapped_column(String(16))         # mcq | case | essay
    stem: Mapped[str] = mapped_column(Text)
    options: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)   # list[str] for mcq
    answer: Mapped[str] = mapped_column(Text)                              # for mcq: "A"/"B"/...
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    difficulty: Mapped[int] = mapped_column(Integer, default=3)            # 1..5
    source: Mapped[str] = mapped_column(String(16), default="ai")          # ai | manual | past
    ai_model: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    chapter: Mapped[Optional[Chapter]] = relationship(back_populates="questions")
    attempts: Mapped[list["QuestionAttempt"]] = relationship(back_populates="question", cascade="all,delete")


class QuestionAttempt(Base):
    __tablename__ = "question_attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"))
    user_answer: Mapped[str] = mapped_column(Text)
    correct: Mapped[bool] = mapped_column(Boolean)
    time_spent_sec: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    mode: Mapped[str] = mapped_column(String(16), default="chapter")  # chapter | mixed | mock | review
    attempted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    question: Mapped[Question] = relationship(back_populates="attempts")


class Mistake(Base):
    __tablename__ = "mistakes"
    __table_args__ = (UniqueConstraint("question_id", name="uq_mistakes_question"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"))
    wrong_count: Mapped[int] = mapped_column(Integer, default=1)
    last_wrong_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    mastered: Mapped[bool] = mapped_column(Boolean, default=False)


class Essay(Base):
    __tablename__ = "essays"

    id: Mapped[int] = mapped_column(primary_key=True)
    topic: Mapped[str] = mapped_column(Text)
    outline_md: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    body_md: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    word_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    ai_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    ai_feedback_md: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Case(Base):
    __tablename__ = "cases"

    id: Mapped[int] = mapped_column(primary_key=True)
    scenario_md: Mapped[str] = mapped_column(Text)
    questions: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    user_answers: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    ai_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    ai_feedback_md: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class StudySession(Base):
    __tablename__ = "study_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date] = mapped_column(Date, default=date.today)
    minutes: Mapped[int] = mapped_column(Integer, default=0)
    cards_reviewed: Mapped[int] = mapped_column(Integer, default=0)
    questions_done: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class Setting(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class MockExam(Base):
    """Full-exam sim record. mode ∈ mcq|case|essay|full."""
    __tablename__ = "mock_exams"

    id: Mapped[int] = mapped_column(primary_key=True)
    mode: Mapped[str] = mapped_column(String(16))
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    duration_sec: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # question ids, answers, etc.
    score_mcq: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    score_case: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    score_essay: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    passed: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
