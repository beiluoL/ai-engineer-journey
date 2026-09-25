# 大模型微调实战 Day7：Spring Boot + LangChain4j Agent 生产级工程化

# Spring Boot + LangChain4j Agent 生产级工程化

前 6 天我们完成了：

```text
Day1
Google Colab + LLaMA-Factory + 数据准备

↓

Day2
QLoRA 微调 Qwen

↓

Day3
LoRA模型部署到 Ollama + Spring Boot

↓

Day4
RAG + LoRA 架构

↓

Day5
Spring Boot + LangChain4j + Milvus RAG

↓

Day6
Agent + Tool Calling
```

现在你的系统：

已经能工作。

但是距离企业项目还有差距。

企业关注：

> 稳定性、可观测性、成本、安全、评测。

今天升级：

# Java AI Interview Agent V5（生产级）

---

# 一、生产级 Agent 架构

从：

```text
用户

↓

Agent

↓

LLM

↓

回答
```

升级：

```text
 id="y3p0d5"
                         用户

                          |

                          ↓


                    API Gateway


                          |

                          ↓


                 Spring Boot Agent


                          |

          +---------------+---------------+

          |               |               |


          ↓               ↓               ↓


       Memory          Tool           RAG


       Redis        Tool Router      Milvus


          |               |               |

          +---------------+---------------+

                          |

                          ↓


                 LLM Gateway


                          |

                          ↓


                  Qwen + LoRA


                          |

                          ↓


                       SSE输出

```

---

# 二、第一步：Streaming SSE 流式输出

## 为什么需要 SSE？

普通接口：

请求：

```text
 id="y1yb9r"
用户问题

↓

等待30秒

↓

一次返回答案
```

体验差。

ChatGPT：

为什么感觉快？

因为：

Token一个个输出。

---

## SSE

全称：

**Server-Sent Events【服务器发送事件】**

流程：

```text
用户

↓

Spring Boot

↓

LLM生成Token

↓

马上推送

↓

浏览器显示
```

---

# 三、Spring Boot SSE实现

Controller：

```java
@RestController
@RequestMapping("/chat")
public class ChatController {


@GetMapping(
produces =
MediaType.TEXT_EVENT_STREAM_VALUE
)
public Flux<String> chat(
String message
){


return agent.stream(message);


}


}
```

---

返回：

```text
data: ConcurrentHashMap

data: JDK8

data: 使用CAS

data: + synchronized
```

---

# 四、第二步：Conversation Memory【对话记忆】

现在：

用户：

第一次：

```
我叫张三
```

第二次：

```
我的技术栈是什么？
```

模型不知道。

需要 Memory。

---

架构：

```text
用户

↓

ConversationId

↓

Redis

↓

ChatMemory

↓

LLM
```

---

# 五、Redis保存聊天记录

Redis：

保存：

```json
{
"user":"10001",

"messages":[

"我是Java工程师",

"我学习Agent"

]

}
```

---

LangChain4j：

```java
@Bean
ChatMemory chatMemory(){


return MessageWindowChatMemory
.builder()

.maxMessages(20)

.build();

}
```

---

效果：

Agent知道：

```
用户：

6年Java

正在转AI

需要面试训练
```

---

# 六、第三步：Prompt工程化

之前：

Prompt写代码里：

```java
"你是Java面试官"
```

生产：

应该独立。

目录：

```
prompts/

├── interview-system.txt

├── rag-answer.txt

├── resume-analysis.txt

└── evaluation.txt
```

---

例如：

interview-system.txt

```
你是一名高级Java面试官。

回答规则：

1. 先给结论

2. 再解释原理

3. 给源码

4. 给项目场景

5. 最后给30秒面试话术
```

---

好处：

不用重新发版。

---

# 七、第四步：Tool权限控制

现在：

Agent：

可以调用：

```
searchKnowledge()

analyzeResume()
```

但是生产：

不能无限制。

例如：

普通用户：

允许：

```
知识搜索
```

管理员：

允许：

```
上传知识库
删除数据
```

---

设计：

```text
User

↓

Permission Service

↓

Tool Router

↓

Tool
```

---

代码：

```java
@Tool(
"搜索知识库"
)
@Permission(
"USER"
)
public String search(){

}
```

---

# 八、第五步：Agent日志

AI系统最大问题：

不知道为什么回答。

需要记录：

## Trace【链路追踪】

例如：

一次请求：

```json
{
"requestId":"abc123",

"userQuestion":
"ConcurrentHashMap扩容",

"agentPlan":
[
"searchKnowledge"
],

"tool":
"milvusSearch",

"tokens":
1200,

"time":
2300
}
```

---

可以使用：

- Micrometer
    
- Prometheus
    
- Grafana
    

---

# 九、第六步：Token成本统计

企业非常关注。

记录：

输入：

```text
prompt tokens
```

输出：

```text
completion tokens
```

例如：

```json
{
"inputTokens":1200,

"outputTokens":500,

"total":1700
}
```

用途：

控制成本。

---

# 十、第七步：Evaluation【评测系统】

这是很多 AI 项目缺少的。

不能：

"感觉效果不错"

需要测试。

---

建立：

Golden Dataset【黄金测试集】

例如：

```json
[
{
"question":
"HashMap扩容机制",

"expected":
[
"数组",
"链表",
"红黑树",
"resize"
]
}
]
```

---

自动评估：

指标：

## 1. Retrieval Accuracy【检索准确率】

RAG有没有找到正确文档。

## 2. Answer Quality【回答质量】

答案是否完整。

## 3. Hallucination【幻觉】

是否编造。

---

# 十一、第八步：异常处理

生产必须考虑：

## LLM超时

例如：

30秒没返回。

处理：

```text
Timeout

↓

Retry

↓

Fallback
```

---

## 模型不可用

例如：

Qwen挂了。

备用：

```text
Qwen

↓

DeepSeek

↓

GPT
```

---

# 十二、第九步：Docker部署

最终：

docker-compose:

```yaml
services:


springboot:

 image:
 java-agent


milvus:

 image:
 milvus


redis:

 image:
 redis


ollama:

 image:
 ollama
```

---

启动：

```bash
docker compose up
```

---

# 十三、最终项目架构

现在你的项目：

# Java AI Interview Agent

完整链路：

```text
 id="w0p5x4"
用户

↓

Vue3

↓

Spring Boot

↓

LangChain4j Agent

↓

Planner

↓

Tool Calling

├── Milvus RAG

├── Resume Analyzer

├── Evaluation Tool

└── Memory


↓

Prompt Assembly


↓

Qwen + LoRA


↓

SSE Streaming


↓

用户
```

---

# 十四、面试30秒回答

如果面试官问：

> 你做过 Agent 项目吗？

回答：

> 我实现过一个 Java AI Interview Agent，整体基于 Spring Boot 和 LangChain4j。系统通过 Agent 负责任务规划，通过 Tool Calling 调用知识库检索、简历分析和评分工具，RAG 使用 Milvus 存储企业知识文档，同时结合 QLoRA 微调 Qwen 模型，使模型具备 Java 面试场景下的回答风格。系统支持 SSE 流式输出、Redis 会话记忆、Prompt 管理以及评测和日志追踪。

---

# 十五、到这里你的 AI 工程能力地图

你已经覆盖：

```
基础模型
    ↓
Prompt Engineering
    ↓
Embedding
    ↓
RAG
    ↓
Vector Database
    ↓
Fine-tuning
    ↓
LoRA/QLoRA
    ↓
Tool Calling
    ↓
Agent
    ↓
MCP
    ↓
Production Engineering
```

这套能力已经不是“调用 API 做 Demo”，而是完整 **AI Application Engineer【AI 应用工程师】能力链路**。

---

下一阶段建议：

# Day8：把这个项目包装成真实求职项目

内容：

- 项目背景设计
    
- 架构图
    
- 简历描述
    
- 技术难点
    
- 面试100问
    
- 如何避免“微调模型”被面试官追问穿
    

因为对于你目前求职目标（Java + AI），**工程落地表达能力比继续堆技术更重要。**