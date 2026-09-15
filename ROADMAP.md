# ROADMAP — 总路线图

> 维护规则：每个 Phase 必须有 学习目标 / 前置知识 / 知识地图 / 项目 / 代码 / 实验 / 练习 /
> 常见错误 / 复习内容 / 文章素材 / 项目总结。禁止知识跳跃，严格按依赖推进。
>
> 状态标记：`[ ]` 未开始 · `[~]` 进行中 · `[x]` 完成

```text
[x] Phase 0  Python Foundation
[ ] Phase 1  Python Engineering
[ ] Phase 2  AI Application Development
[ ] Phase 3  Embedding / Vector / RAG
[ ] Phase 4  Agent / Tool Calling / MCP
[ ] Phase 5  Deep Learning / PyTorch
[ ] Phase 6  Transformer / LLM Fundamentals
[ ] Phase 7  Hugging Face / Open-source Models
[ ] Phase 8  Fine-tuning (SFT / LoRA / QLoRA)
[ ] Phase 9  Evaluation / Quantization
[ ] Phase 10 Inference / vLLM
[ ] Phase 11 Docker / Production Deployment
[ ] Phase 12 Build Mini LLM / TinyGPT
[ ] Phase 13 Capstone AI Product
```

## 项目状态

```text
[~] Project 01  Python AI CLI Assistant        (v0.1 单轮问答已完成)
[ ] Project 02  AI Chat Web
[ ] Project 03  AI Document Assistant
[ ] Project 04  Personal AI Knowledge Base
[ ] Project 05  Research Agent
[ ] Project 06  Mini Transformer
[ ] Project 07  Tiny Language Model
[ ] Project 08  Local Open Source LLM
[ ] Project 09  Java AI Fine-tuning
[ ] Project 10  QLoRA Fine-tuning
[ ] Project 11  LLM Evaluation
[ ] Project 12  LLM Serving
[ ] Project 13  Production AI Platform
[ ] Project 14  TinyGPT
```

## Phase 依赖与项目对应

| Phase | 前置 | 核心知识 | 对应项目 |
|-------|------|----------|----------|
| 0  | — | Python 基础语法、环境、JSON、异常 | P01 Python AI CLI Assistant |
| 1  | 0  | venv、pip、模块化、测试、日志、async | P01 升级 / P02 起步 |
| 2  | 1  | HTTP/API、FastAPI、Pydantic、SSE、LLM API | P02 AI Chat Web |
| 3  | 2  | Token、Embedding、Chunk、向量库、RAG、Rerank | P03 文档助手 / P04 知识库 |
| 4  | 3  | Function Calling、Agent、Memory、Planning、MCP | P05 Research Agent |
| 5  | 0-1 | 张量、梯度、DataLoader、训练循环 | P07 Tiny Language Model |
| 6  | 5  | Attention、Multi-Head、FFN、LayerNorm | P06 Mini Transformer |
| 7  | 6  | HF Transformers、Tokenizer、Generation | P08 Local Open Source LLM |
| 8  | 7  | SFT、PEFT、LoRA、QLoRA、训练参数 | P09 / P10 微调项目 |
| 9  | 8  | 评估集、自动/人工评估、量化(INT8/INT4) | P11 LLM Evaluation |
| 10 | 9  | vLLM、OpenAI-compatible API、Batching | P12 LLM Serving |
| 11 | 10 | Docker、Compose、前后端联调、生产部署 | P13 Production AI Platform |
| 12 | 6-7 | 从零实现 GPT：Tokenizer→Embedding→Training | P14 TinyGPT |
| 13 | 全部 | 综合：Vue + FastAPI + RAG + Agent + vLLM | Capstone 产品 |

## 每个 Phase 的完成标准

不只是"教程写完"，必须满足：

1. 知识点能独立阅读、修改、运行；
2. 能写出该阶段对应的小程序；
3. 项目对应功能真实可用；
4. 有练习记录和错题记录；
5. 有文章素材沉淀到 `content/`。

## 当前阶段详情：Phase 0 — Python Foundation

课程清单（`00-python-foundation/`）：

```text
01-installation  02-variables   03-types      04-string
05-list          06-dict        07-if         08-for
09-function      10-module      11-class      12-exception
13-file          14-json        15-env        16-venv
17-pip
```

所有课程服务于 **Project 01 — Python AI CLI Assistant**：每学完几个知识点，就把它用于项目。
