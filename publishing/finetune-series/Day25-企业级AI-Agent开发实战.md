# Day25：企业级 AI Agent 开发实战

# LangGraph / LangChain4j 构建可控 Agent

前面 Day24，你学习了 Agent 的高级能力：

```text
Agent

↓

Memory

↓

Planning

↓

Reflection

↓

Self-Improvement
```

但是企业真正开发时，面试官不会只问：

> “你知道 Agent 吗？”

而会问：

> “你怎么实现一个可控、可维护、可上线的 Agent？”

今天进入工程实现。

---

# 一、为什么需要 Agent Framework？

先看最简单实现。

自己写：

```java
while(true){

    response = llm.chat(prompt);


    if(response.needTool()){

        executeTool();

    }

}
```

Demo 可以。

企业不行。

问题：

---

## 1. 状态混乱

复杂任务：

```text

用户需求

↓

任务1

↓

任务2

↓

失败

↓

恢复
```

需要保存状态。

---

## 2. 流程不可控

LLM：

可能：

```text

调用工具A

↓

调用工具B

↓

无限循环
```

---

## 3. 无法观察

不知道：

为什么失败。

---

所以需要：

# Agent Framework【智能体框架】

---

# 二、目前主流 Agent 框架

## 1. LangGraph

定位：

> 用图(Graph)方式构建 Agent。

语言：

Python。

特点：

- 状态管理
    
- 节点编排
    
- 条件分支
    
- 循环
    
- Human Approval
    

---

## 2. LangChain4j

定位：

> Java生态的大模型应用框架。

适合：

Java开发者。

支持：

- ChatModel
    
- Tools
    
- Memory
    
- RAG
    
- Agent
    

---

你的路线：

Java + AI。

重点：

# LangChain4j

---

# 三、什么是 Graph Agent？

传统流程：

线性：

```text

A

↓

B

↓

C
```

---

Agent任务：

可能：

```text

        A

       / \

      B   C

       \ /

        D
```

---

Graph：

节点 + 边。

---

# 四、LangGraph思想

核心：

State Graph【状态图】。

一个Agent：

由：

## Node【节点】

执行任务。

## Edge【边】

决定下一步。

## State【状态】

保存上下文。

---

例如：

AI文章生成：

```text

Start


 ↓


Research Node


 ↓


Write Node


 ↓


Review Node


 ↓


Publish

```

---

# 五、企业 Agent 标准结构

```text

                 User


                  |

                  ↓


             Supervisor


                  |

        +---------+----------+

        |                    |


        ↓                    ↓


    Research              Writer


        |                    |


        +---------+----------+

                  |

                  ↓


             Reviewer


                  |

                  ↓


               Result
```

---

# 六、使用 LangChain4j 创建第一个 Agent

项目：

Spring Boot 3。

依赖：

Maven：

```xml
id="1m8xq5"
<dependency>

    <groupId>
    dev.langchain4j
    </groupId>

    <artifactId>
    langchain4j-spring-boot-starter
    </artifactId>

</dependency>
```

---

# 七、配置模型

application.yml

```yaml
id="q4k9s2"
langchain4j:

 open-ai:

  chat-model:

   base-url:
    http://localhost:11434/v1


   model-name:
    qwen2.5:7b


   api-key:
    none
```

---

这里：

Spring Boot

↓

LangChain4j

↓

Ollama

↓

Qwen

---

# 八、第一个 AI Service

创建：

```java
id="x8m2q6"
public interface InterviewAssistant {


String chat(String message);


}
```

---

绑定：

```java
id="p7n4k1"
@AiService


public interface InterviewAssistant{


String chat(String message);


}
```

---

调用：

```java
id="k5q8m3"
assistant.chat(
"解释ConcurrentHashMap"
);
```

---

现在：

Java调用LLM。

---

# 九、加入 Tool Calling

Agent核心：

不是聊天。

是：

调用工具。

---

例如：

查询用户能力。

创建：

```java
id="r9x3m7"
public class UserTool {


@Tool("查询用户技术能力")


public String querySkill(
String userId
){

return "Java 80分";

}


}
```

---

注册：

```java
id="z4m8q2"
AiServices.builder()

.chatModel(model)

.tools(new UserTool())

.build();
```

---

调用链：

```text

用户

↓

Agent

↓

LLM判断需要工具

↓

Tool Call

↓

Java方法

↓

Tool Result

↓

LLM生成答案
```

---

# 十、Agent State设计

企业Agent必须保存状态。

例如：

任务：

生成技术报告。

State：

```java
id="c7m2q9"
public class AgentState {


String taskId;


String goal;


List<String> steps;


String currentStep;


String result;


}
```

---

状态变化：

```text

INIT


 ↓


RESEARCHING


 ↓


WRITING


 ↓


REVIEWING


 ↓


DONE
```

---

# 十一、Workflow Agent实现

例如：

面试训练。

流程：

```text

Start


 ↓


GenerateQuestion


 ↓


UserAnswer


 ↓


Evaluate


 ↓


SaveMemory


 ↓


GeneratePlan


 ↓


End
```

---

不要：

让LLM自己决定全部。

---

# 十二、Reflection Agent实现

设计两个Agent。

---

## Generator

生成答案。

---

## Critic

检查。

---

流程：

```text

Question


↓

Generator


↓

Answer


↓

Critic


↓

Score


↓

Improve?

```

---

Java：

```java
id="t3m7q9"
critic.evaluate(answer);
```

---

# 十三、Memory实现

## 短期记忆

Redis。

保存：

```json
id="v9k2m5"
{
sessionId:"1001",

messages:[]
}
```

---

## 长期记忆

Milvus。

保存：

```text
用户历史回答

薄弱点

学习记录
```

---

查询：

```text
用户今天练习AQS

↓

搜索历史

↓

生成个性化问题
```

---

# 十四、MCP接入

企业：

Agent：

不要直接连接系统。

结构：

```text

LangChain4j Agent


        |

        ↓


      MCP Client


        |

        ↓


      MCP Server


        |

        ↓


 CRM / ERP / DB
```

---

# 十五、一个企业级 Agent 项目结构

你的项目：

AI Interview Platform

升级：

```
ai-agent-platform


├── agent-core

│
├── state

│
├── workflow

│
├── memory

│
├── tools

│
├── mcp

│
├── rag

│
├── evaluation

│
└── monitoring
```

---

# 十六、Agent可观测性

企业必须知道：

Agent为什么这么做。

记录：

```json
id="j7q4m9"
{

taskId:"001",


steps:[

"search knowledge",

"call evaluator",

"generate answer"

],


toolCalls:2,


cost:0.03

}
```

---

# 十七、Agent失败处理

必须设计：

---

## Timeout

工具超过：

5秒。

停止。

---

## Retry

失败：

重新调用。

---

## Fallback

模型A失败：

↓

模型B。

---

## Human Approval

危险操作：

人工确认。

---

# 十八、面试回答

## Q1：

> 为什么企业Agent需要Workflow？

标准回答：

> Agent负责理解目标和动态决策，但是企业业务流程需要稳定和可控，因此通常使用Agent进行任务规划，Workflow负责关键流程编排，通过状态管理保证可追踪和可恢复。

---

## Q2：

> LangGraph和LangChain4j有什么区别？

回答：

> LangGraph更偏向通过状态图方式构建复杂Agent流程，适合Python生态；LangChain4j针对Java生态，方便Java开发者集成LLM、RAG和Tool Calling。在企业Java项目中，我会优先使用LangChain4j。

---

## Q3：

> 如何避免Agent无限循环？

回答：

> 通过限制最大执行步骤、保存Agent状态、增加工具调用次数限制，并结合Workflow控制关键路径，同时通过监控记录Agent执行轨迹。

---

# 十九、Day25能力升级

你的能力：

从：

```text
会调用LLM
```

升级：

```text

设计Agent

↓

开发Agent

↓

管理Agent状态

↓

控制Agent流程

↓

上线Agent系统
```

---

# 二十、下一节 Day26

建议进入：

# 《Day26：企业级 AI Agent 平台实战：搭建你的 Multi-Agent + MCP + RAG 项目》

下一节开始真正组合：

```text

Spring Boot

+

LangChain4j

+

Multi-Agent

+

Memory

+

Workflow

+

MCP

+

RAG

+

Milvus

+

vLLM
```

完成一个：

**企业数字员工级 Agent 平台。**

这会接近真实：

- AI Agent Engineer
    
- Java AI Engineer
    
- LLM Application Engineer
    

岗位要求。