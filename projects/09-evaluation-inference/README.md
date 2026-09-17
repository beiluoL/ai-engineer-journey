# Project 09 — LLM Evaluation / Inference Platform

## 项目目标

掌握模型评估、量化和高性能推理服务化。

## 为什么做这个项目

训练完模型只是第一步。上线前必须评估效果、量化压缩、做高性能推理服务——这些是 AI 工程师区别于调参侠的关键能力。

## 解决什么问题

- 不知道模型效果好不好（评估）
- 模型太大跑不动（量化）
- 推理太慢无法并发（高性能 Serving）

## 最终能力

```text
Model
    ↓
Evaluation
    ↓
Optimization
    ↓
Inference
    ↓
Serving
```

## 技术栈

- 评估方法论 / Benchmark（MMLU / HumanEval）
- INT8 / INT4 量化
- vLLM / Batching / PagedAttention
- KV Cache 管理
- 并发推理服务

## 项目演进

```
Fine-tuned Model
    ↓ 评估
Evaluation Platform v0.1
    ↓ 量化
Evaluation Platform v0.2
    ↓ vLLM Serving
Evaluation & Inference Platform v1.0
```

## Milestones

| # | Milestone | 核心能力 |
|---|-----------|----------|
| 01 | Evaluation | 评估方法论 / 评估设计 |
| 02 | Benchmark | MMLU / HumanEval / 主流 Benchmark |
| 03 | Evaluation Dataset | 评估数据集构建 |
| 04 | Automatic Evaluation | 自动评估 / 指标 |
| 05 | Model Comparison | 模型对比选型 |
| 06 | Quantization | INT8 / INT4 / GPTQ |
| 07 | Inference Engine | 推理引擎原理 |
| 08 | vLLM | vLLM / PagedAttention |
| 09 | Batching | Batch / Continuous Batching |
| 10 | KV Cache | KV Cache 管理 |
| 11 | Model Serving | 生产级 Serving |

## 当前状态

⬜ 未开始

## 当前版本

还未开始。

## 项目结构

```
src/
└── （Evaluation & Inference Platform）
```

## 已掌握能力

- Project 01-08 的所有能力

## 下一步

完成 Project 08，然后进入评估 + 服务化。

**前置项目**：[Project 08 — LoRA / QLoRA Fine-Tuning](../08-fine-tuning/)
