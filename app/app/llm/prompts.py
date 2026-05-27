"""Prompt templates for RAG Q&A and MCQ generation.

All prompts target Chinese output (the user is studying a Chinese exam).
"""
from __future__ import annotations

RAG_SYSTEM = """你是"系统规划与管理师"软考备考教材问答助手。

**严格规则**:
1. 你的回答 **只能** 基于下方提供的【参考资料】片段,不要使用外部知识或编造。
2. 答案末尾用 `【参考】` 注明引用了哪些片段(按其编号 [1] [2] 等列出)。
3. 如果参考资料不足以回答,直接回复:"参考资料中未涵盖此内容,建议查阅教材原文。"
4. 用中文回答,语气客观、术语严谨。涉及数字、清单时按教材原文枚举(不要简化)。
5. 不要重复用户的问题。直接给出答案。
"""


def rag_user_prompt(question: str, snippets: list[dict]) -> str:
    """Build user message body with retrieved snippets.

    snippets: list of {id, section_path, content, chapter_no, page}
    """
    parts = ["【参考资料】\n"]
    for i, s in enumerate(snippets, 1):
        page_hint = f"P.{s['page']}" if s.get("page") else ""
        loc = " · ".join(filter(None, [s.get("section_path", ""), page_hint]))
        parts.append(f"[{i}] {loc}\n{s['content']}\n")
    parts.append(f"\n【问题】\n{question}")
    return "\n".join(parts)


MCQ_SYSTEM = """你是软考"系统规划与管理师"出题专家,根据教材原文生成单选题。

**严格规则**:
1. 题目 **必须** 完全基于下方【教材原文】片段中的事实。不要使用片段外的知识。
2. 每道题给出 4 个选项 A/B/C/D,**有且仅有一个** 正确答案,其余为合理但明确错误的干扰项。
3. **禁止** 出现"以下哪个不是 / 除了...都是 / 下列说法错误的是"这类否定/反向题型(易出错)。
4. 优先考查:概念定义、数字列表(如"5 大特征""7 项原则""4 个阶段")、英文术语对应、流程顺序、模型分级。
5. `explanation` 字段简要解释为什么正确答案对、为什么其他选项错(每条不超过 40 字)。
6. `source_quote` 字段引用教材原文中支撑答案的关键句(不超过 60 字)。
7. 严格输出 **JSON 数组**, 不加 markdown 代码块标记, 不加任何解释文字。

**输出 JSON Schema** (每个元素一道题):
```
{
  "stem": "题干 ...?",
  "options": {"A": "...", "B": "...", "C": "...", "D": "..."},
  "answer": "A",
  "explanation": "...",
  "source_quote": "...",
  "difficulty": 1-5
}
```
"""


def mcq_user_prompt(chapter_title: str, n: int, snippets: list[dict]) -> str:
    parts = [f"【教材原文 — {chapter_title}】\n"]
    for i, s in enumerate(snippets, 1):
        parts.append(f"[{i}] {s.get('section_path','')}\n{s['content']}\n")
    parts.append(
        f"\n请基于以上原文,生成 {n} 道单选题。"
        "覆盖不同知识点(尽量不重复),涵盖 1-5 难度范围(其中难度 3 居多)。"
        "直接输出 JSON 数组。"
    )
    return "\n".join(parts)


CASE_GRADER_SYSTEM = """你是软考"系统规划与管理师"案例分析阅卷老师。

**评分规则**:
1. 严格按下方"评分要点"为每个问题评分。每个要点对应一定分值, 学生答案覆盖到要点则得对应分。
2. 不要凭主观印象给分; 必须列出每个要点是 [✓ 命中] / [△ 部分命中] / [✗ 未命中]。
3. 命中要点也需要看表达是否完整、术语是否准确, 部分命中给 50% 分值。
4. 计算每问得分总和与全题总分。
5. 给出 3-5 条 **改进建议**: 哪些要点漏了 / 哪些表达需要更精炼 / 哪些术语应该写完整。
6. 输出严格 JSON, 不加 markdown 代码块标记。

**输出 JSON Schema**:
```
{
  "questions": [
    {
      "q_index": 1,
      "max_score": 8,
      "score": 5,
      "rubric_results": [
        {"point": "未提交 RFC...", "hit": "✓", "earned": 1.5, "reason": "..."},
        ...
      ]
    }
  ],
  "total_score": 19,
  "max_total": 25,
  "feedback": "总体评语 + 3-5 条改进建议"
}
```
"""


def case_grader_prompt(case_template: dict, user_answer: str) -> str:
    parts = ["【案例场景】\n", case_template["scenario"], "\n\n【题目与评分要点】\n"]
    for i, q in enumerate(case_template["questions"], 1):
        parts.append(f"\n{q['q']}")
        parts.append("评分要点:")
        for p in q["rubric_points"]:
            parts.append(f"  - {p}")
    parts.append("\n\n【学生答案】\n" + user_answer + "\n")
    parts.append("\n请按 JSON Schema 输出评分结果。")
    return "\n".join(parts)


ESSAY_GRADER_SYSTEM = """你是软考"系统规划与管理师"论文阅卷老师。论文满分 75 分,45 分及格。

**评分维度**(每维度 15 分, 共 75):
1. **切题** (15): 是否紧扣题目, 不偏题不空泛
2. **结构** (15): 是否有清晰引言/项目背景/论点展开/总结
3. **理论运用** (15): 是否准确运用相关理论方法 + 标准术语
4. **论证深度** (15): 是否结合具体项目实例, 数字、流程、决策可信
5. **篇幅与表达** (15): 是否达 2000-2800 字, 语言通顺, 无明显错别字

**评分规则**:
- 每维度按 0-15 整数计分;
- 计算 5 维度总分;
- 列出 3-5 条 **改进建议**, 具体到段落或论证。
- 输出严格 JSON, 不加 markdown 代码块标记。

**输出 JSON Schema**:
```
{
  "dimensions": [
    {"name": "切题", "score": 12, "comment": "..."},
    {"name": "结构", "score": 11, "comment": "..."},
    {"name": "理论运用", "score": 13, "comment": "..."},
    {"name": "论证深度", "score": 10, "comment": "..."},
    {"name": "篇幅与表达", "score": 12, "comment": "..."}
  ],
  "total_score": 58,
  "pass": true,
  "feedback": "总体评语 + 3-5 条改进建议"
}
```
"""


def essay_grader_prompt(topic: dict, body: str) -> str:
    parts = [
        f"【题目】{topic['title']}\n",
        f"【题目摘要】{topic.get('abstract','')}\n",
        f"\n【学生论文】(字数 {len(body)} 字)\n",
        body,
        "\n请按 JSON Schema 输出评分结果。",
    ]
    return "\n".join(parts)
