# Day27：大模型训练与微调完整实战

# Transformer → SFT → LoRA → QLoRA → LLaMA-Factory

前面 Day26 解决了：

> **模型是什么、怎么下载、怎么部署。**

你现在知道：

```text
Hugging Face

↓

Safetensors

↓

Transformers

↓

Ollama

↓

vLLM
```

但是还有一个核心问题：

> 一个大模型是怎么从“通用模型”变成“企业专用模型”的？

例如：

原始：

```text
Qwen2.5-7B
```

它会：

- 中文聊天
    
- 写代码
    
- 总结文章
    

但是企业想要：

```text
Java面试专家模型

客服专家模型

法律助手模型

医疗助手模型
```

怎么办？

答案：

# Model Fine-tuning【模型微调】

---

# 一、先理解：训练 ≠ 微调

很多小白误解：

> 我要训练一个ChatGPT。

实际上企业99%：

不是从0训练。

而是：

```text
基础模型

+

企业数据

↓

领域模型
```

---

# 二、大模型训练路线

完整流程：

```text

海量文本数据

↓

Pre-training【预训练】

↓

Base Model【基础模型】

↓

SFT【监督微调】

↓

RLHF/DPO【偏好优化】

↓

Chat Model【聊天模型】
```

---

# 三、Pre-training【预训练】

## 什么是预训练？

让模型学习：

语言规律。

例如：

输入：

```
Java中的HashMap底层采用
```

模型预测：

```
数组+链表+红黑树
```

---

训练数据：

非常大：

例如：

- 网页
    
- 书籍
    
- 代码
    
- 文档
    

规模：

TB级。

---

## 预训练目标

本质：

预测下一个Token。

例如：

输入：

```
我喜欢吃
```

模型预测：

```
苹果
香蕉
米饭
```

---

公式：

```text

P(next token | previous tokens)
```

---

# 四、Transformer是什么？

Transformer：

大模型核心结构。

2017年论文：

《Attention Is All You Need》

---

简单理解：

Transformer：

一个超级语言处理架构。

---

核心：

Attention【注意力机制】。

作用：

让模型知道：

一句话中哪些词重要。

---

例如：

```
小明把苹果给小红，因为她喜欢吃水果。
```

Attention：

知道：

“她”

指：

小红。

---

# 五、Transformer结构

简化：

```text

输入文本


↓

Tokenizer


↓

Embedding


↓

Transformer Layers


↓

Output


↓

预测Token

```

---

每一层：

包含：

```text

Attention

+

Feed Forward Network

+

Normalization
```

---

# 六、参数(Parameter)是什么？

例如：

Qwen2.5-7B。

7B：

70亿参数。

参数：

就是模型训练过程中学习出来的数字。

---

例如：

简单神经网络：

```text
y = wx+b
```

w：

就是参数。

---

大模型：

几十亿个w。

---

# 七、为什么不能直接训练？

假设：

Qwen 7B。

重新训练：

需要：

巨大GPU。

原因：

不仅存模型。

还需要：

- 梯度
    
- 优化器
    
- 激活值
    

显存需求：

可能几十GB到几百GB。

---

所以：

企业采用：

# Fine-tuning【微调】

---

# 八、SFT是什么？

## SFT

英文：

Supervised Fine-Tuning

中文：

监督微调。

---

作用：

让模型学会：

按照指令回答。

---

例如：

训练前：

用户：

```
解释HashMap
```

模型：

可能：

普通介绍。

---

SFT后：

```text
面试回答：

1. 数据结构

2. put流程

3. resize

4. 并发问题

5. 优化方案
```

---

# 九、SFT训练数据格式

最常见：

Instruction格式。

例如：

json：

```json
{
"instruction":
"你是Java高级面试官",

"input":
"ConcurrentHashMap为什么线程安全?",

"output":
"JDK8通过CAS+synchronized..."
}
```

---

这就是你之前创建的：

```text
java_interview.json
```

---

# 十、LoRA是什么？

## Low-Rank Adaptation

中文：

低秩适配。

---

核心思想：

不要修改整个模型。

冻结：

原模型。

增加：

小模块。

---

原模型：

```text

Qwen

70亿参数
```

---

加入：

```text

LoRA Adapter

几千万参数
```

---

结构：

```text

输入

 |

 ↓


原模型(W)


 +

LoRA(A,B)


 ↓


输出

```

---

# 十一、为什么LoRA有效？

研究发现：

模型参数变化：

其实集中在低维空间。

所以：

不用修改全部。

---

优势：

## 显存低

全量训练：

几十GB显存。

LoRA：

几GB～几十GB。

---

## 速度快

训练参数少。

---

## 多任务

一个模型：

多个Adapter。

例如：

```text

Qwen


+

Java LoRA


+

客服 LoRA


+

法律 LoRA
```

---

# 十二、QLoRA是什么？

## Quantized LoRA

中文：

量化低秩适配。

---

LoRA：

基础模型：

FP16。

---

QLoRA：

基础模型：

4bit量化。

---

区别：

```text

LoRA:

Qwen FP16

+

LoRA


QLoRA:

Qwen INT4

+

LoRA
```

---

# 十三、为什么QLoRA重要？

以前：

7B模型微调：

需要：

A100。

---

QLoRA：

4090：

24GB显存。

也可以。

---

所以：

个人学习首选：

QLoRA。

---

# 十四、LLaMA-Factory是什么？

## LLaMA-Factory

一个开源微调框架。

作用：

简化：

大模型训练。

---

以前：

自己写：

- Dataset
    
- Trainer
    
- LoRA
    
- Quantization
    

很复杂。

---

现在：

配置：

yaml。

运行：

```bash
llamafactory-cli train config.yaml
```

---

# 十五、LLaMA-Factory训练流程

完整：

```text

准备数据


↓

准备模型


↓

配置训练参数


↓

加载Tokenizer


↓

加载模型


↓

插入LoRA


↓

训练


↓

保存Adapter

```

---

# 十六、一次完整微调案例

目标：

Java Interview Model。

---

## Step1 数据

准备：

5000条：

```json
{
question:
"HashMap为什么线程不安全?",

answer:
"..."
}
```

---

## Step2 基础模型

下载：

```text
Qwen2.5-7B-Instruct
```

---

## Step3 配置

yaml：

```yaml
model_name_or_path:
Qwen2.5-7B


stage:
sft


finetuning_type:
lora


quantization_bit:
4


lora_rank:
16
```

---

## Step4 训练

执行：

```bash
llamafactory-cli train
```

---

## Step5 输出

得到：

```text
java-lora/


adapter_model.safetensors

adapter_config.json
```

---

# 十七、Adapter是什么？

LoRA训练产生：

不是完整模型。

例如：

原：

```text
Qwen:

15GB
```

---

LoRA：

```text
adapter:

100MB
```

---

运行：

需要：

```text

Qwen

+

Adapter
```

---

# 十八、合并模型

生产：

可能合并。

流程：

```text

Qwen

+

LoRA


↓

Merge


↓

完整模型


↓

vLLM部署
```

---

# 十九、微调后如何部署？

方式1：

加载Adapter。

方式2：

合并。

然后：

```bash
vllm serve \
java-qwen-model
```

---

调用：

Spring Boot：

```text

用户

↓

Java

↓

vLLM

↓

Java专家模型
```

---

# 二十、RAG和微调区别

这是面试必问。

||RAG|微调|
|---|---|---|
|解决|知识问题|能力问题|
|改变模型|否|是|
|数据变化|容易更新|需要训练|
|成本|低|高|
|适合|企业知识库|领域能力|

---

例子：

公司制度：

用RAG。

让模型：

学会客服语气。

用微调。

---

# 二十一、企业真实组合

不是二选一。

企业：

```text

基础模型

↓

RAG

↓

LoRA

↓

Agent

↓

业务系统
```

---

例如：

客服AI：

Qwen

客服LoRA

产品知识RAG

订单Agent

---

# 二十二、你的 Java AI 项目升级

之前：

```text
Spring Boot

+

LangChain4j

+

Qwen

+

Milvus
```

升级：

```text

Spring Boot


+

LangChain4j


+

Java Interview Qwen


+

LoRA


+

RAG


+

Agent
```

---

# 二十三、面试回答

## Q1：

> 为什么不用从零训练模型？

回答：

> 从零训练大模型需要大量数据、GPU资源和训练成本，企业更多采用基于开源基础模型进行领域微调，通过SFT和LoRA/QLoRA降低成本，同时结合RAG解决实时知识问题。

---

## Q2：

> LoRA为什么能降低训练成本？

回答：

> LoRA冻结基础模型参数，只训练新增的低秩矩阵参数，大幅减少需要更新的参数数量，因此降低显存占用和训练时间。

---

## Q3：

> RAG和微调怎么选择？

回答：

> 如果问题主要是知识更新，例如企业文档、产品资料，优先使用RAG；如果需要改变模型行为、表达风格或领域能力，则考虑微调。实际企业通常结合RAG和LoRA。

---

# 二十四、Day27知识地图

现在你理解：

```text

Transformer

↓

Pre-training

↓

Base Model

↓

SFT

↓

LoRA

↓

QLoRA

↓

Adapter

↓

Merge

↓

vLLM

↓

Production
```

---

# 下一节 Day28

建议进入：

# 《Day28：大模型训练环境实战：GPU服务器 → CUDA → PyTorch → LLaMA-Factory → QLoRA第一次训练》

下一节开始真正操作：

从：

购买/租GPU服务器

↓

Ubuntu

↓

CUDA安装

↓

显卡检测

↓

环境配置

↓

第一次训练你的 Java 面试模型。

目标：

完成：

> 你的第一个真正微调出来的 AI 模型。