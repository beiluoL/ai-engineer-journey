# Project 05 — Research Agent / MCP Assistant

## 项目目标

让 AI 不只是回答，而是能自主规划和调用工具，变成真正的 Agent【智能体】。

## 为什么做这个项目

RAG 解决了知识问题，但 AI 还不能主动做事。Agent + MCP 是让 AI 从「问答」到「执行多步骤任务」的关键一跃。

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

```text
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

| # | Milestone | 状态 | 核心能力 |
|---|-----------|------|----------|
| 01 | [Tool](milestones/01-tool.md) | ✅ | 工具三件套 / ToolResult / 检索即工具 / 沙箱计算 |
| 02 | [Tool Schema](milestones/02-tool-schema.md) | ✅ | JSON Schema / 签名推导 / 参数纠偏 / 校验拦截 |
| 03 | [Function Calling](milestones/03-function-calling.md) | ✅ | tool 消息三字段 / 协议顺序 / 真实链路三坑 |
| 04 | [Agent](milestones/04-agent.md) | ✅ | ReAct 循环 / 两道闸门 / 轨迹落盘 / CLI 入口 |
| 05 | [Agent Loop](milestones/05-agent-loop.md) | ✅ | 工作记忆裁剪 / 草稿纸 / 重复闸门 / 多步骤任务 |
| 06 | Multi-Step Task | ⬜ | 多步骤任务 / 任务分解 |
| 07 | MCP | ⬜ | MCP Protocol 原理 |
| 08 | MCP Server | ⬜ | MCP Server 实现 |
| 09 | MCP Client | ⬜ | MCP Client 实现 |
| 10 | Agent Workflow | ⬜ | 完整 Agent 产品 |

状态：✅ 内容已就绪 · ✅ 代码已落地（`src/agent/`）· ✅ 测试全绿（103 passed）· ✅ 已配真实运行截图

## 当前状态

**5 / 10 个 Milestone 文档 + `src/agent/`（9 个模块）+ 离线与真实双链路 + 15 张真实运行截图** 全部完成。

核心卖点「**检索即工具**」已落地：RAG 里的检索从 pipeline 的固定步骤，变成摆在模型面前的一个 `rag_search` 工具——用不用、什么时候用、查几条，由模型自己决定。真实链路上模型自主选了 `rag_search` 并**自己加了 `k: 2` 参数**，这是「控制权从代码转到模型」的具体证据。

零第三方依赖的离线链路（不联网、不烧 token）与真实 DeepSeek 链路双路跑通，`python -m agent.cli` 可直接在命令行提问。

## 当前版本

**v0.6 Agent Loop 与多步骤任务**：`src/agent/` 共 9 个模块 + `ReActAgent` 循环 + `ToolRegistry` + `DeepSeekLLM`，146 项 pytest 全绿。

- `src/agent/tools.py` —— Tool 三件套（name / description / `run(**kwargs) -> str`）；`ToolCall` 与 `ToolResult` 分离；工具异常**永不抛出**，一律转成 `ToolResult.error` 文本回灌；`calculator` 用 `ast` 白名单求值，**不用 `eval`**
- 「检索即工具」：`rag_search` 走本地关键词检索，也可换 HTTP 后端接上 Project 04 的服务
- `src/agent/registry.py` —— `register` / `schema_of` / `schemas` / `call` / `call_many` / `dispatch` / 参数纠偏（`"3"` → 3，**布尔不是整数**）
- `src/agent/llm.py` —— `LLM` 抽象 + `FakeLLM` / `ScriptedLLM` / `RecordingLLM` + `DeepSeekLLM`
- `src/agent/agent.py` —— ReAct 循环 + `Step` / `AgentResult` / `trace()` + `mkstemp + fsync + os.replace` 原子落盘
- 三道闸门：`max_steps=8`（成本天花板）、`max_tool_failures=3`（报错型空转，成功一次清零）、`max_repeats=2`（**成功但原地打转**，signature 计数）
- `src/agent/memory.py` —— 工作记忆：`trim_history` 按 token 预算压缩历史（**assistant 与 tool 消息必须配对裁剪**）、`Scratchpad` 草稿纸（写在循环之外，不随历史被裁）
- `write_note` / `read_notes` 两个工具让模型自己决定记什么，笔记常驻 system 省掉一轮往返

多步骤任务的真实成本（量出来的，不是估的）：一轮 demos/out/demo_05_real.txt 里 7 轮模型往返**累计发送 5131 token** —— 每轮都要把前面的历史重发一遍，所以比的是累计而不是峰值。

跑起来：

```bash
cd projects/05-agent-mcp
.venv/bin/pip install -e .
.venv/bin/python -m agent.cli --list-tools --notes
DEEPSEEK_API_KEY=xxx .venv/bin/python -m agent.cli --notes "对比 Project 01 与 Project 04 的持久化方式"
.venv/bin/python demos/demo_05_agent_loop.py --real
```

没有 `DEEPSEEK_API_KEY` 也不会崩——自动降级到离线剧本，并在 stderr 打印 `[warn]`。

## 项目结构

```text
projects/05-agent-mcp/
├── demos/                  # 5 个真实运行 demo（demo_01～05）+ 输出落盘 demos/out/
├── src/agent/
│   ├── __init__.py         # 包级导出与「检索即工具」说明
│   ├── agent.py            # ReActAgent / Step / AgentResult / 轨迹落盘
│   ├── cli.py              # python -m agent.cli [--list-tools] [--notes] [--mock] [--trace]
│   ├── errors.py           # AgentError 层级（工具错误不往上抛）
│   ├── llm.py              # LLM 抽象 + FakeLLM/ScriptedLLM/RecordingLLM/DeepSeekLLM
│   ├── memory.py           # 工作记忆：trim_history 裁剪 + Scratchpad 草稿纸（05 章）
│   ├── registry.py         # ToolRegistry：注册 / 声明 / 派发 / 参数纠偏
│   ├── settings.py         # frozen AgentSettings（三道闸门 / context_budget）
│   └── tools.py            # Tool / ToolCall / ToolResult / 内置工具集（含 write_note / read_notes）
├── tests/                  # 全部离线（FakeLLM），146 passed
└── assets/                 # 15 张真实运行截图
```

## 已掌握能力

- Project 01-04 的所有能力（Python 工程化、pytest、Prompt / 流式 / 工具调用、RAG 全链路）
- Tool 设计：接口契约、ToolResult 错误回灌、函数即工具、签名推导
- 检索即工具：把 RAG 的检索从固定步骤变成模型可调的工具
- Tool Schema：JSON Schema 装配与校验、参数类型纠偏、中英文检索的坑
- Function Calling：message 顺序、`tool` 消息三字段、真实链路的三个坑（鉴权头 / tools 外层 / schemas 结构）
- Agent：ReAct 循环、多工具并行、三道闸门、轨迹原子落盘、命令行入口
- Agent Loop：工作记忆的 token 预算管理、协议配对的裁剪规则、草稿纸做跨步骤状态
- 多步骤任务：模型自主拆分 + 并行工具调用 + 中间结论落地（离线剧本与真实模型双路跑通）

## 下一步

1. **M06 Multi-Step Task**：把模型在 thought 里的临时拆解变成显式的 Plan（子任务 + 依赖 + 完成状态），让多个 Agent 能各自领走一部分
2. **M07–M09 MCP**：协议原理、Server 实现、Client 实现——把工具换成协议化的外部能力
3. **M07–M09 MCP**：协议原理、Server 实现、Client 实现——把工具换成协议化的外部能力

**前置项目**：[Project 04 — AI Knowledge Base / RAG Assistant](../04-rag/)
