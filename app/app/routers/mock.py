"""Full-exam mock mode: 综合知识 75 题 × 2.5h, 案例 3 道 × 1.5h, 论文 1 篇 × 2h."""
from __future__ import annotations

import json
import random
import re
from datetime import datetime

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select, desc, func
from sqlalchemy.orm import Session

from app.config import settings
from app.data.case_templates import CASE_TEMPLATES
from app.data.essay_topics import ESSAY_TOPICS
from app.db import get_db
from app.llm import client as llm
from app.llm import prompts
from app.models import MockExam, Question


router = APIRouter(prefix="/mock", tags=["mock"])


@router.get("/", response_class=HTMLResponse)
def mock_index(request: Request, db: Session = Depends(get_db)):
    from app.main import templates
    history = db.scalars(select(MockExam).order_by(desc(MockExam.started_at)).limit(10)).all()
    mcq_available = db.scalar(
        select(func.count()).select_from(Question)
        .where(Question.verified == True).where(Question.type == "mcq")  # noqa: E712
    ) or 0
    return templates.TemplateResponse(
        request, "mock_index.html",
        {"history": history, "mcq_available": mcq_available},
    )


# ---------- 综合知识 (MCQ × 75) ----------

@router.get("/mcq/start", response_class=HTMLResponse)
def mock_mcq_start(request: Request, db: Session = Depends(get_db)):
    from app.main import templates
    pool = db.scalars(
        select(Question).where(Question.verified == True).where(Question.type == "mcq")  # noqa: E712
    ).all()
    if len(pool) < 10:
        return templates.TemplateResponse(
            request, "mock_empty.html",
            {"message": f"题库不足 10 题(当前 {len(pool)}),无法进入综合知识模拟。"},
        )
    n = min(75, len(pool))
    chosen = random.sample(pool, n)

    mock = MockExam(mode="mcq", started_at=datetime.utcnow(),
                    payload={"qids": [q.id for q in chosen]})
    db.add(mock)
    db.commit()
    db.refresh(mock)

    return templates.TemplateResponse(
        request, "mock_mcq.html",
        {"mock_id": mock.id, "questions": chosen, "duration_min": 150},  # 2.5h
    )


@router.post("/mcq/{mock_id}/submit")
def mock_mcq_submit(mock_id: int, request: Request, db: Session = Depends(get_db)):
    """Body is form-encoded: q<id>=A, q<id>=B, ..."""
    mock = db.get(MockExam, mock_id)
    if not mock or mock.mode != "mcq":
        raise HTTPException(404)

    # Sync access to FastAPI Form for many fields is awkward; use raw form parse.
    async def _parse():
        return await request.form()
    import asyncio
    form = asyncio.run(_parse())

    qids = (mock.payload or {}).get("qids", [])
    correct = 0
    answers = {}
    for qid in qids:
        ans = (form.get(f"q{qid}", "") or "").strip().upper()[:1]
        answers[qid] = ans
        q = db.get(Question, qid)
        if q and ans == (q.answer or "").upper():
            correct += 1

    total = len(qids)
    score75 = round(correct / total * 75) if total else 0
    mock.finished_at = datetime.utcnow()
    mock.duration_sec = int((mock.finished_at - mock.started_at).total_seconds())
    mock.score_mcq = score75
    mock.passed = score75 >= 45
    mock.payload = {**(mock.payload or {}), "answers": answers, "correct": correct, "total": total}
    db.commit()

    return RedirectResponse(f"/mock/{mock_id}", status_code=303)


# ---------- 案例分析 (3 cases × 1.5h) ----------

@router.get("/case/start", response_class=HTMLResponse)
def mock_case_start(request: Request, db: Session = Depends(get_db)):
    from app.main import templates
    chosen_keys = random.sample([t["key"] for t in CASE_TEMPLATES], 3)
    cases = [next(c for c in CASE_TEMPLATES if c["key"] == k) for k in chosen_keys]

    mock = MockExam(mode="case", started_at=datetime.utcnow(),
                    payload={"keys": chosen_keys})
    db.add(mock)
    db.commit()
    db.refresh(mock)

    return templates.TemplateResponse(
        request, "mock_case.html",
        {"mock_id": mock.id, "cases": cases, "duration_min": 90},
    )


@router.post("/case/{mock_id}/submit")
async def mock_case_submit(mock_id: int, request: Request, db: Session = Depends(get_db)):
    mock = db.get(MockExam, mock_id)
    if not mock or mock.mode != "case":
        raise HTTPException(404)
    form = await request.form()

    keys = (mock.payload or {}).get("keys", [])
    answers = {k: (form.get(f"ans_{k}", "") or "").strip() for k in keys}
    total_score = 0
    per_case = {}
    feedback_parts = []
    for k in keys:
        tpl = next((c for c in CASE_TEMPLATES if c["key"] == k), None)
        if not tpl:
            continue
        ans = answers.get(k, "")
        if len(ans) < 30:
            per_case[k] = {"score": 0, "note": "答案过短"}
            feedback_parts.append(f"## {tpl['title']}\n答案过短,未评分。")
            continue
        try:
            raw = llm.chat(
                [
                    {"role": "system", "content": prompts.CASE_GRADER_SYSTEM},
                    {"role": "user", "content": prompts.case_grader_prompt(tpl, ans)},
                ],
                temperature=0.1, max_tokens=2048,
            )
            txt = raw.strip()
            m = re.search(r"```(?:json)?\s*(.*?)\s*```", txt, re.DOTALL)
            if m:
                txt = m.group(1)
            result = json.loads(txt)
            score = int(result.get("total_score", 0))
            total_score += score
            per_case[k] = {"score": score, "feedback": result.get("feedback", "")}
            feedback_parts.append(f"## {tpl['title']} — {score}/25\n{result.get('feedback','')}")
        except Exception as e:
            per_case[k] = {"score": 0, "note": str(e)}
            feedback_parts.append(f"## {tpl['title']}\n评分失败:{e}")

    score75 = round(total_score / (25 * len(keys)) * 75) if keys else 0
    mock.finished_at = datetime.utcnow()
    mock.duration_sec = int((mock.finished_at - mock.started_at).total_seconds())
    mock.score_case = score75
    mock.passed = score75 >= 45
    mock.payload = {**(mock.payload or {}), "answers": answers, "per_case": per_case,
                    "feedback_md": "\n\n".join(feedback_parts)}
    db.commit()
    return RedirectResponse(f"/mock/{mock_id}", status_code=303)


# ---------- 论文 (1 of 2 topics × 2h) ----------

@router.get("/essay/start", response_class=HTMLResponse)
def mock_essay_start(request: Request, db: Session = Depends(get_db)):
    from app.main import templates
    two = random.sample(ESSAY_TOPICS, 2)
    mock = MockExam(mode="essay", started_at=datetime.utcnow(),
                    payload={"choices": [t["key"] for t in two]})
    db.add(mock)
    db.commit()
    db.refresh(mock)
    return templates.TemplateResponse(
        request, "mock_essay.html",
        {"mock_id": mock.id, "topics": two, "duration_min": 120},
    )


@router.post("/essay/{mock_id}/submit")
async def mock_essay_submit(mock_id: int, request: Request, db: Session = Depends(get_db)):
    mock = db.get(MockExam, mock_id)
    if not mock or mock.mode != "essay":
        raise HTTPException(404)
    form = await request.form()
    chosen = (form.get("chosen_key") or "").strip()
    body = (form.get("body") or "").strip()
    if not chosen or len(body) < 500:
        raise HTTPException(400, "请选择题目并提交至少 500 字")
    topic = next((t for t in ESSAY_TOPICS if t["key"] == chosen), None)
    if not topic:
        raise HTTPException(400, "topic not found")

    try:
        raw = llm.chat(
            [
                {"role": "system", "content": prompts.ESSAY_GRADER_SYSTEM},
                {"role": "user", "content": prompts.essay_grader_prompt(topic, body)},
            ],
            model=settings.essay_grader_model, temperature=0.1, max_tokens=2048,
        )
        txt = raw.strip()
        m = re.search(r"```(?:json)?\s*(.*?)\s*```", txt, re.DOTALL)
        if m:
            txt = m.group(1)
        result = json.loads(txt)
        score = int(result.get("total_score", 0))
        fb = result.get("feedback", "")
    except Exception as e:
        score = 0
        fb = f"评分失败:{e}"

    mock.finished_at = datetime.utcnow()
    mock.duration_sec = int((mock.finished_at - mock.started_at).total_seconds())
    mock.score_essay = score
    mock.passed = score >= 45
    mock.payload = {**(mock.payload or {}), "chosen": chosen, "body": body,
                    "feedback_md": fb, "word_count": len(body)}
    db.commit()
    return RedirectResponse(f"/mock/{mock_id}", status_code=303)


# ---------- View past mock result ----------

@router.get("/{mock_id}", response_class=HTMLResponse)
def mock_view(mock_id: int, request: Request, db: Session = Depends(get_db)):
    from app.main import templates
    mock = db.get(MockExam, mock_id)
    if not mock:
        raise HTTPException(404)
    return templates.TemplateResponse(
        request, "mock_result.html",
        {"mock": mock},
    )
