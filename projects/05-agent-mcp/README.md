# Project 05 — Research Agent / MCP Assistant

## 项目目标

让 AI 不只是回答，而是能自主规划和调用工具，变成真正的 Agent【智能体】。

## 为什么做这个项目

RAG 解决了知识问题，但 AI 还不能主动做事。Agent + MCP 是让 AI 从"问答"到"执行多步骤任务"的关键一跃。

## 解决什么问题

- AI 只能按给定 Prompt 回答，不能自主做事
- 需要 AI 调用外部 API / 浏览器 / 数据库
- 需要 AI 分解复杂任务为多步骤

## 最终能力

```text
LLM
    ↓
Tool
    ↓
Tool Calling
    ↓
Agent
    ↓
Multi-Step Agent
    ↓
MCP
    ↓
可扩展 Agent System
```

## 技术栈

- Function Calling 高级用法
- Agent Loop（ReAct / Plan-Execute）
- Tool 设计与注册
- MCP 协议（Model Context Protocol）
- Memory（短期 / 长期）
- Multi-Agent Workflow

## 项目演进

```
Personal RAG
    ↓ Tool / Function Calling
Research Agent v0.1
    ↓ Agent Loop
Research Agent v0.2
    ↓ MCP Protocol
Research Agent v0.3
    ↓ Agent Workflow
Research Agent v1.0
```

## Milestones

| # | Milestone | 核心能力 |
|---|-----------|----------|
| 01 | Tool | 工具设计 / Python 函数作为 Tool |
| 02 | Tool Schema | JSON Schema / 参数定义 |
| 03 | Function Calling | 函数调用深入 / 参数解析 |
| 04 | Agent | Agent 概念 / ReAct 模式 |
| 05 | Agent Loop | 循环推理 / Plan → Act → Observe |
| 06 | Multi-Step Task | 多步骤任务 / 任务分解 |
| 07 | MCP | MCP Protocol 原理 |
| 08 | MCP Server | MCP Server 实现 |
| 09 | MCP Client | MCP Client 实现 |
| 10 | Agent Workflow | 完整 Agent 产品 |

## 当前状态

⬜ 未开始

## 当前版本

还未开始。

## 项目结构

```
src/
└── （Research Agent）
```

## 已掌握能力

- Project 01-04 的所有能力

## 下一步

完成 Project 04，然后开始 Agent 构建。

**前置项目**：[Project 04 — AI Knowledge Base / RAG Assistant](../04-rag/)
