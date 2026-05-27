# 软考"系统规划与管理师"备考系统

> 一个本地 Web 应用,辅助软考中级"系统规划与管理师"(2024 大纲)备考。
> 集成 **结构化笔记浏览 / FSRS 间隔重复闪卡 / RAG 智能问答 / AI 出题与评分 / 全真模拟考试** 全流程。

[![Python](https://img.shields.io/badge/Python-3.10+-blue)]()
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688)]()
[![License](https://img.shields.io/badge/License-MIT-yellow)]()

## ✨ 功能特性

| 模块 | 功能 |
|---|---|
| 📖 **笔记浏览** | 24 章结构化笔记,4 篇分类导航,markdown 渲染 |
| 🃏 **闪卡复习** | **FSRS-4.5** 间隔重复算法,键盘 Space + 1/2/3/4 评分 |
| 📝 **三模式刷题** | 章节 / 混合 / 错题复习,自动错题闭环 |
| ⚡ **薄弱专题** | 自动定位正确率最低的 5 章集中冲刺 |
| 📋 **案例分析** | 10 个内置场景骨架 + AI rubric 评分(25 分制) |
| 📜 **论文训练** | 10 个题目 + outline/整篇双模式 + AI 5 维评分(75 分制) |
| 🎯 **全真模考** | 综合 75 题 × 2.5h / 案例 3 道 × 1.5h / 论文 × 2h,计时自动提交 |
| 🤖 **RAG 问答** | 基于教材原文的检索增强问答,流式输出 + 引用页码 |
| 🤖 **AI 出题** | 按章节生成 MCQ,RAG 锚定避免幻觉,人工 ✓/✗ 审核入库 |
| 📊 **数据仪表盘** | 预测通过率 / 4 维知识雷达 / 90 天热图 / 各章正确率 |
| 📦 **数据导出** | Anki CSV / 题库 JSON,数据可迁移 |

## 🧰 技术栈

- **后端**: FastAPI + SQLAlchemy + SQLite (+ `sqlite-vec` 向量扩展)
- **前端**: Jinja2 + HTMX + Alpine.js + Tailwind (CDN, **零 npm 构建**)
- **LLM**: LiteLLM 抽象 — 支持 Claude / 通义千问 / OpenAI / 文心一言 一键切换
- **SRS**: FSRS-4.5 (Anki 5.x 同款算法)

## 📁 项目结构

```
软考/
├── app/                              # 主应用
│   ├── app/
│   │   ├── main.py                   # FastAPI 入口
│   │   ├── config.py / db.py / models.py
│   │   ├── llm/                      # LLM 抽象 + 提示词
│   │   ├── rag/                      # 切块 / 嵌入 / 检索
│   │   ├── srs/                      # FSRS 调度封装
│   │   ├── routers/                  # 10 个路由模块
│   │   ├── data/                     # 案例 / 论文题目常量
│   │   ├── templates/                # 30+ Jinja2 模板
│   │   └── static/
│   ├── scripts/                      # seed / ingest / verify 脚本
│   ├── pyproject.toml
│   ├── .env.example
│   └── run.bat
├── extract_pdf.py                    # PDF → 纯文本提取
├── merge_notes.py                    # 合并分章笔记为单文件
├── docs/SETUP.md                     # 完整数据准备指南
├── README.md                         # 你正在看的文件
├── LICENSE                           # MIT
└── .gitignore
```

> ⚠️ **不在本仓库中**:教材 PDF、提取的纯文本、AI 生成的结构化笔记、学习记录数据库。版权与隐私原因,需要自行准备。详见 [docs/SETUP.md](docs/SETUP.md)。

## 🚀 快速开始

### 前置要求
- Windows / macOS / Linux
- Python 3.10+
- (可选) LLM API key — 通义千问 / Claude / OpenAI / 文心,任选其一

### 三步启动

```bash
# 1. 准备数据(详见 docs/SETUP.md)
#    把你的教材 PDF 放在工作目录根下,命名为:
#    系统规划与管理师教程第2版.pdf
python extract_pdf.py
# (生成结构化笔记的步骤见 SETUP.md, 这是 AI 辅助任务)

# 2. 安装 + 启动
cd app
pip install -e .
copy .env.example .env                # 填入你的 API key (可选)
python scripts/seed_chapters.py       # 把笔记导入 SQLite

# 3. 跑起来
run.bat                                # Windows
# 或:python -m uvicorn app.main:app --host 127.0.0.1 --port 8765
```

浏览器打开 **http://127.0.0.1:8765**。

### 启用 AI 功能(可选)

如果你填了 `.env` 中的 API key,可以解锁 RAG 问答 / AI 出题 / 案例与论文评分:

```bash
cd app
python scripts/verify_p1.py           # 验证 API key
python -m app.rag.ingest              # 构建 RAG 向量索引(~5 分钟, 通义嵌入 ~¥5)
```

## 💰 全程 AI 成本估算(用通义千问 qwen-plus)

| 用途 | 成本 |
|---|---|
| 一次性嵌入(全书索引) | ~¥5 |
| 出题(1500 道) | ~¥60 |
| RAG 问答(200 次/月 × 5 月) | ~¥60 |
| 案例 + 论文评分(各 50 次) | ~¥40 |
| **5 个月全程预算上限** | **~¥200** |

> 论文评分推荐用 Claude Sonnet(中文长文质量明显更高),5 个月增量约 ¥150。

## 📅 推荐备考节奏(对应模块)

| 时间 | 目标 | 主要使用功能 |
|---|---|---|
| **第 1-2 月** | 通读教材 + 建立闪卡 | 📖 笔记 + 🃏 闪卡 |
| **第 3 月** | 各章 AI 出题 + 刷题 | 📚 题库 + 📝 刷题 |
| **第 4 月** | 案例分析 + 论文练手 | 📋 案例 + 📜 论文 |
| **第 5 月** | 全真模考 | 🎯 模考 + 📊 数据 |
| **考前 2 周** | 错题 + 薄弱章冲刺 | ⚡ 薄弱专题 |

## 🛠️ 详细文档

- [docs/SETUP.md](docs/SETUP.md) — 数据准备与安装详细步骤
- [app/README.md](app/README.md) — 应用层文档(命令行参数、环境变量)

## ⚠️ 重要说明

- 本项目**仅提供工具**,不分发任何教材原文或衍生笔记。教材为清华大学出版社出版,使用者需合法持有正版教材。
- AI 生成的题目和评分仅供参考,**不代表真实考试题目**,不保证准确性。
- 所有学习数据(SQLite)存储在本地 `app/data/`,不上传任何云端。

## 📜 License

MIT — 详见 [LICENSE](LICENSE)。
教材内容、笔记及其他衍生数据不在本仓库授权范围内。

## 🙏 贡献

Issue 与 PR 欢迎。改进方向例如:
- 真题导入工具(从 PDF/Word 解析单选题)
- 更精准的 prompt 模板
- 其他软考方向适配(如系统集成项目管理工程师)
- Anki APKG 原生格式导出(目前仅 CSV)
