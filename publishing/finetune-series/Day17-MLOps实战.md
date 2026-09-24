# Day17 MLOps 实战

# 模型版本管理、数据版本管理、自动训练 Pipeline、持续评测

前面 Day1～Day16，你已经完成：

```text
模型选择

↓

模型部署(vLLM)

↓

RAG

↓

Agent

↓

LoRA微调

↓

企业安全
```

但是企业上线后有一个现实问题：

> 模型不是训练一次就结束。

真实情况：

今天：

```text
Qwen-Java-v1
```

上线。

一个月后：

新增：

- 5000条面试数据
    
- 新版Spring源码
    
- 新业务知识
    

怎么办？

不能人工：

```text
重新训练

手动测试

手动部署
```

企业需要：

# MLOps【Machine Learning Operations，机器学习工程运维】

---

# 一、什么是 MLOps？

传统软件：

```text
代码

↓

Git

↓

CI/CD

↓

上线
```

---

AI系统：

除了代码，还有：

- 数据
    
- 模型
    
- Prompt
    
- 评测
    

所以：

```text
代码

+

数据

+

模型

+

评测


↓

自动化发布
```

---

# 二、企业 AI 生命周期

完整流程：

```text
数据采集

↓

数据清洗

↓

数据版本管理

↓

训练

↓

模型评测

↓

模型注册

↓

部署

↓

监控

↓

反馈数据

↓

重新训练
```

形成闭环：

```text
        用户反馈

             |

             ↓

        新训练数据

             |

             ↓

          新模型

             |

             ↓

          新版本

             |

             ↓

        线上验证

             |

             ↓

          用户反馈
```

---

# 三、为什么需要模型版本管理？

普通软件：

```text
app-v1.0

app-v1.1

app-v2.0
```

模型也一样。

不能：

```text
qwen-final-final-new真的最终版
```

企业需要：

规范：

```text
model:

java-interviewer


version:

v1.0.0

v1.1.0

v2.0.0
```

---

# 四、模型版本包含什么？

一个模型版本：

不是只有权重。

完整信息：

```json
{
"name":
"java-interviewer",

"version":
"v2.1",


"base_model":
"Qwen2.5-7B",


"dataset":
"java-interview-dataset-v3",


"lora_rank":
16,


"training_date":
"2026-09-22",


"evaluation_score":
0.92

}
```

---

# 五、Model Registry【模型注册中心】

作用：

保存：

- 模型文件
    
- 元数据
    
- 版本
    
- 状态
    

类似：

GitHub管理代码。

---

常见工具：

## MLflow

开源。

功能：

- 实验记录
    
- 模型保存
    
- 版本管理
    

架构：

```text
训练

↓

MLflow Tracking

↓

Model Registry

↓

部署
```

---

## Hugging Face Hub

也可以：

保存：

- 模型
    
- Adapter
    
- Dataset
    

---

# 六、你的项目模型管理

目录：

```text
models/


├── java-interviewer-v1

│
├── java-interviewer-v2

│
└── java-interviewer-v3
```

---

例如：

v1:

```text
基础Java面试
```

v2:

增加：

```text
Spring源码
```

v3:

增加：

```text
AI Agent面试
```

---

# 七、数据版本管理

这是企业非常重要的部分。

为什么？

因为：

模型效果不好。

你需要知道：

是不是：

- 数据问题？
    
- 模型问题？
    
- 参数问题？
    

---

# 八、Dataset Version【数据集版本】

例如：

```text
java-interview-dataset


v1

1000条


v2

3000条


v3

10000条
```

---

记录：

```json
{
"version":"v3",

"count":10000,

"source":[

"leetcode",

"内部笔记",

"源码分析"

]
}
```

---

# 九、数据管理工具

## DVC

Data Version Control【数据版本控制】

类似：

Git管理代码。

DVC管理：

- 数据集
    
- 模型文件
    

---

流程：

```text
Git

管理代码


DVC

管理数据

```

---

# 十、自动训练 Pipeline

企业不会：

SSH进去：

```bash
python train.py
```

而是：

Pipeline。

---

架构：

```text
数据更新

↓

触发训练

↓

环境准备

↓

QLoRA训练

↓

Evaluation

↓

模型注册

↓

部署
```

---

# 十一、Pipeline工具

常见：

## Airflow

任务编排。

---

## Kubeflow

Kubernetes机器学习平台。

---

## GitHub Actions

简单自动化。

---

# 十二、你的训练Pipeline设计

例如：

每天凌晨：

检查：

是否新增面试数据。

流程：

```text
Git Push

↓

Dataset Check

↓

Data Validation

↓

Start QLoRA

↓

Evaluation

↓

Compare Old/New

↓

Deploy
```

---

# 十三、数据质量检测

训练前：

不能直接训练。

检查：

---

## 格式

例如：

是否：

```json
instruction

input

output
```

---

## 重复

检测：

重复问题。

---

## 长度

例如：

答案：

只有：

"不知道"

删除。

---

## 安全

检测：

敏感信息。

---

# 十四、自动评测 Pipeline

模型训练完成：

不能直接上线。

流程：

```text
New Model

↓

Evaluation Dataset

↓

自动测试

↓

评分

↓

是否超过旧模型？
```

---

例如：

旧模型：

```text
score:

85
```

新模型：

```text
score:

92
```

允许发布。

---

# 十五、LLM Evaluation指标

## 1. Accuracy【准确性】

答案是否正确。

---

## 2. Faithfulness【忠实性】

是否依据知识库。

---

## 3. Relevance【相关性】

是否回答问题。

---

## 4. Latency【延迟】

响应速度。

---

## 5. Cost【成本】

Token消耗。

---

# 十六、自动部署

评测通过：

进入：

Deployment。

---

例如：

Kubernetes：

```text
Model v1

↓

90%

Model v2

↓

10%
```

---

# 十七、自动回滚

如果：

新模型：

错误增加。

自动：

```text
v2

↓

error rate ↑

↓

rollback

↓

v1
```

---

# 十八、完整企业 MLOps 架构

最终：

```text
                     数据源

                       |

                       ↓


                Dataset Repository


                       |

                       ↓


                 Training Pipeline


                       |

          +------------+-------------+

          |                          |


          ↓                          ↓


       MLflow                 Evaluation


          |

          ↓


      Model Registry


          |

          ↓


      Deployment


          |

          ↓


        vLLM


          |

          ↓


        用户

```

---

# 十九、你的 Java AI 项目升级

现在：

Java AI Interview Agent V8：

增加：

```text
MLOps能力


数据版本管理

+

模型版本管理

+

自动训练

+

自动评测

+

灰度发布

+

自动回滚
```

---

# 二十、面试回答

## 问：

> 你们模型如何持续优化？

标准回答：

> 我们建立了完整的 MLOps 流程。首先通过数据版本管理维护训练数据变化，训练阶段使用 LLaMA-Factory 进行 QLoRA 微调，同时记录模型参数和实验结果。训练完成后通过 Evaluation 数据集自动评测模型效果，只有指标超过当前线上版本才进入模型注册和灰度发布。如果线上指标异常，可以快速回滚到稳定版本。

---

# 二十一、你的 AI Engineer 能力最终地图

现在：

```text
AI Application Engineer


          |

+---------+---------+

|                   |


AI应用              AI工程基础


|                   |


RAG                GPU部署


Agent              vLLM


Tool Calling       LoRA


MCP                MLOps


Security           Evaluation
```

---

# 下一节 Day18

建议进入：

# 《Day18：企业级 AI 系统完整设计答辩：从需求分析 → 架构设计 → 技术选型 → 上线运维》

这一节模拟：

> 你作为 AI 应用架构师，设计一个企业大模型系统。

会覆盖真实面试：

- “如果让你设计 ChatGPT 类系统怎么办？”
    
- “100万用户如何支撑？”
    
- “为什么选 RAG 不选微调？”
    
- “GPU成本如何控制？”
    
- “如何保证安全？”
    

这一节会把前面 17 天全部串成一个完整项目。