# 第一次微调实战 Day10

# AI 工程师面试100问 + 项目答辩模拟

今天进入最后阶段：

> **把“会做 AI 项目”训练成“能通过 AI 工程师面试”。**

你的目标岗位：

- Java AI 应用开发工程师
    
- 大模型应用开发工程师
    
- Agent 应用开发工程师
    
- 高级 Java（AI方向）
    

面试重点不是算法岗，而是：

> **Java工程能力 + LLM应用能力 + AI系统落地能力**

---

# 一、AI工程师面试能力地图

你的项目涉及：

```text
LLM基础
   |
   ├── Token
   ├── Transformer
   ├── Attention
   └── Prompt


RAG
   |
   ├── Document Loader
   ├── Chunk
   ├── Embedding
   ├── Vector Database
   ├── Retriever
   └── Rerank


Agent
   |
   ├── Tool Calling
   ├── Planning
   ├── Memory
   └── MCP


模型优化
   |
   ├── SFT
   ├── LoRA
   ├── QLoRA
   └── Evaluation


工程化
   |
   ├── Spring Boot
   ├── LangChain4j
   ├── SSE
   ├── Redis
   ├── Docker
   └── Monitoring
```

---

# 第一部分：LLM基础 20问

---

# Q1：什么是大语言模型 LLM？

标准回答：

> LLM（Large Language Model，大语言模型）是一类基于 Transformer 架构，通过大规模文本数据预训练得到的模型。它能够学习语言中的统计规律和语义关系，并完成文本生成、理解、推理等任务。

---

# Q2：LLM为什么能够生成文本？

回答：

> LLM本质是在预测下一个 Token 的概率。输入文本经过 Tokenizer 转换为 Token，然后模型根据上下文计算每个候选 Token 的概率，选择概率较高的 Token 逐步生成完整文本。

链路：

```text
文本

↓

Tokenizer

↓

Token

↓

Transformer

↓

概率分布

↓

下一个Token

↓

循环生成
```

---

# Q3：Token是什么？

回答：

> Token 是大模型处理文本的基本单位，不一定等于一个字或者一个单词。模型实际处理的是 Token ID，通过 Embedding 转换为向量后进入 Transformer。

---

# Q4：Token ID 和 Embedding有什么区别？

高频问题。

回答：

> Token ID 是文本经过分词后的编号，例如一个词对应数字1234；Embedding 是将这个编号映射成高维向量，让模型能够理解语义关系。

关系：

```text
文本

↓

Tokenizer

↓

Token ID

↓

Embedding

↓

向量

↓

Transformer
```

---

# Q5：Transformer核心是什么？

回答：

> Transformer核心是 Self-Attention（自注意力机制），它能够让模型计算当前 Token 和其他 Token 之间的关联关系，从而理解上下文。

---

# Q6：Attention解决什么问题？

回答：

> Attention解决传统模型无法很好捕获长距离依赖的问题。例如一句话前面的主语和后面的动作之间可能距离很远，通过Attention可以动态关注相关信息。

---

# Q7：为什么LLM会产生幻觉？

回答：

> 因为LLM本质是概率生成模型，它优化的是生成概率，而不是事实验证。当训练数据不足或者上下文缺失时，模型可能生成看似合理但错误的信息。

解决：

- RAG
    
- 工具调用
    
- 评测
    
- Prompt约束
    

---

# Q8：Prompt Engineering是什么？

回答：

> Prompt Engineering（提示词工程）是通过设计输入指令、上下文和约束条件，引导模型产生符合目标的输出。

---

# Q9：System Prompt和User Prompt区别？

回答：

System：

```text
定义模型角色和规则
```

User：

```text
具体任务
```

例如：

System：

> 你是一名Java高级面试官。

User：

> 解释ConcurrentHashMap。

---

# Q10：Context Window是什么？

回答：

> Context Window（上下文窗口）指模型一次能够处理的最大 Token 数量，包括系统提示词、历史消息和当前输入。

---

# 第二部分：RAG面试30问

---

# Q11：什么是RAG？

回答：

> RAG（Retrieval Augmented Generation，检索增强生成）是一种结合检索系统和大语言模型的方法。它先从外部知识库检索相关信息，再将这些信息提供给LLM生成答案。

---

# Q12：为什么需要RAG？

回答：

> 因为模型参数中的知识存在更新慢、无法访问私有数据的问题。RAG通过外部知识库动态提供信息，不需要重新训练模型。

---

# Q13：RAG完整流程？

标准：

```text
用户问题

↓

Query Embedding

↓

Vector Search

↓

Retriever

↓

TopK文档

↓

Prompt组合

↓

LLM

↓

答案
```

---

# Q14：Embedding是什么？

回答：

> Embedding是将文本转换为高维向量的过程，使语义相似的文本在向量空间距离更近，从而支持语义搜索。

---

# Q15：为什么不用关键词搜索？

回答：

关键词：

```text
字面匹配
```

向量：

```text
语义匹配
```

例如：

问题：

> HashMap安全吗？

关键词可能找不到：

> ConcurrentHashMap并发控制。

向量可以。

---

# Q16：Chunk为什么重要？

回答：

> Chunk决定检索粒度。如果太大，会引入无关内容；如果太小，会丢失上下文。因此需要根据文档类型和检索效果调整。

---

# Q17：Chunk大小怎么选择？

回答：

> 通常根据模型上下文长度、文档类型和测试效果决定，没有固定值。一般几百到上千 Token，并结合 overlap 保持上下文连续。

---

# Q18：什么是Overlap？

回答：

> Overlap表示相邻Chunk之间重复部分，避免切分导致上下文信息丢失。

---

# Q19：Vector Database为什么需要？

回答：

> 向量数据库专门用于存储Embedding，并支持高效相似度搜索，例如Milvus、Pinecone、FAISS。

---

# Q20：Milvus如何实现向量搜索？

回答：

> Milvus通过索引结构保存向量，例如HNSW、IVF等，根据距离算法计算查询向量和库中向量的相似度，返回最相关结果。

---

# Q21：RAG如何优化？

回答：

五个方向：

1. Chunk优化
    
2. Embedding模型优化
    
3. Metadata过滤
    
4. Rerank排序
    
5. Prompt优化
    

---

# Q22：什么是Rerank？

回答：

> Rerank（重排序）是在向量召回后，再使用专门模型对候选文档重新排序，提高最终上下文准确性。

---

# 第三部分：Agent面试30问

---

# Q23：什么是Agent？

回答：

> Agent是一种能够根据目标自主规划任务，并通过调用工具完成复杂任务的AI系统。

---

# Q24：Agent和普通Chat区别？

回答：

普通Chat：

```text
输入 → 输出
```

Agent：

```text
输入

↓

理解任务

↓

规划

↓

调用工具

↓

获取结果

↓

生成答案
```

---

# Q25：Tool Calling是什么？

回答：

> Tool Calling是一种让LLM调用外部工具的方法。LLM负责决定是否调用工具以及生成参数，真正执行工具的是应用程序。

---

# Q26：Tool Schema是什么？

回答：

> Tool Schema是工具的结构化描述，包括工具名称、功能描述以及参数定义，让模型知道有哪些能力可以调用。

---

# Q27：LLM为什么不能直接调用Java方法？

回答：

> 因为LLM只是生成文本，不具备执行环境。Java程序需要负责权限校验、参数验证、安全控制以及真正执行业务逻辑。

---

# Q28：Tool Calling完整链路？

必须背：

```text
用户请求

↓

Java发送消息+Tool Schema

↓

LLM判断

↓

返回Tool Call

↓

Java解析

↓

执行方法

↓

Tool Result

↓

再次发送LLM

↓

最终回答
```

---

# Q29：Agent如何避免乱调用工具？

回答：

- 清晰Tool描述
    
- 参数校验
    
- 权限控制
    
- 最大调用次数
    
- 超时机制
    

---

# 第四部分：LoRA/微调20问

---

# Q30：为什么微调？

回答：

> 微调主要用于让模型适应特定领域、任务或者输出风格，例如让通用模型变成Java面试专家。

---

# Q31：RAG和微调区别？

核心：

||RAG|微调|
|---|---|---|
|解决|知识|行为|
|数据变化|频繁|较稳定|
|成本|低|高|

---

# Q32：LoRA是什么？

回答：

> LoRA是一种参数高效微调方法，通过冻结原模型参数，在部分权重旁增加低秩矩阵，只训练新增参数，从而降低训练成本。

---

# Q33：QLoRA是什么？

回答：

> QLoRA是在LoRA基础上结合4bit量化，使大模型可以在更低显存环境完成微调。

---

# Q34：为什么不用全量微调？

回答：

> 全量微调需要更新模型所有参数，成本和显存要求很高，同时容易产生灾难性遗忘。LoRA只训练少量参数，更适合业务场景。

---

# 第五部分：项目答辩模拟

现在进入真实面试。

## 面试官：

你的项目里面为什么同时使用 RAG 和 LoRA？

请你回答。

要求：

不要背答案。

按照：

```
业务问题
↓
技术选择
↓
为什么这样组合
↓
效果
```

回答。

---

你回答后，我会按照：

- 30K Java + AI岗位标准
    
- 是否像真实项目
    
- 技术漏洞
    
- 面试追问
    

进行评分。

下一题继续：

**Q2：请详细讲一下你的 Agent 一次请求的完整执行链路。**