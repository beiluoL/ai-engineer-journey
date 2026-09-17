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

| # | Milestone | 核心能力 |
|---|-----------|----------|
| 01 | Document Ingestion | 文档加载 / 解析 / PDF / Markdown |
| 02 | Chunking | 切分策略 / chunk size / overlap |
| 03 | Embedding | 文本向量化 / Embedding 模型 |
| 04 | Vector Database | Chroma / FAISS / 向量存储 |
| 05 | Retrieval | 向量检索 / 相似性搜索 |
| 06 | Similarity Search | 余弦相似度 / 欧氏距离 |
| 07 | Rerank | 重排序 / Cross-Encoder |
| 08 | Context Assembly | 上下文组装 / Prompt 拼接 |
| 09 | RAG Pipeline | 完整 Pipeline 整合 |
| 10 | RAG Evaluation | RAG 效果评估 |

## 当前状态

⬜ 未开始

## 当前版本

还未开始。

## 项目结构

```
src/
└── （Personal RAG）
```

## 已掌握能力

- Project 01-03 的所有能力

## 下一步

完成 Project 03，然后开始 RAG 构建。

**前置项目**：[Project 03 — AI Application](../03-ai-application/)
