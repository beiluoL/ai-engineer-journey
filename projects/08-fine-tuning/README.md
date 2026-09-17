# Project 08 — LoRA / QLoRA Fine-Tuning

## 项目目标

掌握模型微调，让通用模型变成领域模型。

## 为什么做这个项目

RAG 是外挂知识，Fine-tuning【微调】是把知识和行为"烧进"模型。生产中 LoRA / QLoRA 是标配。

## 解决什么问题

- RAG 能加知识但不能改变模型行为
- 需要模型在特定领域表现更好
- 需要让模型学会新的任务格式

## 最终能力

```text
Base Model
    ↓
Dataset
    ↓
Fine-Tuning
    ↓
LoRA / QLoRA
    ↓
Checkpoint
    ↓
Evaluation
    ↓
Usable Model
```

## 技术栈

- PEFT / LoRA / QLoRA
- Transformers 训练 Pipeline
- Datasets（数据准备）
- Training Arguments
- Checkpoint / Adapter Merge

## 项目演进

```
Local Open Source LLM
    ↓ SFT 基础
Fine-tuning v0.1
    ↓ LoRA / QLoRA
Fine-tuning v0.2
    ↓ Checkpoint + 评估
Fine-tuning v1.0
```

## Milestones

| # | Milestone | 核心能力 |
|---|-----------|----------|
| 01 | Fine-Tuning | 微调概念 / SFT |
| 02 | Dataset Preparation | 训练数据 / 格式转换 |
| 03 | Instruction Tuning | Instruction Format / Alpaca |
| 04 | LoRA | LoRA 原理 / PEFT |
| 05 | QLoRA | QLoRA / 显存优化 |
| 06 | Training Configuration | 训练参数 / 超参 |
| 07 | Checkpoint | Checkpoint / 断点续训 |
| 08 | Merge / Load Adapter | Adapter 合并 / 加载 |
| 09 | Fine-Tuned Model Evaluation | 微调效果评估 |

## 当前状态

⬜ 未开始

## 当前版本

还未开始。

## 项目结构

```
src/
└── （Fine-tuning Pipeline）
```

## 已掌握能力

- Project 01-07 的所有能力

## 下一步

完成 Project 07，然后进入微调。

**前置项目**：[Project 07 — Open Source LLM](../07-open-source-llm/)
