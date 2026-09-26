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

状态：✅ 内容已就绪 · ✅ 代码已落地 · ✅ 测试全绿 · ✅ 已配真实运行截图

## 当前状态

**12 / 12 个 Milestone 文档 + `src/rag/` + 离线/真实服务测试 + 真实运行截图** 全部完成。RAG 两条链路（离线索引 `parse → chunk → embed → store`、在线问答 `retrieve → rerank → assemble → llm`）已跑通；新增真实 embedding + Chroma 持久化、真实 LLM + 忠实度审计两章。

## 当前版本

**v0.4 真实 LLM 可跑**：`src/rag/` 共 15 个模块，129 项 pytest 全绿。真实链路已跑通：

- `DashScopeEmbeddingClient` 接百炼 `text-embedding-v3`
- `ChromaVectorStore` 落盘 `chroma_db/rag_chunks/`，重启后数据可恢复
- `DeepSeekLLMClient` 接入 RAGService；`RAGAnswer.system_prompt` 留档可回放
- 忠实度审计 + 注入式自测，可离线验证审计判据有区分度
- CLI 支持 `--index` 与 `--ask --fake` 全离线演示；`demo_12/13` 支持真实服务全流程演示

## 项目结构

```text
projects/04-rag/
├── data/               # 示例知识库（真实 .md/.txt 样本）
├── demos/              # 12 个真实运行 demo + 1 个 pytest 运行脚本
├── src/rag/            # 五层结构（见 09 章，呼应 P03）
│   ├── cli.py          # 接入层：python -m rag.cli --index/--ask
│   ├── pipeline.py     # 编排层：IngestionPipeline + RAGService
│   ├── retriever.py    # 能力层：vector / hybrid(RRF) / MMR
│   ├── reranker.py     # 能力层：BaseReranker + NoopReranker + FakeReranker
│   ├── assembler.py    # 能力层：ContextAssembler（编号溯源 + token 预算）
│   ├── chunker.py      # 能力层：chunk_text / recursive_split
│   ├── parsing.py      # 能力层：BaseParser + Txt/Md/Pdf/Docx
│   ├── embedding.py    # 模型层：BaseEmbeddingClient + SiliconFlow/Fake
│   ├── store.py        # 模型层：BaseVectorStore + InMemory/Chroma
│   ├── similarity.py   # 支撑层：cosine + NumPy 矩阵实现
│   ├── evaluation.py   # 支撑层：EvalCase + EvalReport + evaluate
│   ├── models.py       # 支撑层：Document / Chunk / ScoredChunk
│   ├── settings.py     # 支撑层：frozen RAGSettings
│   ├── errors.py       # 支撑层：RAGError 层级
│   └── llm.py          # 复用/兼容层：LLMClient 封装
├── tests/              # 全部离线（FakeEmbeddingClient + InMemoryVectorStore）
└── assets/             # 18 张真实运行截图
```

## 已掌握能力

- Project 01-03 的所有能力（Python 工程化、async、FastAPI、pytest、Prompt / 流式 / 工具调用）
- 文档解析、Chunk 切分、Embedding 向量化、向量检索（hybrid + MMR）、重排序、上下文组装
- 可离线跑通的完整 RAG 流水线，120 项 pytest 验证
- 真实 embedding（百炼 text-embedding-v3）与 Chroma 持久化落盘，重启恢复验证
- 真实 LLM（DeepSeek）生成、token 计量、拒答闸门、流式接入
- 忠实度审计，逐句标出无出处内容，并可用注入式自测验证判据

## 下一步

1. 复用 P03 的 FastAPI + SSE 模式，给 RAG 加上 Web API（`api.py`）
2. 做真实 RAG 评估：手写 20–50 条 EvalCase，跑 Hit Rate@k / MRR / 忠实度
3. 接入真实 reranker（可选增强）
4. 监控与可观测：记录检索 latency、召回分数分布、embedding/llm 调用次数

**前置项目**：[Project 03 — AI Application](../03-ai-application/)
