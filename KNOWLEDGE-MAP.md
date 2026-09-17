# AI Engineer Journey — Knowledge Map

> 展示项目 → 知识 → 能力的关系。不复制 Milestone 正文。

## 能力递进

```text
Python
  ↓
Python Engineering（venv / async / FastAPI / testing）
  ↓
LLM Application（Prompt / Streaming / Function Calling）
  ↓
RAG（Embedding / Chunk / Vector DB / Retrieval / Rerank）
  ↓
Agent + MCP（Tool / Agent Loop / Memory / MCP Protocol）
  ↓
PyTorch + Transformer（Tensor / Attention / Decoder）
  ↓
Open Source LLM（Hugging Face / Tokenizer / 本地推理）
  ↓
Fine-tuning（SFT / LoRA / QLoRA）
  ↓
Evaluation + Inference（评估 / 量化 / vLLM 服务化）
  ↓
Mini LLM（Tokenizer → Transformer → Training → Inference → Deploy）
```

## 项目 → 知识 → 能力

### Project 01 — Python AI CLI

| 知识 | 对应 Milestone | 获得能力 |
|------|---------------|----------|
| 变量 / 类型 / I/O | 01-python-basics | Python 基础 |
| List / Dict / JSON | 02-data-and-messages | AI 项目数据结构 |
| if / for / while | 03-control-flow | 逻辑控制 |
| 函数 / 参数 / 返回值 | 04-functions | 代码复用 |
| Module / Package | 05-modules-and-packages | 项目结构 |
| Class / OOP | 06-classes-and-oop | 数据 + 行为封装 |
| Exception | 07-exceptions | 错误处理 |
| 文件 / JSON 读写 | 08-persistence | 数据持久化 |
| venv / pip | 09-environment-and-deps | 依赖管理 |
| HTTP / API | 10-http-api | 网络通信 |
| 真实 LLM 调用 | 11-real-llm-api | AI API 集成 |
| async / await | 12-async | 并发基础 |
| typing / dataclass | 13-typing-and-dataclass | 类型安全 |
| .env / 配置 | 14-config-and-env | 配置管理 |
| pytest / 调试 | 15-testing-and-debugging | 质量保证 |

**整体能力：能构建 Python AI CLI 项目并真实调用 LLM API**

---

### Project 02 — AI Assistant Service

| 知识 | 获得能力 |
|------|----------|
| FastAPI | 服务化 |
| async / await | 高并发 |
| 类型提示 | 工程化 |
| 测试 / 日志 | 质量保证 |

**整体能力：能把脚本升级为可维护的 HTTP 服务**

---

### Project 03 — AI Chat Web

| 知识 | 获得能力 |
|------|----------|
| Prompt Engineering | 引导模型 |
| Streaming / SSE | 流式输出 |
| Function Calling | 结构化交互 |
| Structured Output | JSON Mode |

**整体能力：能构建真实可用的 AI 应用前端**

---

### Project 04 — Personal RAG

| 知识 | 获得能力 |
|------|----------|
| Embedding | 文本向量化 |
| Chunk | 文档切分 |
| Vector Database | 向量存储 |
| Retrieval | 检索 |
| Rerank | 重排序 |

**整体能力：能给模型加上外部知识**

---

### Project 05 — Research Agent

| 知识 | 获得能力 |
|------|----------|
| Tool / Function Calling | 外部能力调用 |
| Agent Loop | 自主规划 |
| MCP Protocol | 标准化工具接入 |
| Memory | 上下文保持 |

**整体能力：能构建自主 Agent**

---

### Project 06 — Mini Transformer

| 知识 | 获得能力 |
|------|----------|
| PyTorch Tensor | 计算基础 |
| Autograd | 自动求导 |
| DataLoader | 数据 pipeline |
| Self-Attention | Transformer 核心 |
| Multi-Head + FFN + LN | 完整 Decoder |

**整体能力：能从零构建 Transformer Decoder**

---

### Project 07 — Local Open Source LLM

| 知识 | 获得能力 |
|------|----------|
| Hugging Face | 模型生态 |
| Tokenizer | 文本编码 |
| Model Loading | 推理基础 |

**整体能力：能在本地跑通开源 LLM**

---

### Project 08 — Fine-tuning

| 知识 | 获得能力 |
|------|----------|
| SFT | 监督微调 |
| LoRA / QLoRA | 高效微调 |
| 数据准备 | 训练 pipeline |

**整体能力：能微调自己的领域模型**

---

### Project 09 — Evaluation & Inference

| 知识 | 获得能力 |
|------|----------|
| 评估方法论 | 模型效果判断 |
| INT8 / INT4 量化 | 模型压缩 |
| vLLM / PagedAttention | 高性能推理 |

**整体能力：能把模型服务化上线**

---

### Project 10 — TinyGPT Capstone

| 知识 | 获得能力 |
|------|----------|
| Tokenizer → Transformer → Training → Inference → Deploy | 完整 LLM 工程 |

**整体能力：能从零实现小型 LLM（综合运用前面所有能力）**

---

## 为什么 Knowledge Map 不复制正文

> Milestone 是单一事实源。Knowledge Map 只负责展示关联，不重复写同样的内容。

想了解具体知识？打开对应项目的 `milestones/` 目录。
