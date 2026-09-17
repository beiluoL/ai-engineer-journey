# Glossary — 术语表

> AI Engineer Journey 中出现的术语，按阶段补充。

## Python Foundation

| 术语 | 含义 |
|------|------|
| f-string | Python 格式化字符串，`f"..."` 语法 |
| 动态类型 | 变量类型在运行时确定，不需要声明 |
| snake_case | 用下划线分隔单词的命名风格，Python 习惯 |
| venv | Python 虚拟环境，隔离依赖 |
| pip | Python 包管理器 |

## AI Application

| 术语 | 含义 |
|------|------|
| LLM | Large Language Model，大语言模型 |
| Prompt | 给 LLM 的输入提示 |
| Token | LLM 处理文本的最小单位 |
| Streaming | 流式输出，逐 token 返回 |
| messages | LLM API 的对话结构，role + content |

## RAG

| 术语 | 含义 |
|------|------|
| Embedding | 把文本转成向量 |
| Chunk | 文档分块 |
| 向量库 | 存储和检索向量的数据库 |
| Rerank | 对检索结果重排序 |

## Agent

| 术语 | 含义 |
|------|------|
| Function Calling | LLM 调用外部函数 |
| Agent | 能自主规划和执行多步任务的 AI |
| MCP | Model Context Protocol |

## 模型工程

| 术语 | 含义 |
|------|------|
| Attention | Transformer 的注意力机制 |
| SFT | Supervised Fine-Tuning，监督微调 |
| LoRA | Low-Rank Adaptation，低秩适配微调 |
| QLoRA | 量化版 LoRA |
| 量化 | 降低模型精度以减少显存（INT8/INT4） |
| vLLM | 高性能 LLM 推理引擎 |
