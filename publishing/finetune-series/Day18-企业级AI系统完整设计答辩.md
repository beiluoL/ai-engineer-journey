# Day18 企业级 AI 系统完整设计答辩

# 从需求分析 → 架构设计 → 技术选型 → 上线运维

前面 Day1～Day17，你已经学习了：

```text
 id="9t2q5a"
大模型基础

↓

模型部署

↓

vLLM

↓

RAG

↓

Agent

↓

Tool Calling

↓

LoRA/QLoRA

↓

安全

↓

MLOps
```

但是企业面试最后考察的是：

> **你能不能从 0 设计一个完整 AI 产品。**

今天模拟：

你作为：

> AI 应用架构工程师

设计一个企业级 AI 系统。

---

# 一、真实面试题

面试官：

> 公司准备建设一个内部 AI 助手平台，支持员工查询公司知识、生成报告、分析代码、自动处理业务流程。用户规模预计 10 万人，请你设计整体架构。

---

很多初级回答：

❌

> 用 ChatGPT API，然后接一个知识库。

这个不够。

高级回答需要：

```text
需求分析

↓

整体架构

↓

技术选型

↓

核心链路

↓

稳定性

↓

安全

↓

成本

↓

运维
```

---

# 二、第一步：需求分析

不要直接选技术。

先分析业务。

---

## 业务目标

建设：

# Enterprise AI Assistant【企业智能助手】

能力：

### 1. 企业知识问答

例如：

员工：

> 公司报销流程是什么？

系统：

查询：

- 制度文档
    
- HR文档
    
- 技术文档
    

---

### 2. 智能办公

例如：

生成：

- 周报
    
- 总结
    
- 方案
    

---

### 3. 代码助手

例如：

开发：

> 解释这个Spring代码。

---

### 4. Agent自动处理

例如：

用户：

> 帮我创建一个项目申请。

Agent：

调用：

- OA系统
    
- 邮件系统
    
- 数据库
    

---

# 三、非功能需求

企业一定关注：

---

## 1. 性能

例如：

10万用户。

同时在线：

5000。

---

## 2. 延迟

目标：

普通问答：

<3秒。

复杂Agent：

<10秒。

---

## 3. 安全

要求：

- 权限隔离
    
- 数据不泄露
    
- 操作审计
    

---

## 4. 成本

不能：

每次调用GPT。

---

# 四、整体架构设计

最终架构：

```text
                         用户

                          |

                          ↓


                    Web / App


                          |

                          ↓


                  API Gateway


                          |

                          ↓


                AI Application Layer


                          |

        +-----------------+----------------+

        |                 |                |


        ↓                 ↓                ↓


      Chat             Agent           Workflow


        |                 |                |


        +-----------------+----------------+

                          |

                          ↓


                  LLM Gateway


                          |

        +-----------------+----------------+

        |                 |                |


        ↓                 ↓                ↓


      Qwen             DeepSeek          GPT


     vLLM                API             API


                          |

                          ↓


                    Model Layer


```

---

# 五、AI应用层设计

## 1. Chat Service

普通问答。

流程：

```text
用户问题

↓

LLM

↓

回答
```

---

## 2. RAG Service

企业知识。

流程：

```text
文档

↓

解析

↓

Chunk

↓

Embedding

↓

Vector DB

↓

Retriever

↓

LLM
```

---

## 3. Agent Service

复杂任务。

例如：

查询：

订单状态。

流程：

```text
用户

↓

Agent

↓

Tool选择

↓

调用ERP

↓

返回结果
```

---

# 六、模型层设计

企业不会只有一个模型。

设计：

## 通用模型

例如：

Qwen2.5-72B

处理：

复杂任务。

---

## 小模型

例如：

Qwen2.5-7B

处理：

简单问答。

---

## 专业模型

例如：

代码模型：

DeepSeek-Coder。

---

# 七、LLM Gateway设计

核心：

统一入口。

接口：

```http
POST /v1/chat/completions
```

请求：

```json
{
"model":
"enterprise-ai",

"messages":[...]

}
```

Gateway决定：

调用：

哪个模型。

---

# 八、模型路由策略

## 简单问题

例如：

> 公司假期多少天？

选择：

```text
Qwen7B
```

---

## 复杂推理

例如：

> 分析年度经营数据。

选择：

```text
DeepSeek-R1
```

---

## 代码分析

选择：

```text
Code Model
```

---

# 九、知识库架构

企业文档：

来源：

```text
PDF

Word

Wiki

Git

数据库
```

---

处理：

```text
Document Loader

↓

Chunk

↓

Embedding

↓

Vector DB

```

---

数据库选择：

## 向量数据库

Milvus。

---

## 关键词搜索

Elasticsearch。

---

最终：

Hybrid Search。

---

# 十、Agent设计

Agent不要直接操作数据库。

中间：

Tool层。

例如：

```text
Agent

↓

Tool Router

↓

Tools


├── 查询订单

├── 查询员工

├── 创建审批

└── 查询库存
```

---

# 十一、权限设计

企业核心。

例如：

员工A：

只能：

查询自己部门。

员工B：

管理员权限。

---

设计：

```text
User

↓

Identity Service

↓

Permission

↓

Tool

↓

Data Filter
```

---

# 十二、数据安全设计

## 数据隔离

多租户：

```text
tenant_id

department_id

user_id
```

---

## 数据脱敏

例如：

身份证：

```text
430123199xxxxxxx
```

变：

```text
430********123
```

---

# 十三、部署架构

生产：

Kubernetes。

```text
                 Kubernetes


                     |

        +------------+-------------+

        |                          |


    AI Service Pods          Model Pods


        |                          |


    Spring Boot              vLLM


                              |

                              ↓


                             GPU

```

---

# 十四、GPU资源规划

假设：

10万用户。

不是：

10万个模型。

---

采用：

共享模型。

例如：

GPU集群：

```text
A100 x 8

↓

vLLM Cluster

↓

负载均衡
```

---

# 十五、性能优化

## 1. KV Cache

vLLM：

减少重复计算。

---

## 2. Continuous Batching

多个请求一起计算。

---

## 3. Prompt Cache

重复Prompt复用。

---

## 4. 小模型路由

简单任务不用大模型。

---

# 十六、监控体系

三层：

---

## 应用监控

Spring Boot：

- QPS
    
- 延迟
    
- 错误
    

---

## AI监控

模型：

- Token
    
- Cost
    
- Quality
    

---

## GPU监控

GPU：

- 显存
    
- 利用率
    
- 温度
    

---

工具：

- Prometheus
    
- Grafana
    

---

# 十七、上线流程

企业流程：

```text
开发环境

↓

测试环境

↓

灰度环境

↓

生产环境

↓

监控

↓

优化
```

---

# 十八、模型迭代

流程：

```text
用户反馈

↓

新增数据

↓

Evaluation

↓

LoRA训练

↓

模型版本

↓

灰度

↓

上线
```

---

# 十九、成本控制设计

企业最关心。

措施：

---

## 1. 模型分级

简单：

7B。

复杂：

70B。

---

## 2. Cache

重复问题：

Redis。

---

## 3. Token限制

控制：

最大输出。

---

## 4. RAG优化

减少Prompt长度。

---

# 二十、完整面试回答

面试官：

> 请设计一个企业级大模型应用平台。

你的回答：

> 我会将系统拆分为应用层、模型服务层和基础设施层。应用层基于Spring Boot和LangChain4j实现Chat、RAG和Agent能力；知识场景采用RAG架构，通过文档解析、Chunk、Embedding和向量数据库实现企业知识增强；复杂业务通过Agent结合Tool Calling调用内部系统。模型层通过LLM Gateway统一管理多个模型，根据任务类型进行路由。部署层使用Kubernetes管理服务，通过vLLM提供高性能推理，并结合GPU监控、模型评测、灰度发布和MLOps流程保证系统稳定迭代。

---

# 二十一、你的能力升级

完成 Day18 后，你已经形成：

```text
Java后端能力

        +

AI应用能力

        +

模型部署能力

        +

Agent能力

        +

MLOps能力

        +

系统架构能力

=

AI Application Engineer
```

---

# 下一阶段 Day19

建议进入：

# 《Day19：从 AI 工程师到 AI 产品工程师：设计、开发、上线一个完整 AI SaaS》

目标：

把技术能力转成：

- 可商业化产品
    
- 用户需求分析
    
- SaaS架构
    
- 收费模式
    
- MVP开发路线
    

因为对于你现在的背景（6年 Java + AI 转型），除了求职，也可以探索：

> AI工具产品 / 独立开发 / 创业验证。