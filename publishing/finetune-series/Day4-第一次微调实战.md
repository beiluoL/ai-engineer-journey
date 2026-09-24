# 第一次微调实战 Day4

# 把 RAG + LoRA 结合：构建真正可用的 Java AI Interview Agent

今天进入一个非常关键的认知升级：

> 企业里的 AI 应用，很少是“只微调模型”。

更常见架构：

> **RAG 负责提供知识，LoRA 负责改变模型行为。**

也就是：

```text
RAG = 给模型外挂知识库
LoRA = 教模型按照你的方式思考和表达
```

---

# 一、先理解 RAG 和 LoRA 的区别

很多初学者会混淆：

## LoRA 解决什么？

例如：

原始 Qwen：

用户：

> HashMap 面试怎么回答？

模型：

```text
HashMap是Java中的Map实现...
```

但是你希望：

```text
面试回答：

1. 先说数据结构
2. 再说JDK8变化
3. 再说扩容机制
4. 最后结合项目
```

这个属于：

> 输出风格、能力偏好改变

所以：

```text
LoRA

改变：

模型行为
回答方式
专业领域习惯
```

---

## RAG解决什么？

例如：

你公司内部：

```text
订单系统架构文档

支付流程文档

数据库设计文档

接口文档
```

Qwen不知道。

RAG：

先检索：

```text
订单系统文档

↓

找到相关内容

↓

放入Prompt

↓

让模型回答
```

所以：

```text
RAG

补充：

外部知识
实时数据
私有数据
```

---

# 二、企业真实架构

你的 Java AI 项目：

```text
                    用户问题

                       |
                       ↓

                Spring Boot API


                       |
                       ↓


              Query Rewrite
              查询改写


                       |
                       ↓


             Milvus Vector DB
             向量数据库


                       |
                       ↓


          找到Java知识片段


                       |
                       ↓


             Prompt组装


                       |
                       ↓


          Qwen + Java LoRA


                       |
                       ↓


                 最终回答
```

---

# 三、为什么不是只微调？

假设：

你训练：

```text
Java面试LoRA
```

训练数据：

1000条。

突然面试官问：

> 公司订单系统如何保证幂等？

你的LoRA：

不知道。

因为：

训练数据没有。

如果加入RAG：

你的知识库：

```
项目A
├──订单设计.md
├──支付流程.md
├──Redis方案.md
```

检索：

找到：

```text
订单幂等方案：

Redis + Token + 唯一索引
```

模型：

结合回答。

---

# 四、你的最终项目架构

## Java AI Interview Agent V2

```text
                 Vue3

                  |

                  ↓

            Spring Boot


                  |

                  ↓


          LangChain4j


                  |

       +----------+-----------+

       |                      |

       ↓                      ↓


    Milvus                 Qwen LoRA

    知识库                  面试模型


       |                      |

       +----------+-----------+

                  |

                  ↓


              Answer
```

---

# 五、开始实现

我们分模块。

---

# Step1：准备知识库

你的数据：

之前：

```text
java_interview.json
```

现在升级：

```
knowledge/

├── java

│   ├── hashmap.md

│   ├── concurrenthashmap.md

│   ├── jvm.md


├── ai

│   ├── rag.md

│   ├── agent.md

│   └── toolcalling.md


└── project

    └── ai-assistant.md
```

---

例如：

hashmap.md

```markdown
# HashMap


## 数据结构

JDK8 HashMap采用：

数组 + 链表 + 红黑树。


## 为什么线程不安全

原因：

1. put操作没有锁

2. resize并发可能覆盖

3. 数据一致性无法保证


## 面试回答

HashMap线程不安全主要原因...
```

---

# Step2：文档切片 Chunk

RAG不会直接把整个文件给模型。

例如：

100页文档：

↓

切：

```
Chunk1

HashMap数据结构


Chunk2

扩容机制


Chunk3

线程安全问题
```

---

通常：

配置：

```text
chunk size:

500~1000 tokens


overlap:

100 tokens
```

---

# Step3：Embedding向量化

文本：

```text
HashMap为什么线程不安全
```

经过：

Embedding模型

变成：

```text
[
0.123,
0.562,
-0.331,
...
]
```

保存：

Milvus。

---

你的链路：

```text
Markdown

↓

Chunk

↓

Embedding

↓

Milvus
```

---

# Step4：Spring Boot接入RAG

依赖：

LangChain4j:

```xml
<dependency>

<groupId>
dev.langchain4j
</groupId>

<artifactId>
langchain4j-easy-rag
</artifactId>

</dependency>
```

---

创建：

Embedding模型：

```java
@Bean
EmbeddingModel embeddingModel(){

return new OllamaEmbeddingModel(
    "nomic-embed-text"
);

}
```

---

向量库：

```java
@Bean
EmbeddingStore store(){

return new MilvusEmbeddingStore();

}
```

---

# Step5：检索

用户：

```text
HashMap为什么线程不安全？
```

流程：

```text
问题

↓

Embedding

↓

向量搜索

↓

Milvus

↓

返回Top K文档
```

例如：

返回：

```
hashmap.md

concurrenthashmap.md
```

---

# Step6：组合 Prompt

最终发送给模型：

不是：

```text
HashMap为什么线程不安全？
```

而是：

```text
你是一名Java高级面试官。


参考资料：

---
HashMap JDK8结构...
HashMap线程安全问题...
---


问题：

HashMap为什么线程不安全？


请按照：

1. 原理

2. 源码

3. 项目

4. 面试回答

输出。
```

---

# Step7：调用 LoRA模型

现在：

输入：

```text
Prompt
+
检索知识
```

进入：

```text
Qwen + Java LoRA
```

输出：

```text
标准面试回答
```

---

# 六、RAG + LoRA 分工总结

|能力|RAG|LoRA|
|---|---|---|
|公司知识|✅|❌|
|最新数据|✅|❌|
|项目文档|✅|❌|
|回答格式|❌|✅|
|语气风格|❌|✅|
|专业习惯|❌|✅|
|减少幻觉|✅|部分|

---

# 七、你的项目升级路线

现在：

## V1

```text
Qwen
+
LoRA

Java面试模型
```

---

升级：

## V2

```text
Qwen
+
LoRA
+
Milvus RAG
```

---

升级：

## V3

加入 Agent：

```text
Java Interview Agent


Tool:

- 查询知识库

- 分析简历

- 生成问题

- 评分

- 记录错题
```

---

# 八、今天你掌握的企业级认知

现在你已经理解：

```text
基础模型

↓

LoRA

改变模型行为


+

RAG

提供外部知识


+

Agent

调用工具完成任务


=

完整AI应用
```

这其实就是目前 Java AI 工程师岗位核心能力。

---

# 下一步 Day5

进入工程实现：

# Day5：Spring Boot + LangChain4j + Milvus 实现 RAG Pipeline

我们会实际写：

```
上传PDF

↓

解析

↓

Chunk

↓

Embedding

↓

Milvus

↓

Retriever

↓

Qwen LoRA

↓

回答
```

这会和你之前做的 **Java AI Knowledge Assistant** 完全融合。