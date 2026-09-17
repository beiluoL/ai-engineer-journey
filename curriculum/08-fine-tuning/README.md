# 08-fine-tuning — Phase 8：Fine-tuning

> 让开源大模型「懂你的业务」，掌握 SFT 与 LoRA 微调全流程。

## 这一阶段学什么

- SFT（Supervised Fine-Tuning）全流程
- PEFT 参数高效微调
- LoRA / QLoRA 原理与实现
- 训练数据准备与格式化
- 超参调优（lr / epochs / batch）
- 训练监控与过拟合判断

## 为什么学

通用大模型不懂你的业务领域、风格、专有术语。微调是让模型「定制化」的核心手段，LoRA / QLoRA 让单卡也能微调，是企业落地的关键技能。

## 前置知识

- [Phase 7 — Hugging Face / 开源大模型](../07-huggingface-open-source-llm/)

## 核心技能

- 准备并格式化 SFT 训练数据
- 用 PEFT 配置 LoRA / QLoRA
- 跑通微调训练循环
- 看懂 loss / eval 曲线
- 合并 LoRA 权重并保存
- 对比微调前后效果

## 项目

| 项目 | 说明 |
|------|------|
| Project 09 | SFT 微调：让模型学特定风格 |
| Project 10 | QLoRA 微调：低资源场景定制 |

## 完成标准

- Project 09 / 10 完成微调并能对比效果
- 能解释 LoRA 为什么参数高效
- 能处理训练数据为 chat 格式
- 能判断过拟合并调整超参

## 下一阶段

[Phase 9 — Evaluation / Quantization](../09-evaluation-quantization/)
