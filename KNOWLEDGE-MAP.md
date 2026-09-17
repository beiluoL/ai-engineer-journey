# AI Engineer Journey Knowledge Map

## 全局路线

```text
Python
 ↓
Python Engineering
 ↓
AI Application
 ↓
Embedding & RAG
 ↓
Agent / MCP
 ↓
PyTorch
 ↓
Transformer / LLM
 ↓
Hugging Face / 开源模型
 ↓
Fine-tuning
 ↓
Evaluation / Quantization
 ↓
Inference / vLLM
 ↓
Docker / Deployment
 ↓
Mini LLM
```

## Python Foundation 关键路径

```text
Variables
  ↓
List + Dict
  ↓
JSON
  ↓
HTTP API
  ↓
LLM Messages (system / user / assistant)
```

## 节点依赖（Python 基础）

| 节点 | 前置 | 后续 | Java 类比 |
|------|------|------|-----------|
| variables/types | — | 全部 | Java 变量与类型 |
| input/output | variables | 全部 | Scanner / println |
| list | variables | for, messages | ArrayList |
| dict | variables | json, messages | HashMap |
| json | dict | http/api | Jackson |
| function | if/for | module, class | Java 方法 |
| module | function | 全部 | Java 包/类路径 |
| class | function | exception | Java 类 |
| exception | function | file/json | try/catch |
| file/json | dict | RAG 文档解析 | Jackson |
| http/api | json | LLM API | HttpClient |
| async | function | FastAPI SSE | CompletableFuture |
