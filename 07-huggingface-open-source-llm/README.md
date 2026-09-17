# 07-huggingface-open-source-llm — Phase 7：Hugging Face / 开源大模型

> 站上开源生态肩膀，加载、调用、部署真正的开源大模型。

## 这一阶段学什么

- Hugging Face Transformers 库
- Tokenizer 原理与使用
- 模型加载与 device_map
- Generation 参数（temperature / top_p / top_k）
- 开源模型选型（Llama / Qwen / Mistral）
- 本地推理与显存管理

## 为什么学

商业 API 有成本、隐私、可控性限制。掌握 HF 生态就能在本地跑开源大模型，是微调、量化、私有化部署的前置条件，也是企业落地 AI 的关键能力。

## 前置知识

- [Phase 6 — Transformer / LLM](../06-transformer-llm/)

## 核心技能

- 用 transformers 加载开源模型
- 用 Tokenizer 编码 / 解码文本
- 配置 Generation 控制输出风格
- 用 device_map 管理多卡显存
- 对比并选型开源模型
- 在本地跑通一次完整推理

## 项目

| 项目 | 说明 |
|------|------|
| Project 08 | Local Open Source LLM：本地部署可对话 |

## 完成标准

- Project 08 本地可运行开源模型对话
- 能解释 Tokenizer 的 BPE / SentencePiece
- 能调 Generation 参数改变输出
- 能在显存不足时做合理选型

## 下一阶段

[Phase 8 — Fine-tuning](../08-fine-tuning/)
