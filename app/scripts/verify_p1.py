"""P1 sanity check: verify API key works, do a tiny embed + chat round-trip.

Run AFTER you've filled DASHSCOPE_API_KEY in .env:
    python scripts/verify_p1.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings
from app.llm.client import embed, chat


def main() -> int:
    if not (settings.dashscope_api_key or settings.openai_api_key or settings.anthropic_api_key):
        print("[FAIL] No API key in .env. Fill DASHSCOPE_API_KEY (or another) then re-run.", file=sys.stderr)
        return 1

    print(f"LLM model    : {settings.llm_model}")
    print(f"Embedding    : {settings.embedding_model} (dim={settings.embedding_dim})")

    print("\n[1/2] Embedding test ...")
    try:
        v = embed(["云计算的 5 大内部特征"])[0]
        print(f"  ✓ Got vector of length {len(v)}")
        if len(v) != settings.embedding_dim:
            print(f"  ⚠️ Dimension mismatch — update EMBEDDING_DIM={len(v)} in .env", file=sys.stderr)
    except Exception as e:
        print(f"  ✗ FAIL: {e}", file=sys.stderr)
        return 2

    print("\n[2/2] Chat test (one short prompt) ...")
    try:
        reply = chat(
            [{"role": "user", "content": "用一句话定义云计算 (≤30 字)。"}],
            temperature=0.1,
            max_tokens=80,
        )
        print(f"  ✓ Reply: {reply.strip()}")
    except Exception as e:
        print(f"  ✗ FAIL: {e}", file=sys.stderr)
        return 3

    print("\n✅ P1 check passed. 你可以运行 `python -m app.rag.ingest` 构建全书索引。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
