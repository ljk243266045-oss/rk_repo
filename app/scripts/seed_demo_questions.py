"""Seed a handful of verified MCQs for P2 smoke testing.

Run from app/ directory:
    python scripts/seed_demo_questions.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, delete
from app.db import session_scope
from app.models import Chapter, Question


DEMO = [
    {
        "chapter_no": 1,
        "stem": "诺兰六阶段模型按顺序划分信息系统发展阶段,其中前三个阶段属于:",
        "options": ["A. 计算机时代", "B. 信息时代", "C. 数字时代", "D. 智能时代"],
        "answer": "A",
        "explanation": "诺兰六阶段:初始、传播、控制属计算机时代;集成、数据管理、成熟属信息时代。",
        "difficulty": 2,
    },
    {
        "chapter_no": 1,
        "stem": "OSI 参考模型中负责端到端可靠传输的是:",
        "options": ["A. 网络层", "B. 数据链路层", "C. 传输层", "D. 会话层"],
        "answer": "C",
        "explanation": "传输层提供端到端的可靠数据传输,典型协议为 TCP。",
        "difficulty": 2,
    },
    {
        "chapter_no": 6,
        "stem": "云计算的 5 大内部特征不包括以下哪一项:",
        "options": ["A. 按需自服务", "B. 资源池化", "C. 可计量服务", "D. 数据加密"],
        "answer": "D",
        "explanation": "云计算 5 大内部特征:按需自服务、广泛网络访问、资源池化、快速伸缩、可计量服务。数据加密属安全措施。",
        "difficulty": 2,
    },
    {
        "chapter_no": 6,
        "stem": "云数据中心衡量能耗效率的关键指标是:",
        "options": ["A. PUE", "B. SLA", "C. MTBF", "D. CMDB"],
        "answer": "A",
        "explanation": "PUE(Power Usage Effectiveness)= 数据中心总能耗 / IT 设备能耗,值越接近 1 越节能。",
        "difficulty": 2,
    },
    {
        "chapter_no": 12,
        "stem": "ITSS 服务质量五大特性不包括:",
        "options": ["A. 安全性", "B. 可靠性", "C. 响应性", "D. 经济性"],
        "answer": "D",
        "explanation": "ITSS 五大服务质量特性:安全性、可靠性、响应性、有形性、友好性(口诀'安可响有友')。",
        "difficulty": 3,
    },
    {
        "chapter_no": 17,
        "stem": "PMBOK 项目管理 5 大过程组按顺序是:",
        "options": [
            "A. 启动 → 规划 → 执行 → 监控 → 收尾",
            "B. 启动 → 执行 → 规划 → 监控 → 收尾",
            "C. 规划 → 启动 → 执行 → 监控 → 收尾",
            "D. 启动 → 规划 → 监控 → 执行 → 收尾",
        ],
        "answer": "A",
        "explanation": "口诀'启规执监收':启动、规划、执行、监控、收尾。监控贯穿全过程,与执行并行。",
        "difficulty": 2,
    },
    {
        "chapter_no": 17,
        "stem": "项目管理 10 大知识领域不包括:",
        "options": ["A. 范围管理", "B. 进度管理", "C. 整合管理", "D. 营销管理"],
        "answer": "D",
        "explanation": "10 知识领域:整范进成质,资沟风采干。营销不在其中。",
        "difficulty": 3,
    },
]


def main() -> int:
    with session_scope() as s:
        # Wipe demo questions (those with source='manual' AND ai_model='demo-seed')
        s.execute(delete(Question).where(Question.ai_model == "demo-seed"))
        s.flush()

        n = 0
        for d in DEMO:
            ch = s.scalar(select(Chapter).where(Chapter.chapter_no == d["chapter_no"]))
            if not ch:
                print(f"  ! chapter {d['chapter_no']} not found, skipping", file=sys.stderr)
                continue
            s.add(Question(
                chapter_id=ch.id,
                type="mcq",
                stem=d["stem"],
                options=d["options"],
                answer=d["answer"],
                explanation=d["explanation"],
                difficulty=d["difficulty"],
                source="manual",
                ai_model="demo-seed",
                verified=True,
            ))
            n += 1
        print(f"Seeded {n} demo verified MCQs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
