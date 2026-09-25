# AI Engineer Journey — Knowledge Map

> 项目 → 知识 → 能力的关系网。只展示关联，不复制 Milestone 正文。
> 想了解具体知识？打开对应项目的 `milestones/` 目录。

## 能力递进

```text
Python
  ↓
Python Engineering（async / FastAPI / testing）
  ↓
LLM Application（Prompt / Streaming / Function Calling）
  ↓
RAG（Embedding / Chunk / Vector DB / Retrieval / Rerank）
  ↓
Agent + MCP（Tool / Agent Loop / MCP Protocol）
  ↓
PyTorch + Transformer（Tensor / Attention / Decoder）
  ↓
Open Source LLM（Hugging Face / Tokenizer / 本地推理）
  ↓
Fine-tuning（SFT / LoRA / QLoRA）
  ↓
Evaluation + Inference（Benchmark / Quantization / vLLM）
  ↓
Mini LLM（Tokenizer → Transformer → Training → Inference → Deploy）
```

---

## Project 01 — Python AI CLI Assistant → 能力

| 知识 | 对应 Milestone | 获得能力 |
|------|---------------|----------|
| Variables / Types / I/O | 01-variables | Python 基础语法 |
| List / Dict / JSON | 02-list-dict-json | AI 项目数据结构 |
| Condition / Loop | 03-condition-loop | 逻辑控制 |
| Function | 04-function | 代码复用 |
| Module / Package | 05-module-package | 项目结构 |
| Exception | 06-exception | 错误处理 |
| File / JSON Persistence | 07-file-json | 数据持久化 |
| venv / pip | 08-venv-pip | 依赖管理 |
| HTTP / API | 09-http-api | 网络通信 |
| Real LLM API | 10-real-llm-api | AI API 集成 |

**整体能力**：能构建 Python AI CLI 项目并真实调用 LLM API

---

## Project 02 — Engineering AI Assistant → 能力

| 知识 | 对应 Milestone | 获得能力 |
|------|---------------|----------|
| Classes and OOP | 00-classes-and-oop | 数据 + 行为封装 |
| Async / Await | 01-async-await | 并发基础 |
| Async HTTP Client | 02-async-http-client | 异步请求 |
| Type Hints | 03-type-hints | 类型安全 |
| Dataclass | 04-dataclass | 数据类 |
| Config / Environment | 05-config-and-environment | 配置管理 |
| Logging | （待创建）| 可观测性 |
| Testing / Debugging | 07-testing-and-debugging | 质量保证 |
| Packaging | （待创建）| 发布 / 安装 |
| FastAPI | （待创建）| 服务化 |

**整体能力**：能把脚本升级为可维护的 HTTP 服务

---

## Project 03 — AI Application → 能力

| 知识 | 获得能力 |
|------|----------|
| Prompt Engineering | 引导模型稳定输出 |
| Streaming / SSE | 流式输出 / 打字机效果 |
| Function Calling | 结构化交互 |
| Structured Output | JSON Mode / Schema |
| Conversation Memory | 多轮对话管理 |
| Token / Context Window | 上下文限制管理 |

**整体能力**：能构建真实可用的 AI 应用前端

---

## Project 04 — AI Knowledge Base / RAG → 能力

| 知识 | 获得能力 |
|------|----------|
| Embedding | 文本向量化 |
| Chunking | 文档切分 |
| Vector Database | 向量存储 |
| Retrieval | 检索 |
| Rerank | 重排序 |
| RAG Pipeline | 完整链路整合 |

**整体能力**：能给模型加上外部知识

---

## Project 05 — Research Agent / MCP → 能力

| 知识 | 获得能力 |
|------|----------|
| Tool / Tool Schema | 外部能力定义 |
| Function Calling | 外部能力调用 |
| Agent Loop | 自主规划（Plan → Act → Observe） |
| MCP Protocol | 标准化工具接入 |
| Agent Workflow | 完整 Agent 系统 |

**整体能力**：能构建自主 Agent

---

## Project 06 — Mini Transformer / LLM → 能力

| 知识 | 获得能力 |
|------|----------|
| PyTorch Tensor | 计算基础 |
| Autograd | 自动求导 / 反向传播 |
| DataLoader | 数据 Pipeline |
| Self-Attention | Transformer 核心 |
| Multi-Head + FFN + LN | 完整 Decoder Block |
| Decoder-Only LLM | 完整语言模型 |

**整体能力**：能从零构建 Transformer Decoder

---

## Project 07 — Open Source LLM → 能力

| 知识 | 获得能力 |
|------|----------|
| Hugging Face | 模型生态导航 |
| Tokenizer | BPE / 文本编码 |
| Model Loading | device / dtype / 推理 |
| Model Memory / VRAM | 显存管理 |
| Quantization | INT8 / INT4 |

**整体能力**：能在本地跑通开源 LLM 并优化

---

## Project 08 — LoRA / QLoRA Fine-Tuning → 能力

| 知识 | 获得能力 |
|------|----------|
| Fine-Tuning / SFT | 监督微调基础 |
| Dataset Preparation | 训练数据处理 |
| LoRA | 参数高效微调 |
| QLoRA | 显存优化微调 |
| Checkpoint / Merge | 模型保存 / 加载 |

**整体能力**：能微调自己的领域模型

---

## Project 09 — LLM Evaluation / Inference → 能力

| 知识 | 获得能力 |
|------|----------|
| Benchmark | MMLU / HumanEval |
| Evaluation Dataset | 评估集构建 |
| Automatic Evaluation | 自动评估指标 |
| Quantization | 模型压缩 |
| vLLM / PagedAttention | 高性能推理 |
| Batching / KV Cache | 并发 / 显存管理 |
| Model Serving | 生产级部署 |

**整体能力**：能把模型评估、优化、服务化上线

---

## Project 10 — Tiny LLM Capstone → 能力

```text
Data → Tokenizer → Embedding → Transformer → Training → Evaluation → Inference → Optimization → Serving → Application
```

**整体能力**：能从零实现小型 LLM（综合运用前面所有能力）

---

## 为什么 Knowledge Map 不复制正文

> **Milestone 是单一事实源。** Knowledge Map 只负责展示关联，不重复写同样的内容。

想了解具体知识？打开对应项目的 `milestones/` 目录。
