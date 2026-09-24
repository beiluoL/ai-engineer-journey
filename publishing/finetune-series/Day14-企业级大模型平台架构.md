# Day14 企业级大模型平台架构

# 从单模型到 AI Platform：LLM Gateway、多模型路由、成本控制、自动扩缩容

前面 Day1～Day13，你已经完成了一条完整链路：

```text
 id="2w1a6b"
模型选择
 ↓
模型下载
 ↓
GPU部署
 ↓
vLLM推理服务
 ↓
Spring Boot调用
 ↓
RAG
 ↓
Agent
 ↓
LoRA微调
 ↓
模型上线
```

但是企业真实环境还有一个问题：

> 一个模型服务不够。

为什么？

因为企业不会只有：

```text
 id="w6z8vw"
用户

↓

Qwen

↓

回答
```

真实情况：

```text
 id="n8h5do"
                 用户

                  |

                  ↓

             AI Gateway

                  |

      +-----------+------------+

      |           |            |

      ↓           ↓            ↓


    Qwen       DeepSeek       GPT


   私有模型     推理模型       商业模型

```

今天学习：

> 如何设计一个企业级 LLM Platform【大语言模型平台】。

---

# 一、为什么需要 LLM Gateway？

## 先看没有 Gateway 的问题

你的系统：

```text
 id="5f7rj8"
Spring Boot

      |

      ↓

Qwen vLLM
```

假设：

用户增加：

100人

1000人

10000人

问题：

---

## 1. 模型压力

Qwen GPU：

只能处理：

100请求/s

超过：

怎么办？

---

## 2. 成本问题

不同任务：

需求不同。

例如：

简单：

> 总结一句话

不需要：

70B模型。

---

复杂：

> 分析代码架构

需要强模型。

---

## 3. 模型切换

今天：

Qwen

明天：

DeepSeek

后天：

GPT

业务代码：

不能全部修改。

---

所以：

增加：

# LLM Gateway

---

# 二、LLM Gateway是什么？

简单理解：

> AI世界的 API Gateway。

传统：

```text
 id="6u3xk5"
用户

↓

Nginx

↓

服务
```

AI：

```text
 id="i4u7k8"
用户

↓

LLM Gateway

↓

模型
```

---

它负责：

- 模型路由
    
- 鉴权
    
- 限流
    
- 成本控制
    
- 日志
    
- 监控
    
- 失败转移
    

---

# 三、企业 AI 架构

最终：

```text
 id="8t1u0w"
                           用户

                            |

                            ↓


                     API Gateway


                            |

                            ↓


                    LLM Gateway


                            |

        +-------------------+-------------------+

        |                   |                   |


        ↓                   ↓                   ↓


     Qwen                DeepSeek              GPT


    vLLM                 API                  API


        |                   |                   |

        +-------------------+-------------------+

                            |

                            ↓


                     Spring Boot Agent


                            |

                            ↓


                        用户结果
```

---

# 四、LLM Gateway核心能力

---

# 1. Model Routing【模型路由】

核心：

> 根据请求选择模型。

例如：

用户：

```text
解释HashMap
```

路由：

```text
 id="s4y2tj"
简单知识问答

↓

Qwen7B
```

---

用户：

```text
分析百万行代码
```

路由：

```text
 id="f8x8jm"
复杂任务

↓

DeepSeek-R1
```

---

# 五、模型路由策略

企业常见：

---

## 策略1：规则路由

最简单。

例如：

```java
if(question.length()<100){

 model="qwen7b";

}else{

 model="deepseek";

}
```

---

## 策略2：分类模型

增加：

Intent Classifier【意图分类器】

流程：

```text
 id="w2x1gt"
用户问题

↓

分类模型

↓

判断类型


技术问题

代码生成

总结

复杂推理

↓

选择模型
```

---

## 策略3：LLM Router

让模型自己判断。

例如：

System:

```
你负责选择最佳模型
```

输出：

```json
{
"model":"deepseek-r1",
"reason":"复杂推理"
}
```

---

# 六、你的 Java AI Interview Agent 路由设计

你的场景：

不同任务：

---

## 面试聊天

模型：

```text
Qwen2.5-7B
```

原因：

快。

---

## 代码分析

模型：

```text
DeepSeek-Coder
```

---

## 复杂技术方案设计

模型：

```text
DeepSeek-R1
```

---

## 图片理解

模型：

```text
Qwen-VL
```

---

架构：

```text
 id="z4aq0t"
用户

↓

Agent Router

↓

判断任务


        |

 +------+------+


 |             |


面试        代码分析


 |             |


Qwen        DeepSeek

```

---

# 七、OpenAI兼容接口设计

企业喜欢统一接口。

例如：

所有模型：

统一：

```
POST /v1/chat/completions
```

请求：

```json
{
"model":"java-interviewer",

"messages":[

{
"role":"user",

"content":"解释HashMap"
}

]
}
```

Gateway：

内部转换：

```text
 id="7t2g5n"
java-interviewer

↓

Qwen vLLM
```

---

# 八、成本控制

这是企业非常关注的。

因为：

大模型费用最高。

---

# 1. Token统计

每次请求：

记录：

```json
{
"user":"10001",

"model":"qwen",

"input_tokens":1200,

"output_tokens":500,

"cost":0.02
}
```

---

# 2. Token预算

例如：

普通用户：

每天：

100万Token。

超过：

限制。

---

# 3. Prompt压缩

例如：

原：

10000 Token

优化：

3000 Token。

方法：

- 删除历史无用聊天
    
- Chunk优化
    
- 摘要Memory
    

---

# 4. 缓存

相同问题：

不要重复调用。

例如：

用户：

```text
HashMap为什么线程不安全？
```

第一次：

调用模型。

保存：

Redis。

第二次：

直接返回。

---

架构：

```text
 id="0cc4eg"
用户

↓

Redis Cache

↓

存在?

↓

返回

↓

不存在

↓

LLM
```

---

# 九、自动扩缩容

企业最大问题：

流量变化。

例如：

白天：

1000用户。

晚上：

10用户。

不能：

一直开10张GPU。

---

解决：

Auto Scaling【自动扩缩容】。

---

架构：

```text
 id="6k5m3s"
用户增加

↓

请求增加

↓

GPU利用率80%

↓

Kubernetes扩容

↓

增加vLLM实例
```

---

# 十、Kubernetes部署

企业：

不用单机Docker。

使用：

K8s。

结构：

```text
 id="s7ukmc"
Kubernetes Cluster


        |

        |

+-------+-------+

|               |


vLLM Pod1     vLLM Pod2


GPU             GPU

```

---

# 十一、vLLM多实例部署

例如：

3个GPU：

```text
 id="n2l1xy"
GPU1

vLLM-Qwen


GPU2

vLLM-Qwen


GPU3

vLLM-Qwen
```

前面：

Load Balancer。

---

# 十二、健康检查

不能：

服务挂了还发送请求。

增加：

Health Check。

例如：

```
GET /health
```

返回：

```json
{
"status":"UP"
}
```

---

# 十三、失败降级

例如：

Qwen挂了。

自动：

```text
 id="58v8wb"
Qwen

↓

DeepSeek API

↓

GPT API
```

---

# 十四、模型版本管理

企业：

不能直接覆盖。

例如：

```text
 id="jzq7fo"
models/


qwen-java-v1


qwen-java-v2


qwen-java-v3
```

---

记录：

```json
{
"version":"v2",

"dataset":"java-interview-2026-09",

"lora_rank":16,

"score":92
}
```

---

# 十五、A/B测试

新模型上线：

不能全部切换。

例如：

```text
 id="y8g2cr"
用户

100%

↓

Gateway


90%

v1


10%

v2
```

比较：

- 回答质量
    
- 延迟
    
- 成本
    

---

# 十六、你的 Java AI 项目升级

现在：

V5：

```text
 id="1j9p7c"
Spring Boot

+

LangChain4j

+

Qwen LoRA

+

Milvus
```

升级：

V6：

```text
 id="c6p3u8"
Java AI Platform


Spring Boot

+

LLM Gateway

+

Model Router

+

vLLM Cluster

+

RAG

+

Agent

+

Evaluation

+

Monitoring
```

---

# 十七、面试回答

面试官：

> 如果用户量增加100倍，你的AI系统如何扩展？

标准回答：

> 我会将模型服务和业务服务解耦，通过 LLM Gateway 统一管理模型调用。推理层使用 vLLM 提供高性能服务，通过 Kubernetes 部署多个模型实例，根据GPU利用率和请求量进行自动扩缩容。同时增加缓存、Token统计、限流和模型路由，根据任务复杂度选择不同模型，降低成本并提升系统稳定性。

---

# 十八、现在你的 AI 工程能力地图

已经达到：

```text
             AI Application Engineer


                    |

        +-----------+------------+

        |                        |


    应用开发                  模型工程


        |                        |


 Spring Boot              QLoRA


 LangChain4j             LLaMA-Factory


 RAG                     vLLM


 Agent                   GPU部署


 Tool Calling            模型优化


        |

        ↓


 企业AI平台设计
```

---

# 下一节 Day15

建议进入：

# 《Day15：企业级 RAG 深度优化：Hybrid Search + Rerank + Agentic RAG + Evaluation》

因为真实企业项目中：

> 80%的 RAG 项目效果不好，不是模型问题，而是检索系统问题。

下一节会做：

```text
普通RAG

↓

Hybrid Search
关键词 + 向量

↓

Rerank

↓

Agentic RAG

↓

自动评测

↓

生产级知识库
```

这部分是目前 Java AI 岗位面试非常高频的内容。