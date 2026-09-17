# KNOWLEDGE-MAP — 知识地图

> 描述知识节点的依赖关系。学新知识前，先在这里确认前置节点已掌握。

## Python Foundation

```text
Python Foundation
│
├── Variables
├── Types (str / int / float / bool / None)
├── Input / Output (input / print / f-string)
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

## 关键路径：从 List+Dict 到 LLM Messages

```text
List + Dict
    ↓
JSON
    ↓
API Request
    ↓
LLM Messages (system / user / assistant)
```

这是 Python 基础通向 AI 应用最关键的一条路径。

## 全局路线

```text
Python
 ↓
Python Engineering (venv/pip/测试/async)
 ↓
HTTP / API
 ↓
FastAPI
 ↓
LLM API / Prompt / Token
 ↓
Embedding
 ↓
RAG
 ↓
Agent
 ↓
PyTorch
 ↓
Attention / Transformer
 ↓
开源模型 / Fine-tuning
 ↓
Evaluation / Quantization
 ↓
Deployment (vLLM / Docker)
```

## 主线依赖图

```text
[Python]──┬─→ [HTTP/API]──→ [FastAPI]──→ [LLM API]──→ [Prompt/Token]──→ [Embedding]
          │                                                     │
          │                                                     ↓
          ├─→ [PyTorch]──→ [Attention]──→ [Transformer]──→ [开源模型]
          │                                      │
          │                                      ↓
          │                              [Fine-tuning: SFT/LoRA/QLoRA]
          │                                      │
          ↓                                      ↓
      [RAG]──→ [Agent]──→ [MCP]          [Evaluation]──→ [Quantization]
                                                 │
                                                 ↓
                                          [vLLM / Docker / 生产部署]
```

## 节点明细：Python 基础（Phase 0）

| 节点 | 前置 | 后续 | Java 类比 | 实战项目 |
|------|------|------|-----------|----------|
| variables/types | — | 全部 | Java 变量与类型 | P01 配置读取 |
| input/print | variables | 全部 | Scanner / println | P01 用户交互 |
| list | variables | for, messages | ArrayList | P01 message history(v0.2) |
| dict | variables | json, messages | HashMap | P01 JSON 消息构造 |
| json | dict | http/api | Jackson | P01 API 请求/响应 |
| function | if/for | module, class | Java 方法 | P01 client 封装 |
| module | function | 全部 | Java 包/类路径 | P01 assistant 包 |
| class | function | exception | Java 类 | P01 LLMClient |
| exception | function | file/json | try/catch | P01 API 重试 |
| file / json | dict, exception | RAG 文档解析 | Jackson | P01 历史保存 |
| http / api | json | LLM API | HttpClient | P01 LLM 调用(v0.9) |
| async | function | FastAPI SSE | CompletableFuture | P01 Streaming |
| typing/dataclass | class | FastAPI Pydantic | Record/DTO | P01 配置模型 |
| config/env | — | 部署配置 | 环境变量注入 | P01 API Key 管理 |
| testing | function, module | 全部 | JUnit | P01 单元测试 |

## 关键决策点（学完后的能力）

- 学完 Phase 2（AI Application）：能判断需求该用 Prompt 还是工具调用
- 学完 Phase 3（RAG）：能判断"知识增强"类需求该用 Prompt 还是 RAG
- 学完 Phase 4（Agent）：能判断"多步任务"该用 Chain 还是 Agent
- 学完 Phase 8（Fine-tuning）：能判断该用 RAG、微调还是两者结合
- 学完 Phase 12（TinyGPT）：真正理解 LLM 内部发生了什么
