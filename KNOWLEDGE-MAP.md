# KNOWLEDGE-MAP — 知识地图

> 描述知识节点的依赖关系。每个节点标记：前置 / 后续 / 关联 / 实战项目。
> 学新知识前，先在这里确认前置节点已掌握。

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

## 节点明细

### Python 基础（Phase 0）

| 节点 | 前置 | 后续 | 关联 | 实战项目 |
|------|------|------|------|----------|
| variables/types | — | 全部 | Java 变量与类型 | P01 配置读取 |
| string | variables | 全部 | Java String（不可变性差异） | P01 用户输入处理 |
| list | variables | for, module | Java List（ArrayList） | P01 message history(v0.2) |
| dict | variables | json, class | Java Map（HashMap） | P01 JSON 消息构造 |
| if / for | types | function | Java if/for（缩进即块） | P01 交互循环 |
| function | if/for | module, class | Java 方法（一等公民差异） | P01 client 封装 |
| module | function | 全部 | Java 包/类路径 | P01 assistant 包 |
| class | function | exception | Java 类（无接口概念差异） | P01 LLMClient |
| exception | function | file/json | Java try/catch（受检异常差异） | P01 API 重试(v0.7) |
| file / json | dict, exception | RAG 文档解析 | Jackson | P01 历史保存(v0.5) |
| env | — | 部署配置 | 环境变量注入 | P01 API Key 管理 |
| venv / pip | — | 一切第三方库 | Maven 依赖隔离 | P01 依赖管理(Phase 1) |

### 主线路线

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

### 关键决策点（学完后的能力）

- 学完 Phase 3（RAG）：能判断"知识增强"类需求该用 Prompt 还是 RAG。
- 学完 Phase 4（Agent）：能判断"多步任务"该用 Chain 还是 Agent。
- 学完 Phase 8（Fine-tuning）：能判断该用 RAG、微调还是两者结合。
- 学完 Phase 12（TinyGPT）：真正理解 LLM 内部发生了什么。
