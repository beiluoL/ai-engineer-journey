# Day28：大模型训练环境实战

# GPU服务器 → CUDA → PyTorch → LLaMA-Factory → QLoRA第一次训练

前面 Day27：

你已经理解：

```text
Transformer

↓

预训练 Pre-training

↓

SFT

↓

LoRA

↓

QLoRA

↓

Adapter

↓

部署
```

但是作为 AI 工程师，光理解概念不够。

企业面试会问：

> “你有没有真正微调过模型？”

今天进入实战流程。

目标：

从 0：

租一台 GPU 服务器

↓

安装环境

↓

下载 Qwen

↓

准备数据

↓

LLaMA-Factory

↓

QLoRA训练

↓

测试模型

最终得到：

你的：

# Java Interview AI Model

---

# 一、完整微调链路

今天完成：

```text

GPU服务器


↓

Ubuntu系统


↓

NVIDIA Driver


↓

CUDA


↓

PyTorch


↓

Transformers


↓

LLaMA-Factory


↓

Qwen模型


↓

Java面试数据


↓

QLoRA


↓

LoRA Adapter


↓

测试
```

---

# 二、第一步：选择GPU服务器

微调不是普通服务器。

需要：

GPU显存。

---

## 入门推荐

### RTX4090

配置：

```text

GPU:

RTX4090 24GB


CPU:

8核以上


内存:

64GB


SSD:

200GB+
```

---

价格：

云GPU：

约：

2～10元/小时。

---

适合：

Qwen：

7B模型。

---

# 三、云GPU平台选择

国内：

## 1. AutoDL

适合：

个人学习。

优点：

- 便宜
    
- 镜像多
    
- CUDA环境方便
    

---

## 2. 阿里云PAI

企业常用。

---

## 3. 腾讯云GPU

企业常用。

---

国外：

## Lambda Cloud

## RunPod

## AWS

---

第一次：

推荐：

AutoDL。

---

# 四、创建GPU实例

选择：

Ubuntu。

推荐：

```text

Ubuntu 22.04

CUDA 12.x

Python 3.10
```

---

GPU：

选择：

RTX4090。

---

启动。

进入：

SSH。

---

# 五、连接服务器

Mac：

终端：

```bash
ssh root@服务器IP
```

例如：

```bash
ssh root@123.xxx.xxx.xxx
```

---

进入：

```text

root@server:

#
```

---

# 六、检查GPU

执行：

```bash
nvidia-smi
```

看到：

类似：

```
+----------------+

GPU Name

RTX4090


Memory

0MiB/24564MiB

+----------------+
```

说明：

GPU正常。

---

# 七、理解 nvidia-smi

输出：

例如：

```
GPU:

RTX4090


Memory:

0/24576MB


CUDA Version:

12.4
```

解释：

---

## GPU Name

显卡型号。

---

## Memory

显存。

24GB。

---

## CUDA Version

支持CUDA版本。

---

# 八、CUDA是什么？

再复习：

CUDA：

NVIDIA GPU计算平台。

关系：

```text

PyTorch

↓

CUDA

↓

NVIDIA Driver

↓

GPU
```

---

没有CUDA：

PyTorch不能调用GPU。

---

# 九、安装Python环境

推荐：

Conda。

安装：

```bash
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh


bash Miniconda3-latest-Linux-x86_64.sh
```

---

创建环境：

```bash
conda create \
-n llama \
python=3.10
```

---

进入：

```bash
conda activate llama
```

---

# 十、安装PyTorch

PyTorch：

深度学习框架。

作用：

加载模型、训练。

---

安装：

CUDA版本：

例如：

CUDA12.1。

```bash
pip install torch torchvision torchaudio \
--index-url https://download.pytorch.org/whl/cu121
```

---

测试：

Python：

```python
import torch


print(
torch.cuda.is_available()
)
```

输出：

```text
True
```

成功。

---

# 十一、安装LLaMA-Factory

项目：

[https://github.com/hiyouga/LLaMA-Factory](https://github.com/hiyouga/LLaMA-Factory)

---

下载：

```bash
git clone https://github.com/hiyouga/LLaMA-Factory.git
```

进入：

```bash
cd LLaMA-Factory
```

---

安装：

```bash
pip install -e .
```

---

测试：

```bash
llamafactory-cli version
```

---

# 十二、准备模型

选择：

Qwen2.5-7B-Instruct。

为什么？

你的目标：

Java AI工程师。

7B：

适合学习。

---

下载：

方式1：

Hugging Face。

```bash
huggingface-cli download \
Qwen/Qwen2.5-7B-Instruct
```

---

下载结构：

```text

Qwen2.5-7B


├── config.json

├── tokenizer.json

├── model.safetensors

└── generation_config.json
```

---

# 十三、准备训练数据

你的：

java_interview.json

例如：

```json
[
{
"instruction":
"你是一名Java高级面试官",

"input":
"HashMap为什么线程不安全？",

"output":
"HashMap在并发环境..."
}
]
```

---

放：

```text
LLaMA-Factory/data/

java_interview.json
```

---

# 十四、注册数据集

编辑：

```text
data/dataset_info.json
```

添加：

```json
{
"java_interview":{

"file_name":
"java_interview.json",

"columns":{

"instruction":
"instruction",

"input":
"input",

"output":
"output"

}

}
}
```

---

现在：

LLaMA-Factory知道：

你的数据在哪里。

---

# 十五、创建QLoRA配置

创建：

```text
train_java.yaml
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


output_dir:

./java-qwen-lora


learning_rate:

2e-4


num_train_epochs:

3


per_device_train_batch_size:

1


gradient_accumulation_steps:

8
```

---

解释：

---

## quantization_bit

```yaml
4
```

表示：

4bit量化。

就是：

QLoRA。

---

## lora

只训练：

Adapter。

---

## batch_size

一次训练多少数据。

显存小：

设置1。

---

## gradient_accumulation

模拟大Batch。

---

# 十六、开始训练

执行：

```bash
llamafactory-cli train \
train_java.yaml
```

---

屏幕：

类似：

```
epoch 1

loss 2.35


epoch 2

loss 1.21


epoch 3

loss 0.65
```

---

# 十七、Loss是什么？

Loss：

损失。

表示：

模型预测错误程度。

训练目标：

降低。

---

例如：

开始：

```
loss=3.0
```

训练：

```
loss=0.5
```

说明：

模型更适应数据。

---

注意：

不是越低越好。

过低：

可能：

过拟合。

---

# 十八、训练输出

生成：

```text

java-qwen-lora/


├── adapter_model.safetensors


├── adapter_config.json

```

---

这就是：

你的Java专家能力。

---

# 十九、测试模型

加载：

基础模型：

Qwen。

LoRA。

测试：

问题：

```
解释ConcurrentHashMap
```

观察：

是否：

更像Java面试专家。

---

# 二十、微调前后区别

原Qwen：

回答：

通用解释。

---

微调后：

回答：

更加：

```text

面试结构

↓

核心原理

↓

源码

↓

追问

↓

项目场景
```

---

# 二十一、企业真实流程

生产：

不是：

训练完直接上线。

流程：

```text

Dataset


↓

Training


↓

Evaluation


↓

Model Registry


↓

Gray Release


↓

Production
```

---

# 二十二、常见错误

## 错误1：

显存不足

解决：

降低：

- batch
    
- rank
    
- seq length
    

---

## 错误2：

CUDA不匹配

检查：

```bash
nvidia-smi
```

和：

PyTorch CUDA版本。

---

## 错误3：

数据质量差

大模型微调：

数据 > 参数。

---

# 二十三、你的项目实践路线

你的目标：

Java AI Engineer。

建议训练：

三个LoRA。

---

## 模型1：

Java Interview LoRA

数据：

1000～5000题。

---

## 模型2：

AI Engineer Interview LoRA

数据：

RAG/Agent/MCP。

---

## 模型3：

你的个人知识助手

数据：

你的：

- Obsidian
    
- 博客
    
- 学习笔记
    

---

# 二十四、面试回答

## Q：

> 你有没有做过模型微调？

回答：

> 我使用Qwen2.5-7B作为基础模型，通过LLaMA-Factory完成SFT训练，采用QLoRA方式降低显存占用。训练数据采用JSON指令格式，通过LoRA Adapter学习Java技术面试场景，训练完成后通过vLLM加载模型，并结合Spring Boot和LangChain4j提供业务接口。

---

# 二十五、Day28知识地图

现在完整链路：

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


↓

Merge


↓

vLLM


↓

Spring Boot
```

---

# 下一节 Day29

建议进入：

# 《Day29：模型评测与生产上线：Evaluation → Model Registry → vLLM → 灰度发布》

因为企业真正关心：

不是：

“你会训练”。

而是：

> “你训练的模型有没有效果？怎么安全上线？”

下一节学习：

- Golden Dataset【黄金测试集】
    
- 自动评测
    
- 人工评测
    
- 模型版本管理
    
- 灰度发布
    
- A/B测试
    
- 生产监控
    

这一步就是从：

**会微调模型 → 会管理企业模型生命周期。**