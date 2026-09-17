# FAQ — 常见问题

## 学习路线

### Q: 我有 Java 基础，能跳过 Phase 0 吗？

不建议。Phase 0 不是传统 Python 教材，而是把 Python 基础对接到 AI 开发场景。
即使会 Java，Python 的动态类型、dict/JSON/messages 结构也需要实际写一遍。

### Q: 需要数学基础吗？

Phase 0-4 不需要。Phase 5（PyTorch）开始需要基础线性代数和微积分概念，
但会在用到时补充，不要求提前学完。

### Q: 需要什么硬件？

- Phase 0-4：普通笔记本即可
- Phase 5-8：建议有 GPU（或用 Colab / 云 GPU）
- Phase 9-12：显存越大越好，但也会讲量化方案

## 项目

### Q: Project 01 为什么从这么简单的输入输出开始？

复杂度自然增长：script → function → module → package → application → AI service。
从最简单的开始，每学一课升级一版，最终自然达到 v1.0 完整 CLI。

### Q: 仓库根目录的 projects/ 和 00-python-foundation/projects/ 有什么区别？

根目录 `projects/` 是早期实验性实现（已实现真实 API 调用），可作为参考。
`00-python-foundation/projects/` 是随课程逐步搭建的学习版本，是主线。

## Git

### Q: 为什么推两个远程？

GitHub（origin）是主仓库，Gitee 是国内镜像。每次提交双推，方便国内访问。

### Q: .env 文件为什么不能提交？

`.env` 存放 API Key 等密钥。提交到 git 会导致密钥泄漏。
仓库只提供 `.env.example` 模板，真实 Key 通过环境变量或本地 `.env` 注入。
