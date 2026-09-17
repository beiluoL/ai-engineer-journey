# 06-transformer-llm — Phase 6：Transformer / LLM

> 拆解 GPT 的心脏：Attention，亲手拼出一个 Mini Transformer。

## 这一阶段学什么

- Self-Attention 机制
- Multi-Head Attention
- Feed-Forward Network（FFN）
- LayerNorm 与残差连接
- 位置编码（Positional Encoding）
- Transformer Block 堆叠

## 为什么学

所有现代大模型（GPT / Llama / Qwen）都建立在 Transformer 之上。理解 Attention 与整体架构，才能看懂模型结构、做微调、读论文、实现自己的 TinyGPT。

## 前置知识

- [Phase 5 — PyTorch](../05-pytorch/)

## 核心技能

- 手写 Self-Attention 公式
- 实现 Multi-Head 拼接
- 解释 FFN 与残差的作用
- 用 LayerNorm 稳定训练
- 实现正弦 / 可学习位置编码
- 堆叠 Transformer Block 成完整模型

## 项目

| 项目 | 说明 |
|------|------|
| Project 06 | Mini Transformer：从零实现并训练 |

## 完成标准

- Project 06 可训练并生成文本
- 能画出 Transformer 结构并解释每层作用
- 能手算一次 Scaled Dot-Product Attention
- 能解释为什么需要位置编码

## 下一阶段

[Phase 7 — Hugging Face / 开源大模型](../07-huggingface-open-source-llm/)
