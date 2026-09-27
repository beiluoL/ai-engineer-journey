# Project 04 — AI Knowledge Base / RAG Assistant

## 项目目标

给 AI 加上外部知识，构建真正的 RAG【检索增强生成】系统。

## 为什么做这个项目

LLM 有知识截止日期，而且幻觉不可避免。RAG 让模型能检索外部知识，是目前生产级 AI 应用的标配能力。

## 解决什么问题

- LLM 不知道最新信息（知识截止日期）
- LLM 可能编造事实（幻觉）
- 私有知识（文档 / 数据库）无法直接给 LLM 用

## 最终能力

```text
Document
    ↓
Parsing
    ↓
Chunk
    ↓
Embedding
    ↓
Vector Database
    ↓
Retrieval
    ↓
Rerank
    ↓
Context
    ↓
LLM
    ↓
Answer
```

## 技术栈

- Document Ingestion（文档解析）
- Chunking（文档切分）
- Embedding（文本向量化）
- Vector Database（Chroma / FAISS / Milvus）
- Retrieval（检索）
- Rerank（重排序）

## 项目演进

```
AI Chat Web
    ↓ Document Ingestion
Personal RAG v0.1
    ↓ Embedding + Vector DB
Personal RAG v0.2
    ↓ Retrieval + Rerank + Pipeline
Personal RAG v1.0
```

## Milestones

| # | Milestone | 状态 | 核心能力 |
|---|-----------|------|----------|
| 01 | [Document Ingestion](milestones/01-document-ingestion.md) | ✅ | 文档加载 / 解析 / PDF / Markdown |
| 02 | [Chunking](milestones/02-chunking.md) | ✅ | 切分策略 / chunk size / overlap |
| 03 | [Embedding](milestones/03-embedding.md) | ✅ | 文本向量化 / Embedding 模型 |
| 04 | [Vector Database](milestones/04-vector-database.md) | ✅ | Chroma / FAISS / 向量存储 |
| 05 | [Retrieval](milestones/05-retrieval.md) | ✅ | 向量检索 / 混合检索 / MMR |
| 06 | [Similarity Search](milestones/06-similarity-search.md) | ✅ | 余弦相似度 / 欧氏距离 |
| 07 | [Rerank](milestones/07-rerank.md) | ✅ | 重排序 / Cross-Encoder |
| 08 | [Context Assembly](milestones/08-context-assembly.md) | ✅ | 上下文组装 / 引用溯源 |
| 09 | [RAG Pipeline](milestones/09-rag-pipeline.md) | ✅ | 完整 Pipeline 整合 |
| 10 | [RAG Evaluation](milestones/10-rag-evaluation.md) | ✅ | Hit Rate / MRR / 忠实度 |
| 11 | [Real Service Integration](milestones/11-real-service-integration.md) | ✅ | 真实 embedding + Chroma 持久化 |
| 12 | [Real LLM Integration](milestones/12-real-llm-integration.md) | ✅ | 真实 LLM 生成 + 忠实度审计 |
| 13 | [FastAPI Web API](milestones/13-fastapi-web-api.md) | ✅ | POST /ask + SSE /ask/stream |
| 14 | [Real RAG Evaluation](milestones/14-real-rag-evaluation.md) | ✅ | 30 条 EvalCase + 真实 embedding/LLM 评估 |
| 15 | [Observability](milestones/15-observability.md) | ✅ | metrics 埋点：latency / 分数分布 / 调用计数 |
| 16 | [Real Reranker & Calibration](milestones/16-real-reranker-and-calibration.md) | ✅ | LLM 精排 A/B + min_score 阈值校准 + 指标跨进程对比 |
| 17 | [Chat UI & Session History](milestones/17-chat-ui-and-session-history.md) | ✅ | 前端 Chat UI / 会话历史 / 多轮追问 |

状态：✅ 内容已就绪 · ✅ 代码已落地 · ✅ 测试全绿 · ✅ 已配真实运行截图

## 当前状态

**17 / 17 个 Milestone 文档 + `src/rag/` + 离线/真实服务测试 + 真实运行截图** 全部完成。RAG 两条链路（离线索引 `parse → chunk → embed → store`、在线问答 `retrieve → rerank → assemble → llm`）已跑通；新增真实 embedding + Chroma 持久化、真实 LLM、FastAPI Web API、真实 RAG 评估、可观测性、真实精排与阈值校准六章。

## 当前版本

**v0.8 产品化**：`src/rag/` 共 19 个模块 + `web/` 原生前端，197 项 pytest 全绿。真实链路已跑通：

- `DashScopeEmbeddingClient` 接百炼 `text-embedding-v3`
- `ChromaVectorStore` 落盘 `chroma_db/rag_chunks/`，重启后数据可恢复
- `DeepSeekLLMClient` 接入 RAGService；`RAGAnswer.system_prompt` 留档可回放
- 忠实度审计 + 注入式自测，可离线验证审计判据有区分度
- FastAPI Web API：`POST /ask` + `POST /ask/stream`（SSE）+ `/health` + `/stats` + `/index`
- 30 条手写 EvalCase，真实 embedding + DeepSeek 跑出完整评估报告
- 可观测性：`MetricsRegistry` + 计量壳（embedding/LLM），四段耗时、分数分桶、`/stats` 直接读
- 真实精排 `LLMReranker`（DeepSeek listwise）：MRR 0.711→0.767；`min_score` 按 F1 扫描校准（余弦量纲最优 0.60）
- 指标落盘 `--save/--baseline` 跨进程对比，20% 容忍带不误报
- 前端零构建 Chat UI：会话列表 / 流式打字 / 引用来源 / 中止生成；SSE 增量渲染 + 历史自动落库
- CLI 支持 `--index` 与 `--ask --fake` 全离线演示；`demo_12/13/14/15/16/17/18` 支持真实服务全流程演示

## 项目结构

```text
projects/04-rag/
├── data/               # 示例知识库 + 30 条 EvalCase；会话落盘 data/sessions/（可选）
├── demos/              # 18 个真实运行 demo（demo_01～18）+ 公共装置
├── src/rag/            # 五层结构（见 09 章，呼应 P03）
│   ├── api.py          # 接入层：FastAPI Web API（SSE 流式 + 会话端点 + 静态页挂载）
│   ├── cli.py          # 接入层：python -m rag.cli --index/--ask
│   ├── pipeline.py     # 编排层：IngestionPipeline + RAGService（支持多轮 history）
│   ├── session.py      # 会话层：Turn / Session / 内存与 JSON 文件存储（17 章）
│   ├── retriever.py    # 能力层：vector / hybrid(RRF) / MMR
│   ├── reranker.py     # 能力层：Noop / Fake / SiliconFlow / LLMReranker（16 章）
│   ├── assembler.py    # 能力层：ContextAssembler（编号溯源 + token 预算）
│   ├── chunker.py      # 能力层：chunk_text / recursive_split
│   ├── parsing.py      # 能力层：BaseParser + Txt/Md/Pdf/Docx
│   ├── embedding.py    # 模型层：BaseEmbeddingClient + SiliconFlow/Fake
│   ├── store.py        # 模型层：BaseVectorStore + InMemory/Chroma
│   ├── similarity.py   # 支撑层：cosine + NumPy 矩阵实现
│   ├── evaluation.py   # 支撑层：EvalCase + EvalReport + evaluate
│   ├── metrics.py      # 支撑层：MetricsRegistry + 计量壳（15 章）
│   ├── models.py       # 支撑层：Document / Chunk / ScoredChunk
│   ├── settings.py     # 支撑层：frozen RAGSettings
│   ├── errors.py       # 支撑层：RAGError 层级
│   └── llm.py          # 复用/兼容层：LLMClient 封装
├── tests/              # 全部离线（FakeEmbeddingClient + InMemoryVectorStore）
├── web/                # 17 章：零构建原生 Chat UI（index.html / style.css / app.js）
└── assets/             # 44 张真实运行截图
```

## 已掌握能力

- Project 01-03 的所有能力（Python 工程化、async、FastAPI、pytest、Prompt / 流式 / 工具调用）
- 文档解析、Chunk 切分、Embedding 向量化、向量检索（hybrid + MMR）、重排序、上下文组装
- 可离线跑通的完整 RAG 流水线，120 项 pytest 验证
- 真实 embedding（百炼 text-embedding-v3）与 Chroma 持久化落盘，重启恢复验证
- 真实 LLM（DeepSeek）生成、token 计量、拒答闸门、流式接入
- 忠实度审计，逐句标出无出处内容，并可用注入式自测验证判据
- 真实 RAG 评估：30 条 EvalCase，top_k 对照、忠实度审计、可复现性验证
- 可观测性：四段耗时占比、召回分数分桶、embedding/LLM 调用计数（并发安全）
- 产品化：零构建前端 Chat UI、会话历史、多轮追问

## 下一步

1. 有 cross-encoder 权限后，把 `LLMReranker` 换成 `bge-reranker-v2-m3`（阈值重扫一遍）
2. 把 pytest/CI 接到 GitHub Actions，PR 上跑 check_links + 全量测试
3. 前端 UI 继续打磨：移动端适配、Markdown 渲染、代码块高亮、深色模式

**前置项目**：[Project 03 — AI Application](../03-ai-application/)
