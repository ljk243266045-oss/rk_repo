# 安装与数据准备指南

本系统**不分发任何教材数据**(版权原因)。要让所有功能可用,需要你自行准备教材并生成笔记。

## 0. 前置环境

```bash
# 检查 Python
python --version    # >= 3.10

# (Windows) 启用 UTF-8 控制台
chcp 65001
set PYTHONUTF8=1
```

## 1. 准备教材 PDF

把你合法持有的教材 PDF 放在仓库根目录,推荐文件名:

```
软考/
└── 系统规划与管理师教程第2版.pdf      ← 这里
```

教材信息:
- 书名:《系统规划与管理师教程》第 2 版
- 出版社:清华大学出版社
- 依据:2024 年审定通过的考试大纲
- ISBN: 978-7-302-67091-9

## 2. 提取纯文本

```bash
python extract_pdf.py
# 或指定路径:
python extract_pdf.py path/to/your.pdf
```

生成:`系统规划与管理师教程第2版.txt`(约 4.7 MB,798 页,每页有 `===== Page N =====` 分隔)。

## 3. 生成结构化笔记(AI 辅助)

这一步用 LLM 把教材分章节,提取出 `本章概述 / 知识结构 / 核心概念 / 重点考点 / 易混淆口诀` 5 个 section。

### 方式 A:使用 Claude Code(本项目原作者的做法)

```bash
# 让 Claude Code 读 .txt 后并行 6 个 agent 分批处理 24 章
# 输出到 notes/ch01-04.md ... notes/ch22-24.md
```

### 方式 B:自己写脚本调用 LLM API

参考 `app/app/llm/prompts.py` 中的 `RAG_SYSTEM` 模板风格,要求 LLM 输出固定格式的 markdown。
6 批,每批 4 章左右,每章约 800-1200 字。

### 方式 C:手写笔记

不推荐,工作量约 100 小时。

### 合并为单文件

```bash
# 假设你已经在 notes/ 目录下放好了 ch01-04.md ... ch22-24.md
python merge_notes.py
```

生成 `系统规划与管理师_全书结构化笔记.md`(约 160 KB)。

## 4. 配置 LLM API(可选,但强烈推荐)

```bash
cd app
copy .env.example .env
notepad .env
```

填入至少一个 provider 的 key:

```ini
LLM_MODEL=dashscope/qwen-plus              # 默认用通义千问
DASHSCOPE_API_KEY=sk-...

# 论文评分推荐换成 Claude(中文长文质量明显更高):
ESSAY_GRADER_MODEL=anthropic/claude-sonnet-4-5
ANTHROPIC_API_KEY=sk-ant-...
```

获取 API key:
- **通义千问**(推荐):https://dashscope.console.aliyun.com/
- Claude(中转或官方):https://console.anthropic.com/
- OpenAI:https://platform.openai.com/

成本估算见根目录 [README.md](../README.md) "全程 AI 成本估算"。

## 5. 安装依赖

```bash
cd app
pip install -e .
```

约 10 个核心依赖,首次安装 ~2 分钟。

## 6. 初始化数据库

```bash
# 在 app/ 目录下
python scripts/seed_chapters.py
# 期望输出:
#   ✓ ch01 信息系统与信息技术发展  (5 sections)
#   ...
#   Seeded 24 chapters into ...\ruankao.db
```

## 7. 构建 RAG 索引(可选,启用 AI 问答 / 出题)

```bash
# 验证 API key 可用
python scripts/verify_p1.py

# 构建索引(用 DashScope 嵌入约 5 元成本, 3-5 分钟)
python -m app.rag.ingest
```

## 8. 启动

```bash
# Windows:
run.bat

# 跨平台:
python -m uvicorn app.main:app --host 127.0.0.1 --port 8765
```

浏览器打开:**http://127.0.0.1:8765**

## 9. 备份数据(强烈建议)

5 个月学习数据如果丢了等于白考。建议配置定时备份:

```bash
# Windows 任务计划程序 — 每日凌晨 3 点
schtasks /create /tn "ruankao_backup" /sc daily /st 03:00 ^
  /tr "python C:\path\to\app\scripts\backup_db.py"
```

(`backup_db.py` 需自行实现,简单的 `shutil.copy2` 即可。)

## 常见问题

### 「ModuleNotFoundError: No module named 'sqlite_vec'」
你跑了不带 sqlite-vec 的 Python。重新 `pip install -e .` 确认依赖装齐。

### 「LiteLLM 报 BadRequestError」
检查 `.env` 中 `LLM_MODEL` 的 provider 前缀和对应 `*_API_KEY` 是否匹配。

### 「FSRS Card has no field 'difficulty'」
fsrs 包版本不对,本项目用 fsrs >= 6.0。`pip install -U fsrs`。

### 中文显示乱码
Windows PowerShell 默认 GBK。先执行 `chcp 65001` + `set PYTHONUTF8=1`,或用 `run.bat`(已内置)。

### sqlite-vec 报「no such function: vec_distance_L2」
sqlite-vec 扩展未加载。检查 `app/app/db.py` 中 `_enable_sqlite_vec` 的输出。Windows 上 wheel 应该自带二进制。

## 下一步

回到根目录 [README.md](../README.md) 看推荐备考节奏。
