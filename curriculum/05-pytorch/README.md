# 05-pytorch — Phase 5：PyTorch

> 走进深度学习，从手写张量到跑通第一个训练循环。

## 这一阶段学什么

- 张量（Tensor）与运算
- 自动求导（autograd）
- DataLoader 与数据集
- 训练循环：前向 / 反向 / 更新
- 模型保存与加载
- GPU 与 CUDA 基础

## 为什么学

后续要理解 Transformer、微调、量化、训练 TinyGPT，都必须能看懂和写 PyTorch 代码。这是从「调 API」到「懂模型」的分水岭。

## 前置知识

- [Phase 0 — Python Foundation](../00-python-foundation/)
- [Phase 1 — Python Engineering](../01-python-engineering/)

## 核心技能

- 用 Tensor 做矩阵运算
- 理解 autograd 自动求导
- 用 DataLoader 批量喂数据
- 手写训练循环（loss / backward / step）
- 把模型搬到 GPU 训练
- 保存 / 加载 checkpoint

## 项目

| 项目 | 说明 |
|------|------|
| Project 07 | Tiny Language Model：从零训练一个最小语言模型 |

## 完成标准

- Project 07 可训练并产出 loss 曲线
- 能解释前向 / 反向传播流程
- 能在 CPU 与 GPU 间切换训练
- 能用 Tensor 实现简单的线性回归

## 下一阶段

[Phase 6 — Transformer / LLM](../06-transformer-llm/)
