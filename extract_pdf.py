"""把教材 PDF 提取为纯文本(每页加 `===== Page N =====` 分隔)。

用法:
    python extract_pdf.py                              # 默认路径
    python extract_pdf.py path/to/textbook.pdf
    python extract_pdf.py textbook.pdf out.txt

依赖:pip install pymupdf
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import fitz  # type: ignore


DEFAULT_PDF = "系统规划与管理师教程第2版.pdf"


def extract(pdf_path: Path, out_path: Path) -> None:
    if not pdf_path.exists():
        raise SystemExit(
            f"[ERROR] 找不到 PDF 文件:{pdf_path}\n"
            f"请将教材 PDF 放在该路径,或在命令行指定:\n"
            f"  python extract_pdf.py <pdf_path> [out_path]"
        )

    doc = fitz.open(str(pdf_path))
    total = doc.page_count
    print(f"PDF: {pdf_path}  ({total} pages)")
    print(f"OUT: {out_path}")

    with open(out_path, "w", encoding="utf-8") as f:
        for i in range(total):
            page = doc.load_page(i)
            text = page.get_text()
            f.write(f"\n===== Page {i + 1} =====\n")
            f.write(text)
            if (i + 1) % 50 == 0:
                print(f"  Extracted {i + 1}/{total} pages")

    doc.close()
    print("✓ Done")


def main(argv: list[str]) -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

    if len(argv) >= 2:
        pdf_path = Path(argv[1])
    else:
        pdf_path = Path(DEFAULT_PDF)

    if len(argv) >= 3:
        out_path = Path(argv[2])
    else:
        out_path = pdf_path.with_suffix(".txt")

    extract(pdf_path, out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
