"""把 notes/ch*.md 分章笔记合并为单一结构化笔记文件。

用法:
    python merge_notes.py                                       # 默认目录
    python merge_notes.py path/to/notes/ output.md
"""
from __future__ import annotations

import io
import sys
from pathlib import Path


DEFAULT_NOTES_DIR = "notes"
DEFAULT_OUT = "系统规划与管理师_全书结构化笔记.md"

FILES_IN_ORDER = [
    "ch01-04.md", "ch05-08.md", "ch09-12.md", "ch13-17.md", "ch18-21.md", "ch22-24.md",
]

HEADER = """# 系统规划与管理师教程(第2版)全书结构化笔记

> 教材:清华大学出版社《系统规划与管理师教程》第 2 版(依据 2024 年审定大纲)
> 全书 798 页,分 4 篇 24 章。本笔记按章节生成:**本章概述 / 知识结构 / 核心概念 / 重点考点 / 易混淆·口诀**。

---

## 全书目录与速览

### 第一篇 基础篇
- [第 1 章 信息系统与信息技术发展](#第1章-信息系统与信息技术发展)
- [第 2 章 数字中国与数智化发展](#第2章-数字中国与数智化发展)
- [第 3 章 系统科学与哲学方法论](#第3章-系统科学与哲学方法论)

### 第二篇 方法篇
- [第 4 章 信息系统规划](#第4章-信息系统规划)
- [第 5 章 应用系统规划](#第5章-应用系统规划)
- [第 6 章 云资源规划](#第6章-云资源规划)
- [第 7 章 网络环境规划](#第7章-网络环境规划)
- [第 8 章 数据资源规划](#第8章-数据资源规划)
- [第 9 章 信息安全规划](#第9章-信息安全规划)
- [第 10 章 云原生系统规划](#第10章-云原生系统规划)

### 第三篇 能力篇
- [第 11 章 信息系统治理](#第11章-信息系统治理)
- [第 12 章 信息系统服务管理](#第12章-信息系统服务管理)
- [第 13 章 人员管理](#第13章-人员管理)
- [第 14 章 规范与过程管理](#第14章-规范与过程管理)
- [第 15 章 技术与研发管理](#第15章-技术与研发管理)
- [第 16 章 资源与工具管理](#第16章-资源与工具管理)
- [第 17 章 信息系统项目管理](#第17章-信息系统项目管理)

### 第四篇 实践篇
- [第 18 章 智慧城市发展规划](#第18章-智慧城市发展规划)
- [第 19 章 智慧园区发展规划](#第19章-智慧园区发展规划)
- [第 20 章 数字乡村发展规划](#第20章-数字乡村发展规划)
- [第 21 章 企业数字化转型发展规划](#第21章-企业数字化转型发展规划)
- [第 22 章 智能制造发展规划](#第22章-智能制造发展规划)
- [第 23 章 新型消费系统规划](#第23章-新型消费系统规划)
- [第 24 章 法律法规和标准规范](#第24章-法律法规和标准规范)

---

"""


def merge(notes_dir: Path, out_path: Path) -> None:
    if not notes_dir.exists():
        raise SystemExit(f"[ERROR] 找不到分章笔记目录:{notes_dir}")

    missing = [f for f in FILES_IN_ORDER if not (notes_dir / f).exists()]
    if missing:
        raise SystemExit(
            f"[ERROR] 缺少分章笔记文件:{missing}\n"
            f"请先准备好 6 份分章笔记(详见 docs/SETUP.md)。"
        )

    with open(out_path, "w", encoding="utf-8") as out:
        out.write(HEADER)
        for fn in FILES_IN_ORDER:
            path = notes_dir / fn
            content = path.read_text(encoding="utf-8")
            out.write(content)
            out.write("\n\n---\n\n")

    text = out_path.read_text(encoding="utf-8")
    cjk = sum(1 for c in text if 0x4E00 <= ord(c) <= 0x9FFF)
    print(f"✓ Done. Output: {out_path}")
    print(f"  Total characters: {len(text):,}")
    print(f"  CJK characters: {cjk:,}")


def main(argv: list[str]) -> int:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

    notes_dir = Path(argv[1]) if len(argv) >= 2 else Path(DEFAULT_NOTES_DIR)
    out_path = Path(argv[2]) if len(argv) >= 3 else Path(DEFAULT_OUT)

    merge(notes_dir, out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
