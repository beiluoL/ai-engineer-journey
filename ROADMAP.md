# AI Engineer Journey — Roadmap

> 接下来要构建哪些项目？

## 10 个项目路线

```text
Stage 01  Python AI CLI
          ↓  学 Python 基础 + AI API
Stage 02  AI Assistant Service
          ↓  学 Python Engineering + FastAPI
Stage 03  AI Chat Web
          ↓  学 LLM Application（Prompt / Streaming / Tool Calling）
Stage 04  Personal RAG
          ↓  学 RAG（Embedding / Chunk / Vector DB）
Stage 05  Research Agent
          ↓  学 Agent + MCP Protocol
Stage 06  Mini Transformer
          ↓  学 PyTorch / Attention / Transformer 内部原理
Stage 07  Local Open Source LLM
          ↓  学 Hugging Face 生态 + 本地推理
Stage 08  Fine-tuning
          ↓  学 SFT / LoRA / QLoRA
Stage 09  Evaluation & Inference
          ↓  学评估 / 量化 / vLLM 服务化
Stage 10  TinyGPT Capstone
          ↓  从零实现小型 LLM（把所有知识串起来）
```

## 项目详情

### Stage 01 — Python AI CLI

**为什么存在**：AI 项目全是 Python 写的。从 Python 基础 + 真实 LLM API 切入。

**核心技术**：变量 / 类型 / list / dict / JSON / 函数 / OOP / 异常 / 文件 / HTTP

**最终交付**：v1.0 的 CLI AI Assistant（能真实调用 LLM）

**状态**：🔄 进行中

---

### Stage 02 — AI Assistant Service

**为什么存在**：脚本级代码无法扩展，需要工程化。

**核心技术**：venv / pip / 模块化 / async / FastAPI / 类型提示 / 测试

**最终交付**：HTTP 服务化的 AI Assistant

**状态**：⬜ 未开始

---

### Stage 03 — AI Chat Web

**为什么存在**：会调 API 不等于会做 AI 应用。

**核心技术**：Prompt Engineering / Streaming / SSE / Function Calling / Structured Output

**最终交付**：Web 端 AI Chat 应用

**状态**：⬜ 未开始

---

### Stage 04 — Personal RAG

**为什么存在**：LLM 有知识截止日期，幻觉不可避免。

**核心技术**：Token / Embedding / Chunk / 向量库 / Retrieval / Rerank

**最终交付**：接入个人知识库的 AI Assistant

**状态**：⬜ 未开始

---

### Stage 05 — Research Agent

**为什么存在**：RAG 解决了知识问题，但 AI 还不能主动做事。

**核心技术**：Tool / Function Calling / Agent Loop / MCP Protocol / Memory

**最终交付**：能自主规划和调用工具的 Agent

**状态**：⬜ 未开始

---

### Stage 06 — Mini Transformer

**为什么存在**：会调用 LLM 不等同于理解 LLM。

**核心技术**：PyTorch / Tensor / Autograd / Attention / Multi-Head / Decoder

**最终交付**：从零构建的 Mini Transformer

**状态**：⬜ 未开始

---

### Stage 07 — Local Open Source LLM

**为什么存在**：生产不可能全靠商业 API，必须掌握开源模型生态。

**核心技术**：Hugging Face / Tokenizer / Model Loading / 本地推理

**最终交付**：本地跑通的开源 LLM

**状态**：⬜ 未开始

---

### Stage 08 — Fine-tuning

**为什么存在**：RAG 是外挂知识，Fine-tuning 是烧进模型。

**核心技术**：SFT / PEFT / LoRA / QLoRA / 数据准备 / 显存优化

**最终交付**：自己微调的领域模型

**状态**：⬜ 未开始

---

### Stage 09 — Evaluation & Inference

**为什么存在**：训练完只是第一步，上线前必须评估、量化、服务化。

**核心技术**：评估集 / Benchmark / INT8 INT4 量化 / vLLM / Batching / PagedAttention

**最终交付**：高性能推理服务

**状态**：⬜ 未开始

---

### Stage 10 — TinyGPT Capstone

**为什么存在**：把前面 9 个项目的所有知识串成一个完整工程。

**核心技术**：Tokenizer / Embedding / Transformer / Training / Inference / Deployment

**最终交付**：自己实现的小型 LLM 工程（从 Tokenizer 到部署全链路）

**状态**：⬜ 未开始

---

## 能力递进关系

```text
Python          ← Stage 01-02
    ↓
LLM Application ← Stage 03
    ↓
RAG             ← Stage 04
    ↓
Agent / MCP     ← Stage 05
    ↓
模型原理        ← Stage 06
    ↓
开源生态        ← Stage 07
    ↓
微调            ← Stage 08
    ↓
评估 + 服务化   ← Stage 09
    ↓
综合实现        ← Stage 10
```
