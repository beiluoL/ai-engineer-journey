# Day15 企业级 RAG 深度优化

# Hybrid Search + Rerank + Agentic RAG + Evaluation

前面 Day5 你实现了：

```text
基础 RAG Pipeline

文档

↓

Chunk

↓

Embedding

↓

Milvus

↓

Retriever

↓

LLM

↓

答案
```

这已经可以跑 Demo。

但是企业上线后，会遇到大量问题：

---

## 问题1：为什么搜不到？

用户：

> ConcurrentHashMap 为什么线程安全？

知识库：

```text
JDK8 ConcurrentHashMap源码解析
CAS机制分析
Node节点设计
```

但是：

向量搜索可能召回：

```text
HashMap基础
Map接口介绍
```

原因：

语义相似，但是不够精准。

---

## 问题2：为什么找到很多垃圾内容？

例如：

TopK=10：

返回：

```text
1. ConcurrentHashMap源码

2. Java集合介绍

3. HashMap历史

4. List源码

5. JVM介绍
```

真正需要：

只有第1个。

---

## 问题3：为什么模型还是胡说？

因为：

检索质量不好。

LLM再强也无法弥补错误上下文。

---

所以企业 RAG：

不是：

```text
Embedding + Vector DB
```

而是：

```text
Query理解

↓

Hybrid Search

↓

Rerank

↓

Context压缩

↓

LLM

↓

Evaluation
```

---

# 一、企业级 RAG 架构

最终：

```text
                 用户问题

                     |

                     ↓


              Query Rewrite


                     |

        +------------+-------------+

        |                          |


        ↓                          ↓


  Vector Search             Keyword Search


 Milvus                     Elasticsearch


        |                          |


        +------------+-------------+

                     |

                     ↓


              Merge Result


                     |

                     ↓


                 Reranker


                     |

                     ↓


              Top Context


                     |

                     ↓


                  Prompt


                     |

                     ↓


                    LLM

```

---

# 二、Hybrid Search【混合搜索】

## 什么是 Hybrid Search？

Hybrid：

混合。

结合：

1. Dense Retrieval【稠密检索】
    
2. Sparse Retrieval【稀疏检索】
    

---

简单理解：

## 向量搜索

擅长：

语义。

例如：

问题：

> HashMap安全吗？

找到：

> ConcurrentHashMap并发控制

---

但是：

不擅长：

精确关键词。

例如：

用户：

> AQS acquireQueued源码

向量可能找：

> ReentrantLock源码

但是：

可能找不到：

`acquireQueued`。

---

## 关键词搜索

擅长：

精确匹配。

例如：

搜索：

```text
acquireQueued
```

马上找到。

---

所以：

组合：

```text
向量搜索

+

关键词搜索

↓

更全面
```

---

# 三、Hybrid Search实现

## 方案1：Milvus + BM25

架构：

```text
用户问题

       |

       |

+------+------+

|             |


BM25        Embedding


|             |


关键词       语义


+------+------+

       |

       ↓


结果融合
```

---

## BM25是什么？

BM25：

**Best Matching 25【最佳匹配算法】**

传统搜索算法。

例如：

ElasticSearch默认相关算法。

---

# 四、为什么需要 Rerank？

这是企业 RAG 核心。

流程：

第一阶段：

召回。

目标：

> 找全。

例如：

TopK=50。

---

第二阶段：

排序。

目标：

> 找准。

例如：

50个：

↓

Reranker

↓

5个。

---

架构：

```text
用户问题

↓

Retriever

↓

50个Chunk

↓

Reranker

↓

5个Chunk

↓

LLM
```

---

# 五、Reranker原理

普通Embedding：

判断：

```text
问题向量

和

文档向量

距离
```

---

Rerank模型：

直接：

输入：

```text
问题:

ConcurrentHashMap扩容


文档:

JDK8扩容通过transfer方法...
```

输出：

```json
{
"score":0.96
}
```

---

# 六、常见Rerank模型

开源：

## BGE Reranker

例如：

```text
BAAI/bge-reranker
```

---

## Cohere Rerank

商业。

---

## Jina Reranker

商业+开源。

---

# 七、RAG优化前后区别

## 普通RAG

```text
问题

↓

Embedding

↓

Milvus Top5

↓

LLM
```

问题：

召回不稳定。

---

## 企业RAG

```text
问题

↓

Query Rewrite

↓

Hybrid Search

↓

Top50

↓

Rerank

↓

Top5

↓

LLM
```

---

# 八、Query Rewrite【查询改写】

用户输入：

可能不好。

例如：

用户：

> hashmap问题

改写：

```text
请解释JDK8 HashMap线程安全问题，包括：

1. 数据结构

2. put过程

3. resize

4. 并发风险

5. 面试回答
```

---

为什么？

提高检索。

---

# 九、Agentic RAG【智能体RAG】

普通RAG：

固定流程。

```text
问题

↓

搜索

↓

回答
```

---

Agentic RAG：

Agent决定：

是否搜索。

搜索几次。

搜索什么。

---

架构：

```text
用户

↓

Agent

↓

判断:

需要知识吗？

        |

       是

        ↓

调用Search Tool


        ↓

判断结果

        ↓

需要继续搜索？

        ↓

回答
```

---

# 十、你的 Java AI Interview Agent 升级

以前：

用户：

> AQS是什么？

固定：

```text
搜索一次

↓

回答
```

升级：

Agent：

```text
用户问题

↓

Agent分析


需要：

源码知识

+

面试表达模板


↓

Tool1:

搜索AQS源码


↓

Tool2:

搜索面试模板


↓

Tool3:

查询历史薄弱点


↓

生成答案
```

---

# 十一、Evaluation【评测系统】

企业最容易忽略。

不能：

“感觉效果很好”。

需要数据。

---

# 1. Golden Dataset【黄金测试集】

建立：

```json
{
"question":
"ConcurrentHashMap为什么线程安全？",

"expected_keywords":[

"CAS",

"synchronized",

"Node"

]
}
```

---

# 2. RAG评测指标

## Retrieval Recall【召回率】

问题：

正确答案有没有被找到。

例如：

100个问题：

找到90个。

Recall：

90%。

---

## Precision【准确率】

找到的内容：

多少相关。

---

## Faithfulness【忠实度】

答案是否来自知识库。

---

## Answer Relevance【答案相关性】

回答是否解决问题。

---

# 十二、自动评测流程

架构：

```text
测试问题

↓

RAG系统

↓

生成答案

↓

Evaluator模型

↓

评分

↓

报告
```

---

例如：

输出：

```json
{
"retrieval_score":0.92,

"answer_score":0.88,

"hallucination":false
}
```

---

# 十三、RAG生产监控

上线后监控：

---

## 检索

指标：

- Recall
    
- TopK命中率
    
- Rerank分数
    

---

## 模型

指标：

- Token
    
- 延迟
    
- 错误率
    

---

## 用户

指标：

- 满意度
    
- 反馈
    

---

# 十四、你的项目最终架构升级

Java AI Interview Agent V7：

```text
                    用户

                     |

                     ↓


                Spring Boot


                     |

                     ↓


              LangChain4j Agent


                     |

                     ↓


              Agentic RAG


                     |

        +------------+-------------+

        |                          |


        ↓                          ↓


 Hybrid Search              Tool Calling


        |                          |


        ↓                          ↓


 Milvus + BM25              Resume Tool


        |

        ↓


     Reranker


        |

        ↓


     Prompt


        |

        ↓


   Qwen + LoRA


        |

        ↓


     Answer
```

---

# 十五、面试回答模板

面试官：

> 你们项目RAG效果如何优化？

回答：

> 初始版本采用Embedding加向量数据库检索，但发现存在召回不准确问题。因此进行了优化：首先增加Query Rewrite改善用户问题表达，然后采用Hybrid Search结合关键词检索和向量检索提升召回能力，再通过Reranker模型对候选文档进行重排序，最终将高质量上下文输入大模型。同时建立Evaluation数据集，通过Recall、相关性和幻觉指标持续评估优化。

---

# 十六、今天你的能力升级

现在你的知识体系：

```text
RAG

↓

基础检索

↓

Hybrid Search

↓

Rerank

↓

Agentic RAG

↓

Evaluation

↓

Production RAG
```

这已经是企业大模型应用开发核心能力。

---

# 下一节 Day16

建议进入：

# 《Day16：大模型应用安全与稳定性：Prompt Injection、防止幻觉、权限控制、数据安全》

因为企业上线 AI 系统，面试官一定会问：

- 用户输入恶意 Prompt 怎么办？
    
- 如何防止模型泄露公司数据？
    
- 如何控制 Agent 工具权限？
    
- 如何保证回答可信？
    

这部分会把你的项目从：

> 能跑

升级到：

> 企业敢上线。