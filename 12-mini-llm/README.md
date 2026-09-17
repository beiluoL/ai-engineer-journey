# 12-mini-llm — Phase 12：Mini LLM

> 从零造一个 GPT：Tokenizer、Embedding、训练全手写。

## 这一阶段学什么

- 从零实现 BPE Tokenizer
- Embedding 层与位置编码
- Transformer Block 堆叠
- 训练数据准备与采样
- 训练循环与损失优化
- 生成采样与模型评估

## 为什么学

调 API 谁都会，但理解「模型是怎么造出来的」是 AI 工程师的护城河。完整走过一遍 GPT 实现，你将彻底看懂所有大模型的内部结构，读论文、做微调、改架构都不再恐惧。

## 前置知识

- [Phase 6 — Transformer / LLM](../06-transformer-llm/)
- [Phase 7 — Hugging Face / 开源大模型](../07-huggingface-open-source-llm/)

## 核心技能

- 手写 BPE 分词器
- 实现 Token Embedding 与位置编码
- 堆叠完整 GPT 模型结构
- 准备并采样训练数据
- 跑通训练循环并调 loss
- 实现温度 / top-k 采样生成文本

## 项目

| 项目 | 说明 |
|------|------|
| Project 14 | TinyGPT：从零实现并训练一个最小 GPT |

## 完成标准

- Project 14 可训练并生成可读文本
- 能解释从 Token 到输出的完整流程
- 能调参改变生成风格
- 读懂 nano-GPT 等参考实现

## 下一阶段

[Phase 13 — Capstone](../13-capstone/)
