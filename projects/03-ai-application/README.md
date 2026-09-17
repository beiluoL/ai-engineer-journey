# Project 03 — AI Application

## 项目目标

从 Service 升级到真正的 AI 应用层，掌握 LLM Application【大模型应用】核心能力。

## 为什么做这个项目

会调 API 不等于会做应用。LLM Application 有自己的核心问题：Prompt 设计、流式输出、函数调用、结构化输出——这些是每个 AI 工程师每天都在处理的事情。

## 解决什么问题

- Prompt 怎么写才能让模型稳定输出？
- 怎么让用户看到打字机效果（Streaming）？
- 怎么让模型返回 JSON 而不是自然语言？
- 怎么让模型调用外部程序？

## 最终能力

```text
调用 LLM
    ↓
控制模型
    ↓
管理上下文
    ↓
获取结构化结果
    ↓
调用外部程序能力
    ↓
形成完整 AI Application
```

## 技术栈

- Prompt Engineering 方法论
- Streaming / SSE（Server-Sent Events）
- Function Calling / Tool Use
- Structured Output（Pydantic + JSON Mode）
- Multi-turn Conversation Management
- Token / Context Window 管理

## 项目演进

```
Engineering AI Assistant Service
    ↓ Prompt + Streaming
AI Chat Web v0.1
    ↓ Function Calling + Structured Output
AI Chat Web v0.2
    ↓ 前端 Chat UI
AI Chat Web v1.0
```

## Milestones

| # | Milestone | 核心能力 |
|---|-----------|----------|
| 01 | Prompt | Prompt 工程基础 / 模板化 |
| 02 | System / User / Assistant Messages | 对话角色 / 消息格式 |
| 03 | Structured Output | JSON Mode / Pydantic / Schema |
| 04 | Streaming | SSE / 打字机效果 |
| 05 | Conversation Memory | 多轮对话 / 上下文管理 |
| 06 | Model Parameters | temperature / max_tokens / top_p |
| 07 | Token / Context Window | Token 计数 / 上下文窗口限制 |
| 08 | Function Calling | 函数调用 / 参数定义 / 结果解析 |
| 09 | AI Application Architecture | 完整 AI 应用架构 |

## 当前状态

⬜ 未开始

## 当前版本

还未开始。

## 项目结构

```
src/
└── （AI Chat Web 前端 + 后端）
```

## 已掌握能力

- Project 01-02 的所有能力

## 下一步

完成 Project 02，然后开始 AI Application 构建。

**前置项目**：[Project 02 — Engineering AI Assistant](../02-engineering-ai-assistant/)
