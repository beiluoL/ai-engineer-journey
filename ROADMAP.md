# AI Engineer Journey — Roadmap

> 10 个连续项目，逐步构建 AI Engineer 完整能力体系。

## 能力递进关系

```text
Python              ← Project 01-02（脚本 → 服务）
  ↓
LLM Application     ← Project 03（Prompt / Streaming / Tool Calling）
  ↓
RAG                 ← Project 04（Embedding / Vector DB / Retrieval）
  ↓
Agent / MCP          ← Project 05（Tool / Agent Loop / MCP Protocol）
  ↓
模型原理            ← Project 06（PyTorch / Attention / Transformer）
  ↓
开源生态            ← Project 07（Hugging Face / 本地推理）
  ↓
微调                ← Project 08（SFT / LoRA / QLoRA）
  ↓
评估 + 服务化       ← Project 09（Benchmark / Quantization / vLLM）
  ↓
综合实现            ← Project 10（从零实现 Tiny LLM）
```

联系描述：

前面的项目提供后续项目所需基础能力。Project 01 学会 Python、HTTP 和真实 LLM API；Project 02 将其工程化；Project 03 在此之上构建 AI Application；Project 04 为应用增加外部知识；Project 05 让模型拥有工具和执行能力；Project 06 开始进入模型内部；Project 07 使用真实开源模型；Project 08 修改模型能力；Project 09 解决生产级评估与推理；Project 10 将这些能力重新组合。

---

## Project 01 — Python AI CLI Assistant

**目标**：通过持续升级一个 AI CLI Assistant，学习 Python 基础，并最终接入真实 LLM API。

**核心技术**：Variables / List Dict JSON / Condition Loop / Function / Module Package / Exception / File JSON / venv pip / HTTP API / Real LLM

**最终交付**：v1.0 的 CLI AI Assistant（能真实调用 LLM）

**状态**：🔄 进行中

**10 个 Milestone**：
```
01 — Variables
02 — List / Dict / JSON
03 — Condition / Loop
04 — Function
05 — Module / Package
06 — Exception
07 — File / JSON Persistence
08 — venv / pip / Environment
09 — HTTP / API
10 — Real LLM API
```

---

## Project 02 — Engineering AI Assistant

**目标**：在 Project 01 基础上，把 CLI Assistant 从 Python Script 工程化为 Python Application。

**核心技术**：Async / Type Hints / Dataclass / Config / Logging / Testing / FastAPI

**最终交付**：HTTP 服务化的 AI Assistant Service

**状态**：⬜ 未开始

**10 个 Milestone**：
```
00 — Classes and OOP
01 — Async / Await
02 — Async HTTP Client
03 — Type Hints
04 — Dataclass
05 — Config / Environment
06 — Logging
07 — Testing / Debugging
08 — Packaging
09 — FastAPI
```

---

## Project 03 — AI Application

**目标**：进入真正的 LLM Application【大模型应用】开发。

**核心技术**：Prompt / Structured Output / Streaming / Function Calling / Conversation Memory

**最终交付**：Web 端 AI Chat 应用

**状态**：⬜ 未开始

**9 个 Milestone**：
```
01 — Prompt
02 — System / User / Assistant Messages
03 — Structured Output
04 — Streaming
05 — Conversation Memory
06 — Model Parameters
07 — Token / Context Window
08 — Function Calling
09 — AI Application Architecture
```

---

## Project 04 — AI Knowledge Base / RAG Assistant

**目标**：构建真正的 AI Knowledge Base【AI 知识库】与 RAG【检索增强生成】系统。

**核心技术**：Document Ingestion / Chunking / Embedding / Vector Database / Retrieval / Rerank

**最终交付**：接入个人知识库的 RAG Assistant

**状态**：⬜ 未开始

**10 个 Milestone**：
```
01 — Document Ingestion
02 — Chunking
03 — Embedding
04 — Vector Database
05 — Retrieval
06 — Similarity Search
07 — Rerank
08 — Context Assembly
09 — RAG Pipeline
10 — RAG Evaluation
```

---

## Project 05 — Research Agent / MCP Assistant

**目标**：让 AI 从"回答问题"变成能调用外部工具、执行多步骤任务的 Agent【智能体】。

**核心技术**：Tool / Tool Schema / Function Calling / Agent Loop / MCP Protocol

**最终交付**：能自主规划和调用工具的 Agent System

**状态**：⬜ 未开始

**10 个 Milestone**：
```
01 — Tool
02 — Tool Schema
03 — Function Calling
04 — Agent
05 — Agent Loop
06 — Multi-Step Task
07 — MCP
08 — MCP Server
09 — MCP Client
10 — Agent Workflow
```

---

## Project 06 — Mini Transformer / LLM

**目标**：从 AI 应用层进入模型内部，从零构建 Mini Transformer Decoder。

**核心技术**：PyTorch / Tensor / Autograd / Self-Attention / Multi-Head Attention / Transformer Decoder

**最终交付**：从零构建的 Mini Transformer Decoder

**状态**：⬜ 未开始

**12 个 Milestone**：
```
01 — Tensor
02 — Autograd
03 — Dataset / DataLoader
04 — Neural Network
05 — Training Loop
06 — Tokenization
07 — Embedding
08 — Attention
09 — Self-Attention
10 — Transformer
11 — Decoder-Only LLM
12 — Mini LLM Training
```

---

## Project 07 — Open Source LLM

**目标**：接触真实开源模型生态，在本地跑通 Hugging Face 模型。

**核心技术**：Hugging Face / Tokenizer / Model Loading / Inference / Quantization

**最终交付**：本地跑通的开源 LLM 应用

**状态**：⬜ 未开始

**9 个 Milestone**：
```
01 — Hugging Face
02 — Tokenizer
03 — Model Loading
04 — Model Inference
05 — Generation Parameters
06 — Local Model Serving
07 — Model Memory / VRAM
08 — Quantization
09 — Open Source LLM Application
```

---

## Project 08 — LoRA / QLoRA Fine-Tuning

**目标**：进入模型微调，让通用模型变成领域模型。

**核心技术**：SFT / PEFT / LoRA / QLoRA / Dataset Preparation / Training

**最终交付**：自己微调的领域模型

**状态**：⬜ 未开始

**9 个 Milestone**：
```
01 — Fine-Tuning
02 — Dataset Preparation
03 — Instruction Tuning
04 — LoRA
05 — QLoRA
06 — Training Configuration
07 — Checkpoint
08 — Merge / Load Adapter
09 — Fine-Tuned Model Evaluation
```

---

## Project 09 — LLM Evaluation / Inference Platform

**目标**：掌握模型评估、量化和高性能推理服务化。

**核心技术**：Benchmark / 自动评估 / INT8 INT4 量化 / vLLM / Batching / PagedAttention

**最终交付**：高性能推理服务平台

**状态**：⬜ 未开始

**11 个 Milestone**：
```
01 — Evaluation
02 — Benchmark
03 — Evaluation Dataset
04 — Automatic Evaluation
05 — Model Comparison
06 — Quantization
07 — Inference Engine
08 — vLLM
09 — Batching
10 — KV Cache
11 — Model Serving
```

---

## Project 10 — Tiny LLM / AI Engineer Capstone

**目标**：把前面所有能力重新串起来，完成最终 AI Engineer Capstone【综合项目】。

**核心技术**：Tokenizer → Embedding → Transformer → Training → Evaluation → Inference → Serving

**最终交付**：从零实现的小型 LLM 完整工程

**状态**：⬜ 未开始

**11 个 Milestone**：
```
01 — Project Architecture
02 — Tokenizer
03 — Dataset
04 — Embedding
05 — Transformer Block
06 — Training
07 — Evaluation
08 — Inference
09 — Optimization
10 — Serving
11 — Complete AI Engineer System
```
