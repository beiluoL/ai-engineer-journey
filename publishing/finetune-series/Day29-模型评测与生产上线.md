# Day29：模型评测与生产上线

# Evaluation → Model Registry → vLLM → 灰度发布

前面 Day28：

你已经完成：

```text
GPU服务器

↓

CUDA

↓

PyTorch

↓

LLaMA-Factory

↓

Qwen

↓

QLoRA

↓

LoRA Adapter
```

现在进入企业真正落地阶段。

因为企业不会接受：

> “我训练了一个模型，看起来效果不错。”

企业关心：

1. **效果怎么样？**
    
2. **有没有变差？**
    
3. **怎么上线？**
    
4. **怎么回滚？**
    
5. **怎么监控？**
    

所以今天学习：

# Model Lifecycle【模型生命周期管理】

---

# 一、企业模型完整生命周期

一个模型从研发到上线：

```text

数据准备 Dataset

        ↓

训练 Training

        ↓

评测 Evaluation

        ↓

模型管理 Model Registry

        ↓

部署 Serving

        ↓

灰度发布 Canary Release

        ↓

监控 Monitoring

        ↓

持续优化 Improvement
```

---

# 二、为什么需要模型评测？

假设：

你训练了：

Java Interview Qwen。

训练前：

问题：

> HashMap为什么线程不安全？

回答：

70分。

---

微调后：

可能：

90分。

很好。

但是：

另一个问题：

> JVM G1垃圾回收流程？

可能：

下降。

---

所以：

不能只测试一个问题。

需要：

系统评估。

---

# 三、Evaluation是什么？

## Evaluation

中文：

评测。

作用：

判断：

模型质量。

---

包括：

## 1. 自动评测

机器评分。

## 2. 人工评测

专家评分。

## 3. 线上反馈

用户真实使用。

---

# 四、Golden Dataset【黄金测试集】

企业最重要。

什么是：

Golden Dataset？

中文：

黄金测试数据集。

---

简单：

一套固定标准题。

例如：

Java面试模型：

```json
[
{
"question":
"HashMap为什么线程不安全?",

"expected":
"数组+链表+红黑树，JDK8..."
},

{
"question":
"AQS是什么?",

"expected":
"同步器框架..."
}
]
```

---

每次模型升级：

重新测试。

---

流程：

```text

新模型

↓

回答1000道标准题

↓

自动评分

↓

比较旧模型

↓

决定是否上线
```

---

# 五、企业评测指标

## 1. Accuracy【准确率】

回答是否正确。

例如：

100题：

90正确。

90%。

---

## 2. Relevance【相关性】

回答是否相关。

例如：

问：

Java。

回答：

Python。

低。

---

## 3. Faithfulness【忠实性】

中文：

真实性。

RAG特别重要。

判断：

有没有胡编。

---

## 4. Latency【延迟】

响应速度。

例如：

P95：

2秒。

---

## 5. Cost【成本】

Token消耗。

---

# 六、RAG专项评测

企业知识库：

重点。

链路：

```text

问题

↓

Retriever

↓

召回文档

↓

LLM

↓

答案
```

---

需要评估：

---

## 1. Recall@K

召回率。

例如：

Top5：

有没有找到正确资料。

---

## 2. Precision

准确率。

召回：

10个。

真正有用：

8个。

80%。

---

## 3. Answer Quality

最终回答质量。

---

# 七、自动评测框架

常见：

## 1. RAGAS

用于：

RAG评测。

指标：

- Faithfulness
    
- Answer relevance
    
- Context precision
    

---

## 2. LangSmith

LangChain生态。

功能：

- Trace
    
- Evaluation
    
- Debug
    

---

## 3. OpenAI Evals

模型评测框架。

---

# 八、模型版本管理

企业不会：

覆盖模型。

例如：

现在：

v1。

训练新版本：

v2。

保存：

```text

qwen-java-v1


qwen-java-v2


qwen-java-v3
```

---

类似：

Git。

代码：

```text
commit

↓

version
```

模型：

```text
model version

↓

registry
```

---

# 九、Model Registry是什么？

中文：

模型仓库。

作用：

管理模型生命周期。

保存：

```text

模型文件

版本

训练数据

参数

评测结果

创建时间

负责人
```

---

常见工具：

## MLflow

非常流行。

架构：

```text

Training

↓

MLflow Tracking

↓

Model Registry

↓

Deployment
```

---

# 十、MLflow简单理解

类似：

GitHub + Maven仓库。

代码：

Git管理。

模型：

MLflow管理。

---

记录：

例如：

```json

{
model:

"java-qwen-v2",

accuracy:

0.92,

dataset:

"java-interview-v3",

creator:

"AI Team"

}
```

---

# 十一、模型部署到vLLM

训练：

得到：

LoRA。

生产：

需要：

模型服务。

---

流程：

```text

LoRA Adapter


↓

Merge


↓

完整模型


↓

vLLM


↓

OpenAI API


↓

业务系统
```

---

# 十二、Merge模型

为什么合并？

训练：

得到：

```text

adapter_model.safetensors
```

需要：

基础：

```text
Qwen

+

Adapter
```

生产方便：

合并：

```text
Qwen-Java-Finetuned
```

---

# 十三、vLLM部署

例如：

启动：

```bash
python -m vllm.entrypoints.openai.api_server \
--model ./java-qwen
```

启动后：

接口：

```http
POST

/v1/chat/completions
```

---

Spring Boot调用：

```text

用户

↓

Spring Boot

↓

vLLM API

↓

Java专家模型

↓

回答
```

---

# 十四、为什么企业不用直接替换模型？

因为风险。

例如：

旧模型：

很好。

新模型：

可能：

- 某些问题下降
    
- 速度慢
    
- 成本高
    

所以：

灰度发布。

---

# 十五、Canary Release【灰度发布】

中文：

金丝雀发布。

思想：

少量用户测试。

---

例如：

10000用户。

先：

```text

旧模型:

90%


新模型:

10%
```

---

观察：

- 成功率
    
- 用户反馈
    
- 延迟
    

满意：

扩大。

---

# 十六、模型路由

企业：

同时存在：

多个模型。

例如：

```text

                 请求


                  |

                  ↓


             Model Gateway


        +---------+---------+

        |                   |


    Qwen7B             Qwen72B


简单问题             复杂问题

```

---

规则：

简单：

小模型。

复杂：

大模型。

---

# 十七、A/B Testing【A/B测试】

比较：

两个模型。

例如：

A：

Qwen原版。

B：

Java微调版。

---

指标：

- 用户评分
    
- 完成率
    
- Token成本
    

---

# 十八、生产监控

上线以后：

必须监控。

---

## 系统层

Prometheus。

监控：

- CPU
    
- GPU
    
- 内存
    
- 网络
    

---

## 模型层

监控：

- 请求数量
    
- Token
    
- 延迟
    
- 错误率
    

---

## 业务层

例如：

客服：

- 问题解决率
    
- 转人工率
    

---

# 十九、完整企业模型上线架构

```text

              用户


                |

                ↓


          API Gateway


                |

                ↓


          AI Gateway


                |

        +-------+-------+

        |               |


      vLLM-v1        vLLM-v2


        |               |


    旧模型          新模型


        |

        ↓


      GPU Cluster

```

---

# 二十、结合你的 Java AI 项目

你的：

AI Interview Agent。

生产升级：

## 模型版本：

```text

java-interview-qwen-v1

↓

java-interview-qwen-v2

↓

java-interview-qwen-v3
```

---

## 测试集：

1000题。

分类：

```text
Java基础

并发

JVM

Spring

AI

RAG

Agent
```

---

## 上线：

```text

v1:

90%


v2:

10%
```

---

# 二十一、面试回答

## Q1：

> 微调后的模型如何上线？

标准回答：

> 微调完成后不会直接上线，需要先通过Golden Dataset进行评测，验证效果和性能。然后通过Model Registry管理版本，将模型部署到vLLM推理服务，通过灰度发布观察线上指标，确认稳定后逐步扩大流量。

---

## Q2：

> 如何判断一个RAG系统效果好？

回答：

> 我会从检索和生成两个阶段评估。检索阶段关注Recall、Precision和Context相关性，生成阶段关注答案准确性、忠实性和用户反馈，同时通过Golden Dataset持续回归测试。

---

## Q3：

> 为什么需要模型版本管理？

回答：

> 企业模型会持续迭代，不同版本可能影响效果、成本和稳定性，因此需要类似代码版本管理的机制记录模型、数据、参数和评测结果，支持回滚和持续优化。

---

# 二十二、Day29知识地图

现在完整掌握：

```text

数据

↓

训练

↓

微调

↓

评测

↓

模型仓库

↓

部署

↓

灰度

↓

监控

↓

迭代
```

---

# 二十三、Day29之后你的能力等级

你已经从：

```text
Java开发者

↓

调用AI API
```

升级到：

```text
Java AI Engineer

+

LLM Application Engineer

+

Model Deployment Engineer

+

MLOps Engineer
```

---

# 下一节 Day30（阶段总结）

建议进入：

# 《Day30：Java AI Engineer 完整能力闭环：从模型 → 应用 → 平台 → 企业架构》

总结：

你这30天形成：

```text
Java

↓

LLM

↓

RAG

↓

Agent

↓

模型部署

↓

微调

↓

MLOps

↓

企业AI平台
```

并且会输出：

1. AI工程师技能树
    
2. 简历项目包装
    
3. 面试100问
    
4. 未来6个月成长路线
    
5. 从Java转AI Engineer求职路线
    

完成：

> 从 Java 后端工程师 → Java AI 应用工程师 的完整升级路线。