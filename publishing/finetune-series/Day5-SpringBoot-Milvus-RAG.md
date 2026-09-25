# 大模型微调实战 Day5：Spring Boot + LangChain4j + Milvus 实现 RAG Pipeline

# Spring Boot + LangChain4j + Milvus 实现 RAG Pipeline

今天开始进入你最熟悉的领域：

> **Java 工程化落地。**

前面：

- Day1～Day3：你学会了模型微调
    
- Day4：理解 RAG + LoRA 架构
    

今天：

> 用 Spring Boot 把 RAG 真正跑起来。

最终目标：

实现：

**Java AI Interview Agent V3**

能力：

用户上传：

```text
Java面试笔记.md
项目文档.pdf
源码分析.md
```

然后：

```text
上传
 ↓
解析
 ↓
切片
 ↓
Embedding
 ↓
Milvus存储
 ↓
检索
 ↓
Qwen+LoRA回答
```

---

# 一、整体架构

今天实现：

```text
                 用户

                  |
                  ↓

            Spring Boot API


                  |
        +---------+----------+

        |                    |

        ↓                    ↓


 Document Loader        Chat API


 文档加载                问题回答


        |                    |

        ↓                    ↓


 Text Splitter          Retriever


        |                    |

        ↓                    ↓


 Embedding Model       Prompt


        |                    |

        ↓                    |


 Milvus Vector DB      Qwen LoRA


        |                    |

        +---------+----------+

                  |

                  ↓


              Answer
```

---

# 二、技术选型

## 后端

```text
Spring Boot 3
```

## AI框架

```text
LangChain4j
```

## 向量数据库

```text
Milvus
```

## Embedding模型

推荐：

你已经有：

```text
nomic-embed-text
```

Ollama运行：

```bash
ollama pull nomic-embed-text
```

## 大模型

你的：

```text
Qwen + Java LoRA
```

通过 Ollama 暴露。

---

# 三、创建 Spring Boot 项目

结构：

```text
java-ai-interview-agent

├── controller

├── service

├── rag

├── embedding

├── vector

├── llm

└── config
```

---

Maven：

加入：

```xml
<dependencies>


<!-- Spring Web -->

<dependency>

<groupId>
org.springframework.boot
</groupId>

<artifactId>
spring-boot-starter-web
</artifactId>

</dependency>



<!-- LangChain4j -->

<dependency>

<groupId>
dev.langchain4j
</groupId>

<artifactId>
langchain4j-spring-boot-starter
</artifactId>

</dependency>


<!-- Ollama -->

<dependency>

<groupId>
dev.langchain4j
</groupId>

<artifactId>
langchain4j-ollama-spring-boot-starter
</artifactId>

</dependency>


</dependencies>
```

---

# 四、启动 Ollama 模型

你的本地：

```bash
ollama list
```

应该：

```text
qwen3.5:9b

java-interviewer
nomic-embed-text
```

启动：

```bash
ollama serve
```

默认：

```text
http://localhost:11434
```

---

# 五、配置 LLM

application.yml

```yaml
langchain4j:

  ollama:

    chat-model:

      base-url:
        http://localhost:11434

      model-name:
        java-interviewer

      temperature:
        0.7
```

含义：

```text
Spring Boot

↓

LangChain4j

↓

Ollama

↓

java-interviewer
```

---

# 六、创建 Chat Service

接口：

```java
public interface InterviewAssistant {


    String chat(
        String question
    );

}
```

---

实现：

```java
@Service
public class InterviewService {


    private final ChatLanguageModel model;



    public InterviewService(
        ChatLanguageModel model
    ){

        this.model=model;

    }



    public String answer(String question){

        return model.generate(question);

    }

}
```

---

测试：

请求：

```http
GET

/chat?question=HashMap为什么线程不安全
```

返回：

```text
HashMap线程不安全原因...
```

说明：

Java已经调用模型。

---

# 七、加入 Embedding

现在：

用户上传：

```text
HashMap.md
```

需要变成向量。

流程：

```text
文本

↓

Embedding Model

↓

向量

↓

Milvus
```

---

创建：

```java
@Bean
EmbeddingModel embeddingModel(){

return OllamaEmbeddingModel.builder()

.baseUrl(
"http://localhost:11434"
)

.modelName(
"nomic-embed-text"
)

.build();

}
```

---

# 八、文本切片 Chunk

为什么切？

因为：

模型上下文有限。

例如：

100页PDF：

不能直接塞。

所以：

```text
PDF

↓

1000个Chunk

↓

每个500 token
```

---

代码：

```java
DocumentSplitter splitter =
DocumentSplitters.recursive(
500,
100
);
```

含义：

```text
chunk size:

500


overlap:

100
```

---

# 九、创建 Milvus Vector Store

你的环境：

之前已经安装：

```text
milvus-lite
```

---

配置：

```java
@Bean
EmbeddingStore<TextSegment> store(){

return MilvusEmbeddingStore.builder()

.host("localhost")

.port(19530)

.collectionName(
"java_knowledge"
)

.build();

}
```

---

数据流：

```text
Java知识

↓

Embedding

↓

Milvus

保存：

[
0.123,
0.432,
...
]

+
原文本
```

---

# 十、实现文档导入

接口：

```java
@PostMapping("/upload")
public String upload(
MultipartFile file
){

ragService.ingest(file);

return "success";

}
```

---

流程：

```text
upload

↓

读取文件

↓

Document

↓

Chunk

↓

Embedding

↓

Milvus
```

---

# 十一、实现 Retrieval

用户：

```text
ConcurrentHashMap如何扩容？
```

执行：

```java
Embedding

↓

Milvus搜索

↓

Top K
```

例如返回：

```
concurrenthashmap.md

第30段

扩容迁移机制...
```

---

# 十二、组合 RAG Prompt

最终：

发送给模型：

```text
System:

你是Java高级面试官


参考资料:

-----
ConcurrentHashMap扩容采用多线程迁移...
-----


问题:

ConcurrentHashMap如何扩容？
```

---

模型：

```text
Qwen+LoRA
```

输出：

```text
面试回答：

JDK8 ConcurrentHashMap扩容...

第一...
第二...
第三...
```

---

# 十三、完整调用链（面试重点）

你以后面试可以这样回答：

> 用户提出问题后，Spring Boot 接收到请求，通过 LangChain4j 调用 Retriever，从 Milvus 向量数据库中检索相关知识片段，然后将检索结果和用户问题组装成 Prompt，发送给经过 LoRA 微调的 Qwen 模型，模型结合自身能力和外部知识生成最终答案。

链路：

```text
User

↓

Spring Boot

↓

LangChain4j

↓

Retriever

↓

Milvus

↓

Prompt Builder

↓

Qwen LoRA

↓

Answer
```

---

# 十四、今天完成标准

完成：

✅ Spring Boot启动

✅ Ollama调用

✅ Embedding配置

✅ Milvus接入

✅ 文档切片

✅ RAG链路理解

---

# 下一步 Day6

## Day6：实现完整 Agent

把你的系统升级：

从：

```text
RAG问答
```

变成：

```text
Java AI Interview Agent
```

加入：

Tools【工具】

- 查询知识库
    
- 分析简历
    
- 自动出题
    
- 自动评分
    
- 保存错题
    

架构：

```text
User

↓

Agent

↓

Decision

↓

Tool Calling

↓

RAG

↓

LLM

↓

Answer
```

这一步会把你之前学习的 **Tool Calling + MCP + Agent** 全部串起来。你现在这条路线已经接近一个完整 AI Engineer 项目闭环。