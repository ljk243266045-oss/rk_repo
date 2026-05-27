"""One-shot ingest: chunk all chapter notes, embed via API, insert into chunks_vec.

Idempotent: drops & recreates the `chunks_vec` virtual table before inserting.

Run from app/ directory:
    python -m app.rag.ingest
"""
from __future__ import annotations

import struct
import sys
import time
from pathlib import Path

from sqlalchemy import select, delete

from app.config import settings
from app.db import engine, session_scope, init_db
from app.models import Chapter, Chunk
from app.rag.chunker import chunk_markdown
from app.llm.client import embed


BATCH = 16


def _pack_floats(vec: list[float]) -> bytes:
    return struct.pack(f"{len(vec)}f", *vec)


def chunk_all_notes() -> int:
    """Replace all `chunks(source='notes')` rows with freshly chunked content."""
    with session_scope() as s:
        s.execute(delete(Chunk).where(Chunk.source == "notes"))
        s.flush()
        chapters = s.scalars(select(Chapter).order_by(Chapter.chapter_no)).all()
        total = 0
        for ch in chapters:
            md = ch.content_md or ""
            if not md.strip():
                continue
            root = f"第{ch.chapter_no}章 {ch.title}"
            for c in chunk_markdown(md, root_path=root):
                s.add(Chunk(
                    chapter_id=ch.id,
                    section_path=c.section_path,
                    content=c.text,
                    token_count=c.token_count,
                    source="notes",
                ))
                total += 1
            print(f"  ch{ch.chapter_no:02d}  +{total}")
        return total


def embed_all_chunks() -> int:
    """Embed every chunk whose id is not yet in chunks_vec."""
    # Recreate the virtual table fresh.
    with engine.begin() as conn:
        try:
            conn.exec_driver_sql("DROP TABLE IF EXISTS chunks_vec")
            conn.exec_driver_sql(
                f"CREATE VIRTUAL TABLE chunks_vec "
                f"USING vec0(embedding FLOAT[{settings.embedding_dim}])"
            )
        except Exception as e:
            print(f"[FATAL] sqlite-vec virtual table creation failed: {e}", file=sys.stderr)
            return 0

    with session_scope() as s:
        rows = s.scalars(select(Chunk).order_by(Chunk.id)).all()

    total = len(rows)
    print(f"\nEmbedding {total} chunks ...")
    done = 0
    t0 = time.time()
    with engine.begin() as conn:
        for i in range(0, total, BATCH):
            batch = rows[i : i + BATCH]
            texts = [r.content for r in batch]
            vectors = embed(texts)
            for r, v in zip(batch, vectors):
                if len(v) != settings.embedding_dim:
                    raise RuntimeError(
                        f"Embedding dim mismatch: got {len(v)}, expected {settings.embedding_dim}. "
                        f"Update EMBEDDING_DIM in .env."
                    )
                conn.exec_driver_sql(
                    "INSERT INTO chunks_vec(rowid, embedding) VALUES (?, ?)",
                    (r.id, _pack_floats(v)),
                )
            done += len(batch)
            print(f"  {done}/{total}  ({(time.time()-t0):.1f}s)")
    return done


def main() -> int:
    init_db()
    print("=== Step 1/2: chunk notes ===")
    n_chunks = chunk_all_notes()
    print(f"  total chunks: {n_chunks}\n")

    print("=== Step 2/2: embed chunks ===")
    if not (settings.dashscope_api_key or settings.openai_api_key or settings.anthropic_api_key):
        print("[WARN] No API key set in .env — skipping embedding step.", file=sys.stderr)
        print("       Set DASHSCOPE_API_KEY (or another provider) in .env to enable RAG.", file=sys.stderr)
        return 0
    n_emb = embed_all_chunks()
    print(f"\nDone. Embedded {n_emb} chunks into chunks_vec.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
