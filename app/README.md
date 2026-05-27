# 软考"系统规划与管理师"备考系统

本地 Web 应用,辅助 2026 年 11 月软考"系统规划与管理师"中级备考。

## 快速开始

```cmd
cd app
pip install -e .
copy .env.example .env
:: 编辑 .env, 填入你的 API key
python scripts\seed_chapters.py
run.bat
```

浏览器打开 http://127.0.0.1:8765

## 功能 (P0 阶段)

- 24 章结构化笔记浏览
- FSRS 间隔重复闪卡 (手动新增 + 复习)

后续阶段陆续增加:RAG 问答 / AI 出题 / 刷题模式 / 案例分析 / 论文训练 / 模拟考试。

## 技术栈

- 后端: FastAPI + SQLAlchemy + SQLite (+ sqlite-vec for RAG)
- 前端: Jinja2 + HTMX + Alpine.js + Tailwind (CDN, 零构建)
- LLM: LiteLLM 抽象 (Claude / 通义 / OpenAI / 文心)
- SRS: FSRS-4.5
