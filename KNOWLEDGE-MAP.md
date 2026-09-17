# KNOWLEDGE-MAP — 知识关系地图

> 描述知识节点的依赖关系。学新知识前，先在这里确认前置节点已掌握。
> 详情见 [knowledge/map/](knowledge/map/)

## Python Foundation

```text
Python Foundation
│
├── Variables
├── Types (str / int / float / bool / None)
├── Input / Output
├── List
├── Dict
├── JSON
├── Function
├── Module / Package
├── OOP / Class
├── Exception
├── File
├── HTTP / API
└── Async
```

## 关键路径

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

## 全局路线

```text
Python
 ↓
Python Engineering
 ↓
HTTP / API
 ↓
FastAPI
 ↓
LLM API / Prompt / Token
 ↓
Embedding → RAG
 ↓
Agent / MCP
 ↓
PyTorch
 ↓
Attention / Transformer
 ↓
开源模型 / Fine-tuning
 ↓
Evaluation / Quantization
 ↓
vLLM / Docker / 生产部署
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
