"""Case analysis: 10 scenarios + AI rubric grading."""
from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from app.config import settings
from app.data.case_templates import CASE_TEMPLATES
from app.db import get_db
from app.llm import client as llm
from app.llm import prompts
from app.models import Case


router = APIRouter(prefix="/cases", tags=["cases"])


def _template_by_key(key: str) -> dict | None:
    return next((c for c in CASE_TEMPLATES if c["key"] == key), None)


@router.get("/", response_class=HTMLResponse)
def cases_index(request: Request, db: Session = Depends(get_db)):
    from app.main import templates

    # Past attempts (latest first)
    attempts = db.scalars(select(Case).order_by(desc(Case.submitted_at)).limit(50)).all()
    # Stats per template
    per_template = {}
    for a in attempts:
        if a.questions and isinstance(a.questions, dict):
            k = a.questions.get("_template_key")
            if k:
                per_template.setdefault(k, {"count": 0, "best": 0})
                per_template[k]["count"] += 1
                if (a.ai_score or 0) > per_template[k]["best"]:
                    per_template[k]["best"] = a.ai_score or 0

    return templates.TemplateResponse(
        request, "cases_index.html",
        {"templates_list": CASE_TEMPLATES, "per_template": per_template, "attempts": attempts[:10]},
    )


@router.get("/template/{key}", response_class=HTMLResponse)
def case_view(key: str, request: Request, db: Session = Depends(get_db)):
    from app.main import templates

    tpl = _template_by_key(key)
    if not tpl:
        raise HTTPException(404, "case template not found")
    return templates.TemplateResponse(
        request, "case_attempt.html",
        {"tpl": tpl},
    )


@router.post("/template/{key}/submit")
def case_submit(
    key: str,
    user_answer: str = Form(...),
    db: Session = Depends(get_db),
):
    tpl = _template_by_key(key)
    if not tpl:
        raise HTTPException(404, "case template not found")
    user_answer = user_answer.strip()
    if len(user_answer) < 50:
        raise HTTPException(400, "答案太短(至少 50 字)")

    # Call AI grader.
    messages = [
        {"role": "system", "content": prompts.CASE_GRADER_SYSTEM},
        {"role": "user", "content": prompts.case_grader_prompt(tpl, user_answer)},
    ]
    try:
        raw = llm.chat(messages, temperature=0.1, max_tokens=2048)
    except Exception as e:
        raise HTTPException(500, f"AI grading failed: {e}. 是否已在 .env 配置 API key?")

    # Parse JSON.
    import re
    text = raw.strip()
    m = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if m:
        text = m.group(1)
    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        raise HTTPException(500, f"AI 返回的不是有效 JSON:\n{raw[:500]}")

    # Snapshot template into the Case row so it's self-contained even if templates change.
    questions_snapshot = {
        "_template_key": key,
        "title": tpl["title"],
        "scenario": tpl["scenario"],
        "questions": tpl["questions"],
    }
    feedback_md = "## 评分结果\n\n"
    for q in result.get("questions", []):
        feedback_md += f"### 问题 {q.get('q_index')} — {q.get('score', '?')}/{q.get('max_score','?')}\n\n"
        for r in q.get("rubric_results", []):
            feedback_md += f"- {r.get('hit', '?')} **{r.get('point')}** ({r.get('earned', 0)} 分){' — ' + r['reason'] if r.get('reason') else ''}\n"
        feedback_md += "\n"
    feedback_md += f"\n## 总体评语\n\n{result.get('feedback', '')}"

    case_row = Case(
        scenario_md=tpl["scenario"],
        questions=questions_snapshot,
        user_answers=[user_answer],
        ai_score=int(result.get("total_score", 0)),
        ai_feedback_md=feedback_md,
        submitted_at=datetime.utcnow(),
    )
    db.add(case_row)
    db.commit()
    db.refresh(case_row)
    return RedirectResponse(f"/cases/attempts/{case_row.id}", status_code=303)


@router.get("/attempts/{case_id}", response_class=HTMLResponse)
def case_attempt_view(case_id: int, request: Request, db: Session = Depends(get_db)):
    from app.main import templates
    c = db.get(Case, case_id)
    if not c:
        raise HTTPException(404)
    return templates.TemplateResponse(
        request, "case_result.html",
        {"c": c, "user_answer": (c.user_answers or [""])[0]},
    )
