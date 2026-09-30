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
| Project 08 milestones | ✅ 9/9 已成文（fine-tuning → dataset-preparation → instruction-tuning → lora → qlora → training-configuration → checkpoint → merge-adapter → evaluation） |
| Project 08 src + tests | ✅ v1.0 落地：`src/ft/` 12 个手写模块（LoRA / NF4 分位量化 + 双量化 / QLoRA / 指令数据答案区 mask / 只训 adapter 的训练器 / 断点续训 / Adapter 合并 / 评估），189 项 pytest 全绿；主线叙事「通用基座 → 冻结 → 注入 LoRA → Java 面试领域 SFT → 评估」；实测：B 零初始化等价性误差 0.000e+00、grad_check 6.585e-05、基座改动 0/28、LoRA 可训练 10.53%、NF4 压缩 7.75×、域内困惑度 3649.9→421.1；9 张真实终端截图 + 9 张手写架构图 SVG |
| Project 09 milestones | ✅ 11/11 已成文（evaluation → benchmark → evaluation-dataset → automatic-evaluation → model-comparison → quantization → inference-engine → paged-attention → batching → kv-cache → model-serving） |
| Project 09 src + tests | ✅ v1.0 落地：`src/ie/` 13 个手写模块（评估指标含 ECE 校准 / 防泄漏评估集 / 零 LLM 规则评分 / 多种子配对比较 / INT8·INT4·NF4 量化 / 手写自回归引擎 / PagedAttention 分块 KV / Continuous Batching 仿真 / KV 显存账本 / 标准库 HTTP 服务含 SSE），229 项 pytest 全绿；实测：KV Cache 6.155→2.794 ms（2.20×）、PagedAttention 浪费率 76.4%→16.0%、Continuous Batching 吞吐 1.52×、4 并发 4/4（p95 3.311 ms）；关键反直觉结论「权重 MSE 最小 ≠ 端到端最优」；11 张真实终端截图 + 11 张手写架构图 SVG |
| Project 10 milestones | ✅ 11/11 已成文（architecture → tokenizer → dataset → embedding → transformer-block → training → evaluation → inference → optimization → serving → complete-system） |
| Project 10 src + tests | ✅ v1.0 落地：`src/tiny/` 12 个手写模块（唯一配置入口 `TinyConfig` + BPE 分词含归因报告 / 防泄漏数据集 + 滑动窗口打包 / 手写 Transformer Decoder / 训练闭环含早停回滚与断点续训 / 三层评估 + 配对显著性 / 采样四旋钮 + 真·流式 + KV Cache / 量化 ΔPPL + 显存账本 / OpenAI 兼容服务 + 冒烟 + 压测 / 八段流水线），71 项 pytest 全绿；**三层复用 P06/P08/P09**（手写 autograd + 确定性补丁 + 评估/量化/服务）；实测：BPE 压缩 1.445 字/token、UNK 0.33%、val roundtrip 失败 14/14 全归因 OOV；因果自检过去误差 0.000e+00 / 未来 1.191e+01、确定性 0.000e+00；train 7.1547→3.6882 / val 6.2283→5.7551（第 800 步）→5.8234，**早停回滚**；跨进程重训/续训误差 0.000e+00；PPL 315.79 / token_acc 0.1736 / ECE 0.0662；KV Cache 等价 3.442e-15、TTFT 0.20 ms vs 总耗时 4.73 ms；INT8 3.85×/ΔPPL +0.08%、INT4 7.42×/+2.66%、NF4 7.75×/+4.01%；全链路有缓存 0.928 s；11 张真实终端截图 + 11 张手写架构图 SVG |
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
| 08 | LoRA / QLoRA Fine-Tuning | ⬜ | ✅ v1.0 从零手写 LoRA/QLoRA（纯 numpy，复用 P06 手写 autograd）+ 测试 189 passed + 9 个真实 demo（域内困惑度 3649.9→421.1）+ 9 张真实终端截图 + 9 张手写 SVG + M01-09 全成 |
| 09 | LLM Evaluation / Inference | ⬜ | ✅ v1.0 从零手写评估体系 + 量化 + 推理引擎（纯 numpy + 标准库 http.server）+ 测试 229 passed + 11 个真实 demo（KV Cache 2.20×、PagedAttention 浪费率 76.4%→16.0%、Continuous Batching 1.52×）+ 11 张真实终端截图 + 11 张手写 SVG + M01-11 全成 |
| 10 | Tiny LLM Capstone | ⬜ | ✅ v1.0 从零串起 LLM 全链路（BPE 分词 → 数据集 → Transformer Decoder → 训练闭环 → 三层评估 → 推理 → 量化 → 服务 → 八段流水线）+ 71 项 pytest 全绿 + 11 个真实 demo（PPL 315.79、早停回滚到第 800 步、KV Cache 等价 3.442e-15、INT8 3.85×/ΔPPL +0.08%、全链路 0.928 s）+ 11 张真实终端截图 + 11 张手写 SVG + M01-11 全成 |

## Next

1. 动手复现 `exercises/01-basic` 8 题：先自己敲，再对照 `answers.py`，把 🎓 从「参考答案已判卷」变成「我真的会了」
2. Project 04 下一步：有 cross-encoder 权限后替换 LLMReranker 并重扫阈值；前端 UI 可继续打磨（Markdown 渲染、深色模式、移动端）
3. P02 学习进度推进：读完 `OVERVIEW.md` + 10 章，对着 `src/` 逐文件看

## 维护工具

```bash
python3 scripts/check_links.py --strict   # 死链 + 坏图体检（CI 也在跑）
cd projects/01-python-ai-cli/src && python3 -m unittest discover -s tests
```
