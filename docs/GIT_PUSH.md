# Git 推送清单

## 0. 预检(必看)

确认下面 3 类文件**不会**被传:

```bash
git ls-files --others --ignored --exclude-standard
```

应该列出(部分):
- `系统规划与管理师教程第2版.pdf`     ← 教材原书
- `系统规划与管理师教程第2版.txt`     ← 提取的纯文本
- `系统规划与管理师_全书结构化笔记.md` ← AI 生成笔记
- `notes/ch*.md`                       ← 分章笔记
- `app/data/ruankao.db`                ← 你的学习数据
- 各种 `__pycache__/` 和 `.egg-info/`

如果上面这些**没**在列表里,先检查 `.gitignore`。

## 1. 检查将要被追踪的内容

```bash
git status
git ls-files --others --cached --exclude-standard | head -30
```

期望看到的是:`README.md`、`LICENSE`、`.gitignore`、`app/` 全部源码、`extract_pdf.py`、`merge_notes.py`、`docs/`。

## 2. 配置 git 身份(如果还没配)

```bash
git config user.name  "你的名字"
git config user.email "你的邮箱@example.com"
```

## 3. 首次提交

```bash
git add .
git status               # 再核对一遍 staged 的文件
git commit -m "Initial commit: 软考'系统规划与管理师'备考系统"
```

## 4. 创建 GitHub 远端

### 方式 A — 命令行(用 gh CLI)

```bash
gh auth login
gh repo create ruankao-prep --public --source=. --remote=origin --push
```

### 方式 B — 浏览器

1. 浏览器打开 https://github.com/new
2. Repository name: `ruankao-prep`(或你喜欢的名)
3. **不要**勾选 "Initialize this repository with..."(README/LICENSE/gitignore 都已经在本地)
4. 选 Public
5. 点 Create repository
6. 然后:
   ```bash
   git branch -M main
   git remote add origin https://github.com/<你的用户名>/ruankao-prep.git
   git push -u origin main
   ```

## 5. 推完后再检查一次

打开 GitHub 网页,确认:
- [ ] 没有 PDF 文件
- [ ] 没有 .txt 大文件
- [ ] 没有 `系统规划与管理师_全书结构化笔记.md`
- [ ] 没有 `notes/` 文件夹(应该是空的或不存在)
- [ ] 没有 `.env`(只有 `.env.example`)
- [ ] 没有 `*.db` 文件
- [ ] README.md 渲染正常

## 6. 如果不小心传了不该传的(应急)

如果某个版权文件被 push 到公开仓库了,**仅删除最新文件还不够**,git 历史里还有。需要:

```bash
# 安装 git-filter-repo
pip install git-filter-repo

# 从全部历史里抹掉某个文件
git filter-repo --path "系统规划与管理师教程第2版.pdf" --invert-paths

# 强推覆盖远端(注意:这会破坏所有协作者的本地副本)
git push origin main --force
```

最后到 GitHub 仓库 Settings → 联系 GitHub Support 请求清除缓存。

## 7. 加一些 GitHub 仓库元信息(可选但推荐)

仓库 Settings:
- **About** 区填写描述:`软考"系统规划与管理师"中级备考的本地 Web 应用,集成 FSRS 闪卡 / RAG 问答 / AI 出题与评分 / 全真模考`
- **Topics** 加几个:`exam-prep`, `soft-exam`, `srs`, `fsrs`, `rag`, `fastapi`, `chinese`
- 关闭 **Issues** 之外的不需要功能(Wiki/Projects/Discussions),Issues 留着收反馈

## 完成

之后日常 push:

```bash
git add .
git commit -m "feat: 新增 ..."     # 或 fix:/docs:/refactor: 等前缀
git push
```
