# 第一次微调实战 Day8

# 把 Java AI Interview Agent 包装成真实求职项目

今天不是学习新技术。

今天做一件对你求职最重要的事情：

> **把一个技术实验，包装成一个企业级 AI 应用项目。**

因为面试官不会因为你说：

> “我训练了一个 Qwen LoRA”

就认可你。

他们更关心：

- 为什么做？
    
- 解决什么业务问题？
    
- 架构怎么设计？
    
- 为什么选 RAG？
    
- 为什么微调？
    
- 遇到什么问题？
    
- 如何保证效果？
    

---

# 一、项目定位重新设计

不要叫：

❌

```
Qwen微调实验
```

太像学习 Demo。

改成：

✅

# Java AI Interview Agent

## 基于大模型的智能面试辅助系统

---

# 二、项目背景设计

面试版本：

> 随着大模型应用的发展，传统 Java 工程师面试准备存在知识分散、缺少个性化反馈、无法持续训练等问题。因此设计并实现了一套基于大语言模型的智能面试 Agent 系统，通过 RAG 技术连接个人技术知识库，通过 LoRA 微调优化 Java 面试回答风格，实现自动出题、知识检索、回答评分和个性化训练。

---

# 三、项目功能设计

不要堆功能。

按照企业产品设计。

## 功能1：智能面试

用户：

```
开始Java高级面试
```

Agent：

自动：

```
选择难度
生成问题
等待回答
评分
继续追问
```

---

## 功能2：技术知识库问答

支持上传：

```
PDF
Markdown
Word
源码
博客
```

例如：

上传：

```
Spring源码分析.md
JVM调优文档.md
项目架构文档.md
```

系统：

```
Chunk
 ↓
Embedding
 ↓
Milvus
 ↓
RAG
```

---

## 功能3：回答评分

用户回答：

> ConcurrentHashMap为什么线程安全？

系统评分：

```json
{
"score":85,

"strength":
"理解CAS+synchronized",

"weakness":
"缺少扩容机制",

"suggestion":
"补充Transfer源码"
}
```

---

## 功能4：个性化模型

通过：

```
QLoRA
+
Java面试数据
```

让模型学习：

你的回答模板。

---

# 四、项目架构图

面试展示：

```text
                         用户

                          |

                          ↓


                       Vue3


                          |

                          ↓


                    Spring Boot


                          |

                          ↓


                  LangChain4j Agent


                          |

        +-----------------+----------------+

        |                 |                |


        ↓                 ↓                ↓


    RAG Tool        Interview Tool    Score Tool


        |                 |                |


        ↓                 ↓                ↓


     Milvus           Question DB       Evaluation


        |

        ↓


    Retriever


        |

        ↓


 Prompt Assembly


        |

        ↓


 Qwen2.5 + LoRA


        |

        ↓


   SSE Streaming

```

---

# 五、技术栈包装

简历不要写：

“用了很多AI名词”。

要按职责。

## 后端

```
Java
Spring Boot 3
MySQL
Redis
RESTful API
```

---

## AI应用

```
LangChain4j
RAG
Embedding
Vector Database
Milvus
Prompt Engineering
Tool Calling
Agent
```

---

## 模型

```
Qwen2.5
LLaMA-Factory
QLoRA
LoRA
Ollama
```

---

## 工程化

```
Docker
SSE
日志追踪
Evaluation
Token统计
```

---

# 六、简历项目描述（可直接使用）

**Java AI Interview Agent｜基于大模型的智能面试辅助系统**

项目介绍：  
基于大语言模型构建的智能面试训练平台，面向 Java 工程师技术面试场景，实现知识库检索、智能问答、模拟面试、回答评分以及个性化模型优化能力。

技术栈：  
Spring Boot 3、LangChain4j、Qwen2.5、QLoRA、LoRA、Milvus、Embedding、Ollama、Redis、MySQL、Docker。

主要工作：

1. 基于 Spring Boot + LangChain4j 搭建 AI Agent 服务，实现用户问题理解、任务规划以及 Tool Calling 工具调用流程。
    
2. 搭建 RAG 知识增强链路，将 Java 源码分析、面试笔记和项目文档进行文档解析、Chunk切分、Embedding向量化，并存储至 Milvus，实现基于私有知识库的精准问答。
    
3. 使用 LLaMA-Factory 基于 Qwen2.5 模型进行 QLoRA 微调，构建 Java 面试领域适配模型，使模型能够按照高级工程师面试表达方式输出答案。
    
4. 设计多工具 Agent 架构，实现知识检索、简历分析、面试评分等能力，通过 Tool Calling 动态选择工具完成复杂任务。
    
5. 基于 SSE 实现模型流式输出，结合 Redis 实现用户会话记忆，提高交互体验。
    
6. 建立 AI Evaluation 评测流程，通过测试数据集评估检索准确率、回答完整性以及模型幻觉问题。
    

项目成果：

- 实现从文档上传、知识检索、Agent决策到模型回答的完整 AI 应用链路。
    
- 支持个人技术知识库问答和 Java 高级面试模拟训练。
    
- 完成大模型应用开发、RAG、Agent、模型微调完整实践。
    

---

# 七、面试重点追问准备

面试官看到：

> QLoRA微调Qwen

一定追问：

---

## Q1：为什么不用直接 Prompt？

回答：

> Prompt 可以改变输入方式，但无法稳定改变模型输出习惯。我的场景需要模型长期按照 Java 高级面试结构回答，因此使用 LoRA 微调学习回答风格。同时知识内容变化较快，所以通过 RAG 提供实时知识。

---

## Q2：为什么 RAG 和微调同时使用？

回答：

> 两者解决的问题不同。RAG主要解决知识更新和私有知识注入问题，LoRA主要优化模型行为和领域适配。例如 Java 最新源码知识通过RAG获取，而面试回答结构通过LoRA优化。

---

## Q3：为什么不用把所有知识训练进去？

回答：

> 因为知识变化频繁，全部微调成本高，并且容易产生灾难性遗忘。企业场景通常采用RAG管理动态知识，微调用于优化模型能力和行为。

---

## Q4：LoRA原理？

30秒：

> LoRA是一种参数高效微调方法，不直接更新大模型全部参数，而是在Transformer部分权重旁增加低秩矩阵，只训练新增参数，从而降低显存和训练成本。

---

# 八、你的项目真实性问题

这里需要注意：

不要面试说：

❌

> 我训练了一个7B大模型。

容易被追问。

更准确：

✅

> 我基于开源 Qwen 模型，通过 LLaMA-Factory 使用 QLoRA 完成领域适配实验，并将 LoRA Adapter 集成到推理流程中。

这是工程师表达。

---

# 九、项目开发路线（真实可完成）

建议最终版本：

## V1（1周）

完成：

```
Spring Boot
+
LangChain4j
+
Ollama
+
RAG
```

---

## V2（1周）

加入：

```
Agent
+
Tool Calling
+
Memory
```

---

## V3（1周）

加入：

```
Qwen
+
QLoRA
+
Evaluation
```

---

## V4（求职展示）

加入：

```
Docker
+
部署
+
监控
+
项目文档
```

---

# 十、你现在对应招聘岗位

这个项目可以支撑：

|岗位|匹配|
|---|---|
|Java AI应用开发工程师|⭐⭐⭐⭐⭐|
|大模型应用开发工程师|⭐⭐⭐⭐|
|Agent应用开发工程师|⭐⭐⭐⭐|
|高级Java工程师（AI方向）|⭐⭐⭐⭐|
|算法训练岗|⭐⭐|

---

# 下一步 Day9

进入最后一个非常重要阶段：

# Day9：模拟真实 AI 工程师面试

我们会准备：

1. 项目介绍 3分钟版本
    
2. 架构设计回答
    
3. RAG追问
    
4. LoRA追问
    
5. Agent追问
    
6. Tool Calling源码追问
    
7. 面试官刁钻问题
    

这一阶段会把“会做项目”转换成“能拿 offer 的表达能力”。