# Day13 企业级 LoRA 微调部署实战

# 数据 → QLoRA训练 → 模型合并 → vLLM加载 → 灰度发布

今天进入真正企业级大模型流程：

> **不是训练一个模型，而是把一个基础模型变成一个业务模型，并安全上线。**

完整链路：

```text
业务需求

↓

数据采集

↓

数据清洗

↓

数据标注

↓

训练集构建

↓

QLoRA微调

↓

模型评测

↓

LoRA Adapter

↓

模型合并

↓

量化

↓

vLLM部署

↓

灰度发布

↓

线上监控

↓

持续迭代
```

---

# 一、先理解企业为什么微调

很多公司现在不是：

> 训练一个新模型

而是：

> 基于开源模型做领域适配。

例如：

基础模型：

```
Qwen2.5-7B-Instruct
```

能力：

- 中文
    
- 编程
    
- 通用问答
    

企业希望：

```
金融客服模型

医疗助手模型

代码助手模型

内部知识助手模型
```

所以：

```text
基础模型

+

企业数据

↓

领域模型
```

---

# 二、你的实际项目目标

继续我们的：

# Java AI Interview Agent

目标：

训练：

```
Qwen2.5-7B-Instruct

↓

Java Interview Adapter

↓

Java面试专家模型
```

---

模型能力变化：

训练前：

用户：

> ConcurrentHashMap如何实现线程安全？

模型：

普通解释。

训练后：

模型：

```
面试回答：

1. 先讲设计思想

2. JDK8源码

3. CAS+synchronized

4. 扩容机制

5. 项目场景
```

---

# 三、企业微调架构

完整架构：

```
                    数据平台

                       |

                       ↓


                 Training Dataset


                       |

                       ↓


                 QLoRA Training


                       |

        +--------------+--------------+

        |                             |


        ↓                             ↓


   Base Model                 LoRA Adapter


        |                             |


        +-------------+---------------+

                      |

                      ↓


              Merged Model


                      |

                      ↓


                vLLM Serving


                      |

                      ↓


              Production API
```

---

# 四、第一步：数据工程

企业里：

数据比模型重要。

---

## 1. 数据来源

你的 Java 项目：

可以来自：

```
data/

├── java_core

│   ├── hashmap.jsonl

│   ├── concurrenthashmap.jsonl


├── spring

│   ├── springboot.jsonl


├── ai

│   ├── rag.jsonl

│   ├── agent.jsonl


└── project

    └── interview.jsonl
```

---

# 五、训练数据格式

企业推荐：

JSONL

一个样本一行。

例如：

`java_interview.jsonl`

```json
{
"instruction":
"你是一名Java高级工程师面试官",

"input":
"ConcurrentHashMap为什么线程安全？",

"output":
"JDK8 ConcurrentHashMap通过CAS+synchronized保证线程安全。空桶使用CAS插入，非空桶锁住头节点..."
}
```

---

# 六、数据清洗

真实企业不会直接训练。

需要：

## 1. 去重

例如：

10000条：

重复：

3000条。

删除。

---

## 2. 去垃圾数据

删除：

```
你好
谢谢
不知道
```

---

## 3. 格式统一

统一：

```
instruction

input

output
```

---

## 4. 数据质量评分

增加：

```json
{
"quality_score":5
}
```

---

# 七、数据规模

小模型：

|数据量|效果|
|---|---|
|100条|实验|
|500-1000条|可以看到变化|
|5000-10000条|明显提升|
|10万+|企业级|

---

你的第一版：

建议：

```
3000条Java AI面试数据
```

足够。

---

# 八、第二步：准备训练服务器

微调比推理更吃资源。

## QLoRA 7B

推荐：

### GPU

最低：

```
RTX4090 24GB
```

推荐：

```
A100 40GB
```

---

## 配置：

```
CPU:
16核

内存:
64GB

GPU:
24GB+

磁盘:
300GB SSD
```

---

# 九、安装训练环境

服务器：

Ubuntu 22.04

创建环境：

```bash
conda create \
-n finetune \
python=3.10


conda activate finetune
```

---

安装：

```bash
pip install torch

pip install transformers

pip install accelerate

pip install peft

pip install bitsandbytes

pip install datasets

pip install trl
```

---

# 十、使用 LLaMA-Factory

安装：

```bash
git clone \
https://github.com/hiyouga/LLaMA-Factory.git


cd LLaMA-Factory


pip install -e .
```

---

# 十一、配置 QLoRA

创建：

```
train_qwen.yaml
```

内容：

```yaml
model_name_or_path:
 Qwen/Qwen2.5-7B-Instruct


stage:
 sft


do_train:
 true


finetuning_type:
 lora


quantization_bit:
 4


dataset:
 java_interview


template:
 qwen


lora_rank:
 16


lora_alpha:
 32


learning_rate:
 2e-4


num_train_epochs:
 3


output_dir:
 ./java-lora
```

---

# 十二、启动训练

执行：

```bash
llamafactory-cli train \
train_qwen.yaml
```

训练过程：

```
Loading Qwen


↓

Loading dataset


↓

Inject LoRA


↓

Training


Epoch 1

loss 2.1


Epoch 2

loss 1.3


Epoch 3

loss 0.8
```

---

# 十三、训练产物

完成：

```
java-lora

├── adapter_model.safetensors

├── adapter_config.json

└── tokenizer
```

注意：

这里不是完整模型。

它是：

```
Qwen

+

插件
```

---

# 十四、模型评测

企业不会直接上线。

需要 Evaluation。

---

## 测试集

例如：

```
test.jsonl
```

100个问题。

---

测试：

训练前：

```
HashMap回答
```

训练后：

```
HashMap回答
```

比较：

---

## 指标

### 1. Accuracy

是否回答正确。

---

### 2. Format

是否符合面试格式。

---

### 3. Hallucination

是否乱编。

---

### 4. Human Evaluation

人工评分。

---

# 十五、模型合并

生产通常：

Adapter:

```
Qwen

+

LoRA
```

合并：

```
Merged Model
```

代码：

```python
model.merge_and_unload()
```

得到：

```
java-qwen-7b
```

---

# 十六、模型量化

生产：

一般不会用FP16。

因为：

显存太大。

转换：

```
FP16

↓

INT8

↓

INT4
```

例如：

7B:

FP16:

14GB+

INT4:

4-6GB

---

# 十七、部署到 vLLM

上传模型：

服务器：

```
/models/java-qwen-7b
```

启动：

```bash
vllm serve \
/models/java-qwen-7b \
--host 0.0.0.0 \
--port 8000
```

---

现在：

你的线上模型：

```
Spring Boot

↓

vLLM

↓

Java-Qwen-7B

↓

GPU
```

---

# 十八、灰度发布

企业不会：

训练完：

直接替换。

流程：

---

## 旧模型

```
qwen-v1
```

线上：

100%

---

## 新模型

```
qwen-java-v2
```

先：

10%流量。

架构：

```
             Gateway

                 |

          +------+------+

          |             |

          ↓             ↓


       v1模型       v2模型


       90%          10%
```

---

观察：

- 延迟
    
- 错误率
    
- 用户评分
    

---

# 十九、模型版本管理

类似代码：

```
models/

├── qwen-java-v1

├── qwen-java-v2

└── qwen-java-v3
```

记录：

```
模型版本

训练数据版本

参数

评测结果

发布时间
```

---

# 二十、企业完整 CI/CD

最终：

```
Git

↓

数据仓库

↓

训练Pipeline

↓

Evaluation

↓

Model Registry

↓

Deployment

↓

Monitoring
```

类似：

软件发布。

---

# 二十一、成本估算

## 微调一次 QLoRA 7B

RTX4090：

3小时：

```
约5-10元
```

---

A100：

3小时：

```
几十元
```

---

企业：

长期训练：

```
几千～几万元/月
```

---

# 二十二、你的最终能力闭环

现在你已经覆盖：

```
模型选择

↓

模型下载

↓

GPU环境

↓

推理部署

↓

vLLM

↓

RAG

↓

Agent

↓

LoRA微调

↓

模型评测

↓

灰度上线

↓

监控
```

这就是：

# AI Application Engineer 完整能力链

---

# 下一阶段 Day14

下一步建议进入：

# 《Day14：从单模型到企业 AI 平台：LLM Gateway、多模型路由、成本控制、自动扩缩容》

学习企业真正的大模型平台架构：

```
          用户

            ↓

       AI Gateway

            ↓

 +----------+-----------+

 |          |           |

Qwen     DeepSeek    GPT


 |          |           |

成本/性能/质量自动路由
```

这一步会让你从：

> 会部署模型

升级到：

> 能设计企业 AI 平台架构。