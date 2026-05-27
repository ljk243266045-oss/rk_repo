from pathlib import Path
import markdown as md_lib

from fastapi import FastAPI, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.config import settings, APP_DIR
from app.db import get_db, init_db
from app.models import Chapter, Card
from app.routers import notes, cards, ai, questions, quiz, stats, cases, essays, mock, export


app = FastAPI(title="软考备考系统", version="0.2.0")

templates = Jinja2Templates(directory=str(APP_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(APP_DIR / "static")), name="static")

app.include_router(notes.router)
app.include_router(cards.router)
app.include_router(ai.router)
app.include_router(questions.router)
app.include_router(quiz.router)
app.include_router(stats.router)
app.include_router(cases.router)
app.include_router(essays.router)
app.include_router(mock.router)
app.include_router(export.router)


def _render_md(md_text: str) -> str:
    return md_lib.markdown(
        md_text,
        extensions=["fenced_code", "tables", "toc", "sane_lists"],
        output_format="html5",
    )


templates.env.filters["md"] = _render_md


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/", response_class=HTMLResponse)
def index(request: Request, db: Session = Depends(get_db)):
    chapter_count = db.scalar(select(func.count()).select_from(Chapter)) or 0
    card_count = db.scalar(select(func.count()).select_from(Card)) or 0
    from datetime import datetime
    due_count = db.scalar(select(func.count()).where(Card.due <= datetime.utcnow())) or 0
    return templates.TemplateResponse(
        request, "index.html",
        {
            "chapter_count": chapter_count,
            "card_count": card_count,
            "due_count": due_count,
            "llm_model": settings.llm_model,
        },
    )


@app.get("/healthz")
def healthz():
    return {"ok": True}
