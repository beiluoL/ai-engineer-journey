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

### Project 02 / 03 —— 自测清单已就位，尚无章节被标记为已学习

> 判定规则（写在这里防止自欺）：**参考答案跑通只证明答案没错，不证明我会了。**
> AI 不替任何一章打勾。做完题 → 能讲清「为什么」→ 才由你本人把 ⬜ 改成 ✅。

| Chapter | 自测清单 | 状态 |
|---|---|---|
| P02 M00–M09（10 章） | [LEARNING.md](projects/02-engineering-ai-assistant/LEARNING.md) + 29 题 | ⬜ 未开始 |
| P03 M01–M09（9 章） | [LEARNING.md](projects/03-ai-application/LEARNING.md) + 32 题 | ⬜ 未开始 |

## 内容生产（Track 2 — 以「仓库里有什么」为准）

| 部分 | 状态 |
|------|------|
| Project 01 milestones 01-10 | ✅ 全部成文；每章 2 张真实运行截图（assets 共 22 张，新增 08/09 两个真实可跑 demo） |
| Project 01 src + tests | ✅ v0.2 骨架，6 个 unittest 全绿（已实测真实调用 DeepSeek API 成功） |
| Project 01 exercises | ✅ 01-basic 8 题参考答案已跑通并判卷 8/8 🎓；02 / 03 / 04 已播种（待做） |
| Project 02 milestones | ✅ 10/10 全部已校对；每章 2 张真实运行截图（assets 共 23 张，新增 async-http / config / logging / fastapi 四个真实 demo） |
| Project 02 src | ✅ v0.2 完整落地：async CLI + FastAPI（/chat、SSE 流式、/health），33 项 pytest 离线全绿，真实调通 DeepSeek |
| Project 03 milestones | ✅ 9/9 全部成文；每章 2 张真实运行截图（assets 共 18 张，新增 prompt / structured / stream / agent / architecture 五个真实 demo） |
| Project 03 src + tests | ✅ v0.2 落地：cli/api/service/agent + 五层代码，61 项 pytest 离线全绿，4 条路径配真实运行截图 |
| Project 04 milestones | ✅ 17/17 全部成文（ingestion → … → fastapi-web-api → real-rag-evaluation → observability → real-reranker-and-calibration → chat-ui-and-session-history） |
| Project 04 src | ✅ v0.8 落地：19 个模块 + `web/` 原生前端，197 项 pytest 全绿，Fake + InMemory/Chroma 离线链路、DashScope 真实 embedding + DeepSeek 真实 LLM + FastAPI Web API（SSE）+ 真实 RAG 评估 + 可观测性 + LLMReranker 真实精排与阈值校准 + 前端 Chat UI / 会话历史 / 多轮追问均已跑通，17 章每章 2+ 张真实运行截图（assets 共 44 张） |
| Project 02 exercises | ✅ LEARNING.md 自测清单（10 章）+ 29 道实操题 + 参考答案 + 离线判卷工具；判卷真实跑通 29/29（**这是参考答案成绩，不代表用户已掌握**） |
| Project 03 exercises | ✅ LEARNING.md 自测清单（9 章）+ 32 道实操题 + 参考答案 + 离线判卷工具；判卷真实跑通 32/32（同上，不代用户勾选） |
| Project 05 milestones | ✅ 10/10 已成文（tool → tool-schema → function-calling → agent → agent-loop → multi-step → mcp → mcp-server → mcp-client → workflow） |
| Project 05 src + tests | ✅ v1.0 落地：11 个模块 + `agent/mcp/` 子包（`src/agent/`）+ `ReActAgent` 循环，244 项 pytest 全绿，离线剧本（FakeLLM/ScriptedLLM/RecordingLLM）+ DeepSeek 真实双链路，「检索即工具」已跑通；M05 工作记忆（trim_history token 预算 + 协议配对裁剪）、Scratchpad 草稿纸、第三道闸门 max_repeats；M06 显式 Plan + 依赖拓扑 + 失败传播；M07-09 MCP 协议/Server/Client 跨进程工具桥接；M10 多 Worker 编排 + 上下文隔离；CLI 支持 `--notes`，28 张真实运行截图 |
| publishing/tutorials | ✅ 8 篇图文教程已发布（md + html）；新增 08《Spring Boot 怎么调 Python》（五方案对比 + HTTP/子进程两条真实跑通链路 + 故障演练 + 避坑清单，10 张配图，完整可复现 demo 工程在 tutorials/demos/08-springboot-python/） |
| publishing/finetune-series | 📝 35 篇草稿（命名已规范化，内容未校对，择优转正 tutorials；已转正 Day1/3/4/5） |
| publishing/articles | 📝 2 篇 |
| CI | ✅ GitHub Actions：单测 + 死链坏图扫描 + 密钥文件检查 |

## 10 项目状态总览

| # | 项目 | 学习进度 | 内容状态 |
|---|------|---------|---------|
| 01 | Python AI CLI Assistant | 🎓 M02 | ✅ v0.2 |
| 02 | Engineering AI Assistant | ⬜ | ✅ v0.2 CLI + API 双形态 |
| 03 | AI Application | ⬜ | ✅ v0.2 文档+代码+测试 |
| 04 | AI Knowledge Base / RAG | ⬜ | ✅ v0.8 文档+代码+测试+真实服务截图+真实 LLM+忠实度审计+FastAPI Web API+真实 RAG 评估+可观测性+真实精排与阈值校准+前端 Chat UI / 会话历史 / 多轮追问 |
| 05 | Research Agent / MCP | ⬜ | ✅ v1.0 文档+代码+测试(244)+真实 LLM 双链路+MCP 跨进程工具+Workflow 多 Worker 编排+M01-10 全成+28 张真实截图 |
| 06 | Mini Transformer / LLM | ⬜ | ✅ v1.0 文档+代码+测试(150：51 分词器+99 模型，含梯度校验)+从零 autograd+真实训练 loss 6.21→4.75+M01-10 全成+11 张手写 SVG+10 张真实终端截图 |
| 07 | Open Source LLM | ⬜ | 🔄 v0.1 `pipelines/` 调用管线 6 模块真实跑通：真实调 DeepSeek API（TTFT 占比 39.33%、净生成 284.77 tok/s）+ 手算参数量对账（0.494/1.544/7.615B 对上标称）+ 显存账本（7B bf16 14.18 / int4 3.55 GiB，KV 57,344 B/token）+ RAG-lite 检索评测（recall@1 87.5%、recall@3 100%、全库 11.59ms）+ 6 张真实终端截图；模型加载/量化线待 Colab GPU |
| 08 | LoRA / QLoRA Fine-Tuning | ⬜ | ⬜ |
| 09 | LLM Evaluation / Inference | ⬜ | ⬜ |
| 10 | Tiny LLM Capstone | ⬜ | ⬜ |

## Next

1. 动手复现 `exercises/01-basic` 8 题：先自己敲，再对照 `answers.py`，把 🎓 从「参考答案已判卷」变成「我真的会了」
2. Project 04 下一步：有 cross-encoder 权限后替换 LLMReranker 并重扫阈值；前端 UI 可继续打磨（Markdown 渲染、深色模式、移动端）
3. P02 学习进度推进：读完 `OVERVIEW.md` + 10 章，对着 `src/` 逐文件看

## 维护工具

```bash
python3 scripts/check_links.py --strict   # 死链 + 坏图体检（CI 也在跑）
cd projects/01-python-ai-cli/src && python3 -m unittest discover -s tests
```
