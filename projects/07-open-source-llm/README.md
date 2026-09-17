# Project 07 — Open Source LLM

## 项目目标

接触真实开源模型生态，在本地跑通 Hugging Face 模型。

## 为什么做这个项目

生产环境不可能每次都调商业 API。需要掌握如何加载、运行、对比开源模型，理解它们的限制和优势。

## 解决什么问题

- 生产环境不能全靠商业 API
- 不知道怎么加载开源模型
- 不理解模型内存占用和推理速度

## 最终能力

```text
Model
    ↓
Tokenizer
    ↓
Weights
    ↓
Memory
    ↓
Inference
    ↓
Application
```

## 技术栈

- Hugging Face Transformers
- Tokenizer 深入理解
- Model Loading（device / dtype）
- Model Inference（生成参数 / 采样）
- 本地模型 Serving
- 量化基础

## 项目演进

```
Mini Transformer
    ↓ 接入开源生态
Open Source LLM v0.1（加载 + 推理）
    ↓ Generation + 本地 Serving
Open Source LLM v0.2
    ↓ 量化 + 应用
Open Source LLM v1.0
```

## Milestones

| # | Milestone | 核心能力 |
|---|-----------|----------|
| 01 | Hugging Face | HF Ecosystem / Hub / Pipeline |
| 02 | Tokenizer | BPE / Token 编码 / decode |
| 03 | Model Loading | device / dtype / from_pretrained |
| 04 | Model Inference | generate / 推理基础 |
| 05 | Generation Parameters | temperature / top_p / max_new_tokens |
| 06 | Local Model Serving | Transformers + 本地推理 |
| 07 | Model Memory / VRAM | 显存管理 / 模型大小 |
| 08 | Quantization | 量化基础 / bitsandbytes |
| 09 | Open Source LLM Application | 完整开源 LLM 应用 |

## 当前状态

⬜ 未开始

## 当前版本

还未开始。

## 项目结构

```
src/
└── （Local Open Source LLM）
```

## 已掌握能力

- Project 01-06 的所有能力

## 下一步

完成 Project 06，然后进入开源模型生态。

**前置项目**：[Project 06 — Mini Transformer / LLM](../06-mini-transformer-llm/)
