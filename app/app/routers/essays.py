"""Essay training: 10 topics + AI rubric grading (75-point scale, 45 to pass)."""
from __future__ import annotations

import json
import re
from datetime import datetime

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from app.config import settings
from app.data.essay_topics import ESSAY_TOPICS
from app.db import get_db
from app.llm import client as llm
from app.llm import prompts
from app.models import Essay


router = APIRouter(prefix="/essays", tags=["essays"])


def _topic_by_key(key: str) -> dict | None:
    return next((t for t in ESSAY_TOPICS if t["key"] == key), None)


@router.get("/", response_class=HTMLResponse)
def essays_index(request: Request, db: Session = Depends(get_db)):
    from app.main import templates
    attempts = db.scalars(select(Essay).order_by(desc(Essay.submitted_at)).limit(50)).all()
    return templates.TemplateResponse(
        request, "essays_index.html",
        {"topics_list": ESSAY_TOPICS, "attempts": attempts[:10]},
    )


@router.get("/topic/{key}", response_class=HTMLResponse)
def essay_topic(key: str, request: Request, db: Session = Depends(get_db)):
    from app.main import templates
    t = _topic_by_key(key)
    if not t:
        raise HTTPException(404, "topic not found")
    return templates.TemplateResponse(
        request, "essay_topic.html",
        {"topic": t},
    )


@router.post("/topic/{key}/submit")
def essay_submit(
    key: str,
    body: str = Form(...),
    outline: str = Form(""),
    db: Session = Depends(get_db),
):
    t = _topic_by_key(key)
    if not t:
        raise HTTPException(404)
    body = body.strip()
    word_count = len(body)
    if word_count < 500:
        raise HTTPException(400, f"论文太短(当前 {word_count} 字, 至少 500 字)")

    # AI grade (use essay_grader_model — typically claude for Chinese long-form).
    messages = [
        {"role": "system", "content": prompts.ESSAY_GRADER_SYSTEM},
        {"role": "user", "content": prompts.essay_grader_prompt(t, body)},
    ]
    try:
        raw = llm.chat(messages, model=settings.essay_grader_model, temperature=0.1, max_tokens=2048)
    except Exception as e:
        raise HTTPException(500, f"AI grading failed: {e}. 是否已在 .env 配置 API key?")

    text = raw.strip()
    m = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if m:
        text = m.group(1)
    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        raise HTTPException(500, f"AI 返回的不是有效 JSON:\n{raw[:500]}")

    # Build markdown feedback.
    fb = f"## 总分:{result.get('total_score', 0)} / 75 "
    if result.get("pass"):
        fb += "✅ 及格\n\n"
    else:
        fb += "❌ 未达 45 分及格线\n\n"
    fb += "## 各维度评分\n\n"
    for d in result.get("dimensions", []):
        fb += f"### {d.get('name')} — **{d.get('score', 0)} / 15**\n\n{d.get('comment', '')}\n\n"
    fb += f"\n## 总体评语\n\n{result.get('feedback', '')}"

    essay_row = Essay(
        topic=f"[{key}] {t['title']}",
        outline_md=outline.strip() or None,
        body_md=body,
        word_count=word_count,
        ai_score=int(result.get("total_score", 0)),
        ai_feedback_md=fb,
        submitted_at=datetime.utcnow(),
    )
    db.add(essay_row)
    db.commit()
    db.refresh(essay_row)
    return RedirectResponse(f"/essays/attempts/{essay_row.id}", status_code=303)


@router.get("/attempts/{essay_id}", response_class=HTMLResponse)
def essay_attempt(essay_id: int, request: Request, db: Session = Depends(get_db)):
    from app.main import templates
    e = db.get(Essay, essay_id)
    if not e:
        raise HTTPException(404)
    return templates.TemplateResponse(
        request, "essay_result.html",
        {"e": e},
    )
