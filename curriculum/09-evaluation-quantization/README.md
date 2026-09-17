# 09-evaluation-quantization — Phase 9：Evaluation / Quantization

> 给模型「打分」并「瘦身」，让微调成果可量化、可落地。

## 这一阶段学什么

- 评估集构建与指标设计
- 自动评估（perplexity / MMLU / 自定义）
- 人工评估与对比标注
- 量化原理（INT8 / INT4）
- 量化对效果与速度的影响
- 量化模型部署验证

## 为什么学

微调完不能只靠感觉判断好坏，需要系统评估。量化则能在显存有限的设备上跑大模型，是模型走向生产部署的必备环节。

## 前置知识

- [Phase 8 — Fine-tuning](../08-fine-tuning/)

## 核心技能

- 构建领域评估集
- 跑自动评估指标
- 设计 A/B 人工对比方案
- 用 bitsandbytes 做 INT8 / INT4 量化
- 对比量化前后的速度与显存
- 验证量化模型效果是否可接受

## 项目

| 项目 | 说明 |
|------|------|
| Project 11 | LLM Evaluation：评估 + 量化一条龙 |

## 完成标准

- Project 11 输出评估报告与量化模型
- 能解释量化为什么能加速
- 能用自动 + 人工双维度评估
- 量化后效果损失在可接受范围

## 下一阶段

[Phase 10 — Inference / vLLM](../10-inference-vllm/)
