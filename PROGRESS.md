# AI Engineer Journey — Progress

> **双轨制**：「内容生产」（仓库里写了什么）与「学习进度」（我是否真正掌握）分开记录。
> 铁律：**文档就绪 ≠ 已学习**。内容标记 📝 草稿 / ✅ 已校对 / 🎓 已学习。

## 学习进度（Track 1 — 以「我是否掌握」为准）

### Current

**Project 01 — Python AI CLI Assistant** · Milestone 02 已学习

```text
✅ 01 — Variables（已学习：亲手敲过 Demo + 练习）
🎓 02 — List / Dict / JSON（已学习：参考答案已跑通并判卷 8/8）
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
| Project 01 milestones 01-10 | ✅ 全部成文；01-10 每章均配真实运行截图 |
| Project 01 src + tests | ✅ v0.2 骨架，6 个 unittest 全绿（已实测真实调用 DeepSeek API 成功） |
| Project 01 exercises | ✅ 01-basic 8 题参考答案已跑通并判卷 8/8 🎓；02 / 03 / 04 已播种（待做） |
| Project 02 milestones | ✅ 10/10 全部已校对；每章均配真实运行截图 |
| Project 02 src | ✅ v0.2 完整落地：async CLI + FastAPI（/chat、SSE 流式、/health），33 项 pytest 离线全绿，真实调通 DeepSeek |
| Project 03 milestones | ✅ 9/9 全部成文；每章均配真实运行截图 |
| Project 03 src + tests | ✅ v0.2 落地：cli/api/service/agent + 五层代码，61 项 pytest 离线全绿，4 条路径配真实运行截图 |
| Project 04 milestones | ✅ 14/14 全部成文（ingestion → chunking → embedding → vector db → retrieval → similarity → rerank → context → pipeline → evaluation → real-service → real-llm → fastapi-web-api → real-rag-evaluation） |
| Project 04 src | ✅ v0.5 落地：17 个模块，142 项 pytest 全绿，Fake + InMemory/Chroma 离线链路、DashScope 真实 embedding + DeepSeek 真实 LLM + FastAPI Web API（SSE）+ 真实 RAG 评估均已跑通，14 章全部配真实运行截图 |
| Project 05-10 | ⬜ 未开始 |
| publishing/tutorials | ✅ 6 篇图文教程已发布（md + html） |
| publishing/finetune-series | 📝 35 篇草稿（命名已规范化，内容未校对，择优转正 tutorials） |
| publishing/articles | 📝 2 篇 |
| CI | ✅ GitHub Actions：单测 + 死链坏图扫描 + 密钥文件检查 |

## 10 项目状态总览

| # | 项目 | 学习进度 | 内容状态 |
|---|------|---------|---------|
| 01 | Python AI CLI Assistant | 🎓 M02 | ✅ v0.2 |
| 02 | Engineering AI Assistant | ⬜ | ✅ v0.2 CLI + API 双形态 |
| 03 | AI Application | ⬜ | ✅ v0.2 文档+代码+测试 |
| 04 | AI Knowledge Base / RAG | ⬜ | ✅ v0.5 文档+代码+测试+真实服务截图+真实 LLM+忠实度审计+FastAPI Web API+真实 RAG 评估 |
| 05 | Research Agent / MCP | ⬜ | ⬜ |
| 06 | Mini Transformer / LLM | ⬜ | ⬜ |
| 07 | Open Source LLM | ⬜ | ⬜ |
| 08 | LoRA / QLoRA Fine-Tuning | ⬜ | ⬜ |
| 09 | LLM Evaluation / Inference | ⬜ | ⬜ |
| 10 | Tiny LLM Capstone | ⬜ | ⬜ |

## Next

1. 动手复现 `exercises/01-basic` 8 题：先自己敲，再对照 `answers.py`，把 🎓 从「参考答案已判卷」变成「我真的会了」
2. Project 04 下一步：接入真实 reranker；加监控与可观测（latency / 召回分数分布 / 调用次数）
3. P02 学习进度推进：读完 `OVERVIEW.md` + 10 章，对着 `src/` 逐文件看

## 维护工具

```bash
python3 scripts/check_links.py --strict   # 死链 + 坏图体检（CI 也在跑）
cd projects/01-python-ai-cli/src && python3 -m unittest discover -s tests
```
