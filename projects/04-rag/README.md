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

状态：✅ 内容已就绪 · 🔄 代码落地中 · ⬜ 未开始

## 当前状态

**10 / 10 个 Milestone 已全部成文**（文档先行，作为 `src/` 落地的设计依据）。

## 当前版本

**v0.1 文档就绪**，`src/` 待落地：目标是把 `chunker.py` / `embeddings.py` / `vector_store.py` / `retriever.py` / `reranker.py` / `context.py` / `pipeline.py` 真实跑通。

## 项目结构

```text
src/rag/                # 五层结构（见 09 章，呼应 P03）
├── cli.py  api.py      # 接入层（计划：复用 P03 的 FastAPI + SSE 模式）
├── pipeline.py  service.py   # 编排层（索引链路 + 问答链路）
├── parser.py  chunker.py  retriever.py  reranker.py  context.py  # 能力层
├── embeddings.py  vector_store.py            # 模型/存储层（唯一知道 API 与库细节）
└── settings.py  errors.py  evaluate.py       # 支撑层 / 评估
tests/                  # 全部离线（FakeEmbeddingClient + InMemoryVectorStore）
```

## 已掌握能力

- Project 01-03 的所有能力（Python 工程化、async、FastAPI、pytest、Prompt / 流式 / 工具调用）

## 下一步

1. 按 10 章文档落地 `src/`，真实跑通两条链路：离线索引（parse → chunk → embed → store）与在线问答（retrieve → rerank → assemble → llm）
2. 跑通后配真实运行截图，P04 从「文档就绪」转为「文档 + 代码」双全
3. Embedding 用 SiliconFlow（bge-m3）真实调通；向量库先 InMemory + Chroma，Milvus 留给生产篇

**前置项目**：[Project 03 — AI Application](../03-ai-application/)
