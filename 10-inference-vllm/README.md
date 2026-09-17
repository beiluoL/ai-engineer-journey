# 10-inference-vllm — Phase 10：Inference / vLLM

> 用工业级推理引擎把模型服务化，吞吐量翻倍。

## 这一阶段学什么

- vLLM 推理框架
- PagedAttention 原理
- Continuous Batching
- OpenAI 兼容 API 服务
- 吞吐与延迟调优
- 多模型并发服务

## 为什么学

HuggingFace 原生推理慢、显存利用率低，无法支撑生产并发。vLLM 是当前主流开源推理引擎，掌握它就能把模型真正变成可对外提供服务的高性能 API。

## 前置知识

- [Phase 9 — Evaluation / Quantization](../09-evaluation-quantization/)

## 核心技能

- 用 vLLM 启动模型服务
- 理解 PagedAttention 显存管理
- 配置 Continuous Batching 提升吞吐
- 暴露 OpenAI 兼容接口
- 压测并调优吞吐 / 延迟
- 对比 vLLM 与原生推理性能

## 项目

| 项目 | 说明 |
|------|------|
| Project 12 | LLM Serving：vLLM 高性能推理服务 |

## 完成标准

- Project 12 可对外提供 OpenAI 兼容 API
- 能解释 PagedAttention 解决了什么问题
- 压测吞吐量明显高于原生推理
- 能配置 batch 与并发参数

## 下一阶段

[Phase 11 — Docker / Deployment](../11-docker-deployment/)
