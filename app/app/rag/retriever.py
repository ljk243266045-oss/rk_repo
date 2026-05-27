"""Vector + optional chapter filter retriever over `chunks_vec`."""
from __future__ import annotations

import struct
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.llm.client import embed
from app.models import Chunk, Chapter


def _pack_floats(vec: list[float]) -> bytes:
    return struct.pack(f"{len(vec)}f", *vec)


def retrieve(
    db: Session,
    query: str,
    *,
    k: int = 8,
    chapter_id: int | None = None,
) -> list[dict]:
    """Return top-k chunks for the query. Each dict has id/content/section_path/distance/chapter_no."""
    if not query.strip():
        return []
    q_vec = embed([query])[0]
    q_blob = _pack_floats(q_vec)

    # sqlite-vec KNN: SELECT rowid, distance FROM chunks_vec WHERE embedding MATCH ? ORDER BY distance LIMIT k
    over_k = max(k * 4, 16) if chapter_id else k
    hits = db.execute(
        text("SELECT rowid, distance FROM chunks_vec "
             "WHERE embedding MATCH :q AND k = :k "
             "ORDER BY distance"),
        {"q": q_blob, "k": over_k},
    ).all()
    if not hits:
        return []

    chunk_ids = [int(h.rowid) for h in hits]
    distances = {int(h.rowid): float(h.distance) for h in hits}

    q = db.query(Chunk, Chapter).join(Chapter, Chunk.chapter_id == Chapter.id).filter(Chunk.id.in_(chunk_ids))
    if chapter_id is not None:
        q = q.filter(Chunk.chapter_id == chapter_id)
    rows = q.all()

    enriched = []
    for chunk, chapter in rows:
        enriched.append({
            "id": chunk.id,
            "content": chunk.content,
            "section_path": chunk.section_path or "",
            "chapter_no": chapter.chapter_no,
            "chapter_title": chapter.title,
            "page": chapter.page_start,
            "distance": distances.get(chunk.id, 0.0),
        })
    enriched.sort(key=lambda r: r["distance"])
    return enriched[:k]
