# 第一次微调实战 Day6

# 实现完整 Agent：RAG + LoRA + Tool Calling

今天是整个项目的一个重要升级。

前面：

- Day1～Day3：你完成了 **模型微调**
    
- Day4：理解 **RAG + LoRA**
    
- Day5：实现 **Spring Boot + LangChain4j + Milvus RAG Pipeline**
    

但是现在你的系统还是：

```text
用户问题

↓

RAG检索

↓

LLM回答
```

这叫：

> RAG Application【RAG 应用】

还不是完整 Agent。

今天升级：

```text
用户

↓

Agent【智能体】

↓

判断任务

↓

选择工具

↓

调用工具

↓

获取结果

↓

LLM综合推理

↓

回答
```

---

# 一、什么是真正 Agent？

先理解：

## 普通 Chat

用户：

> HashMap为什么线程不安全？

流程：

```text
用户

↓

LLM

↓

回答
```

模型自己猜。

---

## Agent

用户：

> 根据我的简历，模拟一次 Java 高级面试，并指出我的不足。

流程：

```text
用户

↓

Agent

↓

分析需求

↓

需要哪些能力？

↓

调用工具：

1. 简历分析工具

2. 知识库搜索工具

3. 面试评分工具

↓

组合结果

↓

回答
```

---

# 二、你的 Java AI Interview Agent 设计

最终目标：

## Java AI Interview Agent V4

功能：

### 1. 面试模式

输入：

```
开始模拟Java高级面试
```

Agent：

调用：

```text
InterviewQuestionTool
```

生成问题。

---

### 2. 知识查询

输入：

```
解释ConcurrentHashMap扩容
```

Agent：

调用：

```text
KnowledgeSearchTool
```

查询 Milvus。

---

### 3. 简历分析

输入：

```
分析我的简历
```

Agent：

调用：

```text
ResumeAnalyzerTool
```

---

### 4. 面试评分

输入：

```
评价我的回答
```

Agent：

调用：

```text
AnswerScoreTool
```

---

# 三、整体架构

```text
                    User

                     |

                     ↓


              Spring Boot API


                     |

                     ↓


              Interview Agent


                     |

        +------------+-------------+

        |            |             |


        ↓            ↓             ↓


 Knowledge      Resume       Evaluation

 Tool            Tool          Tool


        |            |             |


        ↓            ↓             ↓


    Milvus       PDF解析       Score


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

# 四、核心：Tool Calling

你之前已经学习过。

这里真正落地。

核心思想：

> LLM 不直接执行 Java 方法，只决定调用哪个工具。

例如：

用户：

```
查询HashMap源码
```

LLM返回：

```json
{
 "tool":"searchKnowledge",
 "arguments":{
    "query":"HashMap源码"
 }
}
```

Java收到：

执行：

```java
searchKnowledge(
"HashMap源码"
)
```

返回：

```json
{
"result":
"HashMap JDK8采用数组+链表+红黑树"
}
```

再给LLM：

生成最终答案。

---

# 五、LangChain4j实现Agent

## 1. 引入 Agent 依赖

Maven：

```xml
<dependency>
    <groupId>dev.langchain4j</groupId>
    <artifactId>langchain4j</artifactId>
</dependency>
```

---

# 六、创建第一个 Tool

例如：

知识库搜索。

创建：

```java
@Component
public class KnowledgeTool {


    private final Retriever retriever;


    public KnowledgeTool(
        Retriever retriever
    ){
        this.retriever=retriever;
    }



    @Tool(
      "搜索Java技术知识库"
    )
    public String searchKnowledge(
        String query
    ){

        return retriever
            .findRelevant(query);

    }

}
```

---

注意：

这里：

```java
@Tool
```

非常关键。

它告诉：

LLM：

> 我有一个可以调用的能力。

---

# 七、创建 Agent Service

定义：

```java
public interface InterviewAgent {


    String chat(
        String message
    );

}
```

---

绑定：

```java
InterviewAgent agent =
AiServices.builder(
    InterviewAgent.class
)

.chatLanguageModel(model)

.tools(
    knowledgeTool
)

.build();
```

---

现在：

你的 Agent：

拥有：

```text
能力1：

回答问题


能力2：

搜索知识库
```

---

# 八、测试 Tool Calling

用户：

```
ConcurrentHashMap为什么线程安全？
```

Agent判断：

需要知识库。

调用：

```text
KnowledgeTool
```

获取：

```
ConcurrentHashMap源码资料
```

然后：

Qwen：

生成：

```
面试回答：
JDK8采用CAS+synchronized...
```

---

# 九、加入简历分析 Tool

创建：

```java
@Component
public class ResumeTool {


@Tool(
"分析Java工程师简历"
)
public String analyzeResume(
String resume
){

return "分析结果";

}

}
```

---

Agent拥有：

```text
Tools:

├── searchKnowledge()

├── analyzeResume()

└── scoreAnswer()
```

---

# 十、加入 MCP 思想

你之前学习 MCP：

**Model Context Protocol【模型上下文协议】**

本质：

标准化工具连接。

现在：

你的 Agent：

```text
Agent

 |

 MCP Server

 |

Tools

 |
 
├── Milvus

├── GitHub

├── 文件系统

└── 数据库
```

以后可以扩展：

查询：

GitHub源码

数据库

Jira

Notion

---

# 十一、加入 Memory【记忆】

现在：

每次聊天：

```text
问题

↓

回答

↓

结束
```

加入：

Conversation Memory【对话记忆】

保存：

```text
用户：

6年Java经验

薄弱：

AQS

喜欢：

源码分析
```

以后：

Agent知道：

```text
继续训练AQS
```

---

# 十二、最终 Agent 链路（面试话术）

面试官：

> 你如何设计一个 Java AI Agent？

回答：

> 我的设计采用 Spring Boot + LangChain4j 构建 Agent 服务。用户请求进入系统后，Agent 首先通过 LLM 判断当前任务是否需要调用工具。如果需要，例如查询技术知识，则通过 Tool Calling 调用知识库检索工具，从 Milvus 获取相关文档片段，然后将工具结果和上下文重新输入大模型，最终由经过 LoRA 微调的 Qwen 模型生成符合 Java 面试场景的回答。

链路：

```text
User

↓

Spring Boot

↓

LangChain4j Agent

↓

LLM决策

↓

Tool Calling

↓

Knowledge Tool

↓

Milvus

↓

Tool Result

↓

Qwen LoRA

↓

Answer
```

---

# 十三、今天你的项目能力

现在你的项目：

## Java AI Interview Agent V4

技术：

```text
Spring Boot

LangChain4j

Qwen

QLoRA

LoRA

RAG

Milvus

Embedding

Tool Calling

Agent

MCP

Ollama
```

已经覆盖：

企业 AI 应用开发核心链路。

---

# 下一步 Day7

## Day7：把 Agent 工程化

进入生产级：

### 增加：

1. Streaming SSE【流式输出】
    
2. 用户会话管理
    
3. Prompt管理
    
4. Agent日志
    
5. Tool权限控制
    
6. Token成本统计
    
7. Evaluation【评测系统】
    
8. Docker部署
    

最终形成：

> 一个可以放简历、面试演示、继续扩展的 Java AI Agent 项目。

下一节开始做：

**Day7：Spring Boot + LangChain4j Agent 生产级工程化。**