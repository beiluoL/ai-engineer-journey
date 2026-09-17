# Project 10 — Tiny LLM / AI Engineer Capstone

## 项目目标

把前面所有能力重新串起来，完成最终 AI Engineer Capstone【综合项目】——从零实现一个小型 LLM 工程。

## 为什么做这个项目

前面 9 个项目都是专项能力。现在是时候把它们全部串起来，自己完整实现一个 LLM 从 Tokenizer 到训练到推理到部署的全链路。

## 解决什么问题

- 能不能从零实现一个完整的 LLM 工程？
- 能不能把前面学到的所有能力真正串起来？
- 能不能作为 AI Engineer 独立交付完整项目？

## 最终能力

```text
Data
    ↓
Tokenizer
    ↓
Model
    ↓
Training
    ↓
Evaluation
    ↓
Inference
    ↓
Optimization
    ↓
Serving
    ↓
Application
```

完整 AI Engineer 全链路能力。

## 技术栈

- 所有前序项目技术的综合
- Tokenizer 实现（BPE）
- Transformer Decoder
- 完整 Training Pipeline
- 完整 Inference Pipeline
- 部署到生产

## 项目演进

```
前面 9 个项目的所有能力
    ↓ 完整整合
Tiny LLM v0.1（Tokenizer + Model）
    ↓ Training + Evaluation
Tiny LLM v0.2
    ↓ Inference + Serving
Tiny LLM v1.0
```

## Milestones

| # | Milestone | 核心能力 |
|---|-----------|----------|
| 01 | Project Architecture | 架构设计 / 模块划分 |
| 02 | Tokenizer | BPE / 分词器实现 |
| 03 | Dataset | 数据准备 / 预处理 |
| 04 | Embedding | Embedding + Positional Encoding |
| 05 | Transformer Block | Multi-Head Attention + FFN + LN |
| 06 | Training | 完整训练 Pipeline |
| 07 | Evaluation | 模型评估 |
| 08 | Inference | 推理 Pipeline / generate |
| 09 | Optimization | 量化 / KV Cache / 优化 |
| 10 | Serving | API 服务 / FastAPI |
| 11 | Complete AI Engineer System | 完整工程交付 |

## 当前状态

⬜ 未开始

## 当前版本

还未开始。

## 项目结构

```
src/
└── （Tiny LLM 完整实现）
```

## 已掌握能力

- Project 01-09 的所有能力

## 下一步

完成 Project 09，然后进入最终 Capstone。

**前置项目**：[Project 09 — LLM Evaluation / Inference Platform](../09-evaluation-inference/)
