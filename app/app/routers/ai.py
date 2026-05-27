"""AI endpoints: RAG chat (streaming SSE) + MCQ generation."""
from __future__ import annotations

import json
import re
from datetime import datetime

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import Chapter, Question
from app.llm import client as llm
from app.llm import prompts
from app.rag.retriever import retrieve


router = APIRouter(prefix="/ai", tags=["ai"])


# ---------- Chat (RAG) ----------

@router.get("/chat", response_class=HTMLResponse)
def chat_page(request: Request, db: Session = Depends(get_db)):
    from app.main import templates
    chapters = db.scalars(select(Chapter).order_by(Chapter.chapter_no)).all()
    return templates.TemplateResponse(
        request, "ai_chat.html",
        {"chapters": chapters, "llm_model": settings.llm_model},
    )


@router.post("/chat/stream")
def chat_stream(
    question: str = Form(...),
    chapter_id: int | None = Form(None),
    db: Session = Depends(get_db),
):
    question = question.strip()
    if not question:
        raise HTTPException(400, "question is empty")

    try:
        snippets = retrieve(db, question, k=8, chapter_id=chapter_id or None)
    except Exception as e:
        raise HTTPException(500, f"RAG retrieval failed: {e}. 是否已运行 `python -m app.rag.ingest` 建索引?")

    if not snippets:
        async def empty():
            yield f"data: {json.dumps({'token': '参考资料中未涵盖此内容,建议查阅教材原文。'}, ensure_ascii=False)}\n\n"
            yield "event: done\ndata: {}\n\n"
        return StreamingResponse(empty(), media_type="text/event-stream")

    messages = [
        {"role": "system", "content": prompts.RAG_SYSTEM},
        {"role": "user", "content": prompts.rag_user_prompt(question, snippets)},
    ]

    def event_stream():
        # First, send the citations as a single event so the client can render them.
        citations = [
            {"i": i + 1, "section": s["section_path"], "chapter_no": s["chapter_no"], "page": s.get("page")}
            for i, s in enumerate(snippets)
        ]
        yield f"event: citations\ndata: {json.dumps(citations, ensure_ascii=False)}\n\n"
        try:
            for delta in llm.chat_stream(messages, temperature=0.2):
                yield f"data: {json.dumps({'token': delta}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'message': str(e)}, ensure_ascii=False)}\n\n"
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ---------- MCQ Generation ----------

_JSON_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def _parse_mcq_json(text: str) -> list[dict]:
    """Tolerant JSON extraction; LLMs sometimes wrap in ``` fences."""
    text = text.strip()
    m = _JSON_FENCE.search(text)
    if m:
        text = m.group(1)
    # If model returned a single object instead of an array, wrap it.
    if text.startswith("{"):
        text = "[" + text + "]"
    return json.loads(text)


@router.post("/generate-mcq")
def generate_mcq(
    chapter_id: int = Form(...),
    n: int = Form(10),
    db: Session = Depends(get_db),
):
    if n < 1 or n > 30:
        raise HTTPException(400, "n must be between 1 and 30")
    ch = db.get(Chapter, chapter_id)
    if not ch:
        raise HTTPException(404, "chapter not found")

    # Use RAG to ground generation: retrieve key chunks from the chapter.
    try:
        snippets = retrieve(db, f"第{ch.chapter_no}章 {ch.title} 核心概念 重点考点", k=12, chapter_id=chapter_id)
    except Exception as e:
        raise HTTPException(500, f"RAG retrieval failed: {e}. 请先运行 `python -m app.rag.ingest` 建索引。")
    if not snippets:
        raise HTTPException(400, f"第{ch.chapter_no}章没有可用 chunk;请先运行 ingest。")

    messages = [
        {"role": "system", "content": prompts.MCQ_SYSTEM},
        {"role": "user", "content": prompts.mcq_user_prompt(
            chapter_title=f"第{ch.chapter_no}章 {ch.title}",
            n=n,
            snippets=snippets,
        )},
    ]
    raw = llm.chat(messages, temperature=0.5, max_tokens=4096)

    try:
        items = _parse_mcq_json(raw)
    except json.JSONDecodeError as e:
        raise HTTPException(500, f"LLM 返回的不是有效 JSON: {e}\n\n原文:\n{raw[:500]}")

    created = []
    for it in items:
        try:
            options = it["options"]
            opts_list = [f"{k}. {v}" for k, v in options.items()] if isinstance(options, dict) else list(options)
            q = Question(
                chapter_id=chapter_id,
                type="mcq",
                stem=it["stem"],
                options=opts_list,
                answer=it["answer"].strip().upper()[:1],
                explanation=it.get("explanation"),
                difficulty=int(it.get("difficulty", 3)),
                source="ai",
                ai_model=settings.llm_model,
                verified=False,
            )
            # store source_quote inside explanation for now
            if it.get("source_quote"):
                q.explanation = (q.explanation or "") + f"\n\n【原文】{it['source_quote']}"
            db.add(q)
            created.append({"stem": q.stem, "answer": q.answer})
        except (KeyError, TypeError, ValueError) as e:
            continue
    db.commit()

    return JSONResponse({
        "chapter": f"第{ch.chapter_no}章 {ch.title}",
        "requested": n,
        "created": len(created),
        "skipped": len(items) - len(created),
        "preview": created[:3],
    })
