# Project 06 — Mini Transformer / LLM

## 项目目标

从 AI 应用层进入模型内部，从零构建 Mini Transformer Decoder。

## 为什么做这个项目

会调用 LLM 不等同于理解 LLM。作为 AI 工程师，必须知道 Transformer 内部发生了什么，才能调试、优化、微调模型。

## 解决什么问题

- 只会"调 API"，看不懂模型内部代码
- 不理解 Attention【注意力机制】到底做了什么
- 不知道怎么从零写一个 Transformer Decoder

## 最终能力

```text
数据
    ↓
Token
    ↓
Embedding
    ↓
Attention
    ↓
Transformer
    ↓
Training
    ↓
Inference
```

自己解释和实现核心链路。

## 技术栈

- PyTorch / Tensor / Autograd
- Dataset / DataLoader
- Self-Attention / Multi-Head Attention
- Feed-Forward Network / LayerNorm
- Decoder-Only Transformer

## 项目演进

```
前面都是"调用层"
    ↓ 深入模型层
Mini Transformer v0.1（单 Attention）
    ↓ Multi-Head + FFN
Mini Transformer v0.2（完整 Block）
    ↓ 堆叠 + Training
Mini Transformer v1.0（完整 Decoder）
```

## Milestones

| # | Milestone | 核心能力 |
|---|-----------|----------|
| 01 | Tensor | PyTorch Tensor 基础 |
| 02 | Autograd | 自动求导 / 反向传播 |
| 03 | Dataset / DataLoader | 数据 Pipeline |
| 04 | Neural Network | nn.Module / 自定义网络 |
| 05 | Training Loop | 完整训练循环 |
| 06 | Tokenization | 分词 / Token 编码 |
| 07 | Embedding | Embedding / Positional Encoding |
| 08 | Attention | Attention 原理 |
| 09 | Self-Attention | Self-Attention 实现 |
| 10 | Transformer | Multi-Head + FFN + LN |
| 11 | Decoder-Only LLM | 完整 Decoder 堆叠 |
| 12 | Mini LLM Training | 完整训练实验 |

## 当前状态

⬜ 未开始

## 当前版本

还未开始。

## 项目结构

```
src/
└── （Mini Transformer 实现）
```

## 已掌握能力

- Project 01-05 的所有能力

## 下一步

完成 Project 05，然后进入模型原理。

**前置项目**：[Project 05 — Research Agent / MCP Assistant](../05-agent-mcp/)
