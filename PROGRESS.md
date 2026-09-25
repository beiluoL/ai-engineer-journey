# AI Engineer Journey — Progress

> **双轨制**：「内容生产」（仓库里写了什么）与「学习进度」（我是否真正掌握）分开记录。
> 铁律：**文档就绪 ≠ 已学习**。内容标记 📝 草稿 / ✅ 已校对 / 🎓 已学习。

## 学习进度（Track 1 — 以「我是否掌握」为准）

### Current

**Project 01 — Python AI CLI Assistant** · Milestone 02 学习中

```text
✅ 01 — Variables（已学习：亲手敲过 Demo + 练习）
🔄 02 — List / Dict / JSON（学习中）
⬜ 03 — Condition / Loop
⬜ 04 — Function
⬜ 05 — Module / Package
⬜ 06 — Exception
⬜ 07 — File / JSON Persistence
⬜ 08 — venv / pip / Environment
⬜ 09 — HTTP / API
⬜ 10 — Real LLM API（串起所有知识，v1.0 完成）
```

### 已掌握能力

- Python 变量、基础类型、type()、input()、print()、f-string
- List / Dict 嵌套、JSON 序列化、AI messages 数据结构
- 能读懂并运行真实 LLM API 调用骨架

## 内容生产（Track 2 — 以「仓库里有什么」为准）

| 部分 | 状态 |
|------|------|
| Project 01 milestones 01-10 | ✅ 全部成文；08 / 09 / 10 与 README 已配真实运行截图 |
| Project 01 src + tests | ✅ v0.2 骨架，6 个 unittest 全绿（已实测真实调用 DeepSeek API 成功） |
| Project 01 exercises | ✅ 01-basic 有 8 题 + 参考答案；02 / 03 / 04 已播种（待做） |
| Project 02 milestones | 10/10 齐备：6 篇已校对（00/05/06/07/08/09），4 篇迁移草稿待校对（01-04） |
| Project 02 src | ✅ v0.2 完整落地：async CLI + FastAPI（/chat、SSE 流式、/health），33 项 pytest 离线全绿，真实调通 DeepSeek |
| Project 03-10 | ⬜ 空壳（README 就绪） |
| publishing/tutorials | ✅ 4 篇图文教程已发布（md + html） |
| publishing/finetune-series | 📝 35 篇草稿（命名已规范化，内容未校对，择优转正 tutorials） |
| publishing/articles | 📝 2 篇 |
| CI | ✅ GitHub Actions：单测 + 死链坏图扫描 + 密钥文件检查 |

## 10 项目状态总览

| # | 项目 | 学习进度 | 内容状态 |
|---|------|---------|---------|
| 01 | Python AI CLI Assistant | 🔄 M02 | ✅ v0.2 |
| 02 | Engineering AI Assistant | ⬜ | ✅ v0.2 CLI + API 双形态 |
| 03 | AI Application | ⬜ | ⬜ |
| 04 | AI Knowledge Base / RAG | ⬜ | ⬜ |
| 05 | Research Agent / MCP | ⬜ | ⬜ |
| 06 | Mini Transformer / LLM | ⬜ | ⬜ |
| 07 | Open Source LLM | ⬜ | ⬜ |
| 08 | LoRA / QLoRA Fine-Tuning | ⬜ | ⬜ |
| 09 | LLM Evaluation / Inference | ⬜ | ⬜ |
| 10 | Tiny LLM Capstone | ⬜ | ⬜ |

## Next

1. 做完 `exercises/01-basic` 的 8 题（**先自己敲，再对照 `answers.py`**）→ M02 标记 🎓
2. Project 02 收尾：逐篇校对迁移草稿（01-04），P02 学习进度推进
3. 校对 finetune-series 草稿，择优改写为 tutorial 05+；顺手修掉 Day1-10 重复的文内标题
4. 逐篇校对 Project 02 迁移草稿（01-04，📝 → ✅）

## 维护工具

```bash
python3 scripts/check_links.py --strict   # 死链 + 坏图体检（CI 也在跑）
cd projects/01-python-ai-cli/src && python3 -m unittest discover -s tests
```
