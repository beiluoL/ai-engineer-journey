# 11-docker-deployment — Phase 11：Docker / Deployment

> 把 AI 应用装进容器，完成从「能跑」到「能上线」的最后一公里。

## 这一阶段学什么

- Docker 与镜像构建
- Docker Compose 多服务编排
- 前后端 + 模型服务联调
- GPU 容器与 nvidia-docker
- 生产环境配置管理
- 部署与回滚流程

## 为什么学

开发环境能跑不等于上线。Docker 让 AI 应用（前端 + FastAPI + vLLM + 向量库）可复现、可移植、可规模化部署，是 AI 工程师交付能力的体现。

## 前置知识

- [Phase 10 — Inference / vLLM](../10-inference-vllm/)

## 核心技能

- 写 Dockerfile 打包 AI 服务
- 用 Compose 编排多容器
- 配置 GPU 容器运行时
- 前后端 + 模型服务联调
- 用环境变量管理多环境配置
- 完成一次完整的本地部署

## 项目

| 项目 | 说明 |
|------|------|
| Project 13 | Production AI Platform：容器化生产部署 |

## 完成标准

- Project 13 一键 docker compose up 启动全栈
- 前端 / 后端 / 模型服务可联调
- GPU 在容器内可用
- 有基本的环境分离与回滚能力

## 下一阶段

[Phase 12 — Mini LLM](../12-mini-llm/)
