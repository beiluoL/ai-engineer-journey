# 03-embedding-rag — Phase 3：Embedding / RAG

> 让 LLM 不再「胡说」，给它装上可检索的私有知识库。

## 这一阶段学什么

- Token 与 Embedding 向量表示
- 文本分块（Chunk）策略
- 向量库（Chroma / FAISS）
- RAG 检索增强生成流程
- Rerank 重排序优化
- 混合检索（关键词 + 向量）

## 为什么学

LLM 知识截止、不了解私有数据、容易幻觉。RAG 是当前最实用的解决方案：把外部知识检索后喂给 LLM。学完就能做企业知识库、文档问答助手。

## 前置知识

- [Phase 2 — AI Application](../02-ai-application/)

## 核心技能

- 用 Embedding 把文本转向量
- 设计合理的 Chunk 大小与重叠
- 用 Chroma / FAISS 存储与检索
- 拼接检索结果到 Prompt
- 用 Rerank 提升相关性
- 评估 RAG 召回质量

## 项目

| 项目 | 说明 |
|------|------|
| Project 03 | 文档助手：单文档问答 |
| Project 04 | 知识库：多文档检索 + RAG |

## 完成标准

- Project 03 / 04 可运行，能回答文档内问题
- 能解释 Embedding 相似度计算原理
- 能调参 Chunk 大小并对比效果
- 实现带 Rerank 的两阶段检索

## 下一阶段

[Phase 4 — Agent / Tool / MCP](../04-agent-tool-mcp/)
