# 04-agent-tool-mcp — Phase 4：Agent / Tool / MCP

> 让 LLM 从「回答」进化到「行动」，能调工具、做规划、接外部系统。

## 这一阶段学什么

- Function Calling / Tool Calling
- Agent 架构与 ReAct 范式
- 短期 / 长期 Memory
- Planning 与任务拆解
- MCP（Model Context Protocol）
- 多步工具编排与错误恢复

## 为什么学

真实 AI 应用不止是问答，还要让模型自主调用搜索、代码执行、数据库等工具。Agent + Tool 是 LLM 走向生产的核心能力，MCP 则是统一的工具接入标准。

## 前置知识

- [Phase 3 — Embedding / RAG](../03-embedding-rag/)

## 核心技能

- 定义并注册 Tool / Function Schema
- 实现 ReAct 风格的 Agent 循环
- 用 Memory 管理多轮上下文
- 让 LLM 拆解多步任务
- 接入 MCP Server 调用外部工具
- 处理工具调用失败与重试

## 项目

| 项目 | 说明 |
|------|------|
| Project 05 | Research Agent：自动搜索 + 摘要 + 输出报告 |

## 完成标准

- Project 05 可运行，能完成多步研究任务
- 能解释 ReAct 与纯 RAG 的差异
- 实现至少一个 MCP 工具接入
- Agent 能在工具失败时优雅降级

## 下一阶段

[Phase 5 — PyTorch](../05-pytorch/)
