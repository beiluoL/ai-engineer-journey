


# 第一次微调实战 Day1

# 从 0 到跑通 Qwen + LLaMA-Factory + 第一份 Java 面试训练数据

今天的目标非常明确：

> **不训练大模型，只完成一次完整环境搭建，让你理解大模型微调的第一条链路。**

今天结束后，你应该拥有：

```text
Google Colab GPU环境
        ↓
LLaMA-Factory 微调框架
        ↓
Qwen基础模型
        ↓
Java面试训练数据集
        ↓
第一次训练准备完成
```

---

# Day1 总览

预计时间：

|任务|时间|
|---|--:|
|注册 Google Colab|10分钟|
|开启GPU|5分钟|
|测试环境|10分钟|
|安装LLaMA-Factory|30分钟|
|下载Qwen模型|20分钟|
|准备训练数据|1小时|
|理解流程|30分钟|

总计：

约3小时。

---

# 第一部分：准备 Google Colab

## 1. 注册 Google 账号

打开：

[https://colab.research.google.com/](https://colab.research.google.com/)

登录 Google 账号。

进入后：

点击：

```
File
 ↓
New Notebook
```

中文：

```
文件
 ↓
新建笔记本
```

你会看到：

```
Untitled0.ipynb
```

这就是你的训练环境。

---

# 第二部分：开启 GPU

顶部菜单：

```
修改
 ↓
笔记本设置
 ↓
硬件加速器
 ↓
GPU
```

选择：

```
GPU
```

保存。

---

## 检查 GPU

第一个代码：

复制：

```python
!nvidia-smi
```

点击运行。

正常应该看到：

类似：

```
+----------------------+

NVIDIA-SMI

Tesla T4

Memory:
15360MiB

+----------------------+
```

说明：

你的云电脑有 NVIDIA GPU。

![[Pasted image 20260922224924.png]]

---

## 如果显示：

```
/bin/bash: nvidia-smi command not found
```

说明：

没有 GPU。

重新：

```
运行时
 ↓
更改运行时类型
 ↓
GPU
```

---

# 第三部分：理解 Colab

你现在拥有：

一台临时 Linux 服务器：

```text
你的Mac浏览器

        ↓

Google服务器

        ↓

Linux

        ↓

NVIDIA GPU

        ↓

训练模型
```

你的 Mac 不负责训练。

只是控制它。

---

# 第四部分：安装 Python 环境

现在开始安装 AI 工具。

创建一个代码块：

```python
!python --version
```

输出：

例如：

```
Python 3.10.x
```

正常。

---

升级 pip：

```python
!pip install --upgrade pip
```



---

# 第五部分：安装 LLaMA-Factory

## 什么是 LLaMA-Factory？

你可以理解：

以前训练模型：

需要自己写：

- 数据读取
    
- 模型加载
    
- LoRA配置
    
- 训练循环
    
- 保存模型
    

非常复杂。

LLaMA-Factory：

把这些封装好了。

你的流程：

```text
数据

↓

yaml配置

↓

一条命令训练
```

---

安装：

运行：

```python
!git clone https://github.com/hiyouga/LLaMA-Factory.git
```

完成：

看到：

```
Cloning into 'LLaMA-Factory'
```

![[Pasted image 20260922225213.png]]
---

进入目录：

```python
%cd LLaMA-Factory
```

---

安装：

```python
!pip install -e .
```

等待。

可能需要：

5-20分钟。

---

# 第六部分：检查 LLaMA-Factory

运行：

```python
!llamafactory-cli version
```

正常：

类似：

```
LLaMA-Factory version xxx
```

成功。

---

# 第七部分：安装模型依赖

安装：

```python
!pip install transformers datasets accelerate peft bitsandbytes sentencepiece
```

作用：

|组件|作用|
|---|---|
|Transformers|加载Qwen|
|Datasets|读取数据|
|PEFT|LoRA|
|Bitsandbytes|4bit量化|
|Accelerate|GPU训练|
|SentencePiece|Tokenizer|

---

# 第八部分：下载第一个 Qwen 模型

第一次不要7B。

选择：

# Qwen2.5-3B-Instruct

为什么？

因为：

3B：

约30亿参数。

适合第一次。

---

测试下载：

新建代码：

```python
from transformers import AutoTokenizer


model_name="Qwen/Qwen2.5-3B-Instruct"


tokenizer = AutoTokenizer.from_pretrained(
    model_name
)


print("下载成功")
```

第一次：

会下载：

约几GB。

看到：

```
下载成功
```

说明：

模型可以使用。

---

# 第九部分：准备你的第一份训练数据

现在开始最重要部分。

## 不要训练知识

训练：

> 行为 + 输出格式

例如：

不是：

```
HashMap是什么？
```

而是：

```
请使用Java高级面试方式回答HashMap
```

---

创建：

```
java_interview.json
```

内容：

```json
[
 {
  "instruction": "你是一名Java高级工程师面试官，请用面试回答方式回答问题",
  "input": "HashMap为什么线程不安全？",
  "output": "HashMap线程不安全主要原因是多个线程同时修改共享数据结构。JDK8中HashMap采用数组+链表+红黑树结构，但没有加锁。在并发put时可能导致数据覆盖、链表结构异常等问题。因此多线程环境应该使用ConcurrentHashMap。"
 },

 {
  "instruction": "你是一名Java高级工程师面试官，请用面试回答方式回答问题",
  "input": "ConcurrentHashMap JDK8如何保证线程安全？",
  "output": "JDK8 ConcurrentHashMap取消Segment分段锁设计，采用CAS+synchronized实现。空桶插入使用CAS，非空桶锁住头节点，通过Node链表或者TreeBin保证并发安全。同时支持扩容迁移。"
 }
]
```

---

这就是：

## SFT数据

SFT:

**Supervised Fine-Tuning【监督微调】**

意思：

告诉模型：

```
问题

↓

优秀答案

↓

学习这种回答方式
```

---

# 第十部分：创建数据目录

在 Colab：

```python
!mkdir -p data
```

上传：

```
java_interview.json
```

放：

```
data/java_interview.json
```

---

检查：

```python
!ls data
```

看到：

```
java_interview.json
```

成功。

---

# 第十一部分：今天先不要训练

为什么？

因为第一次训练前，需要理解：

完整链路：

```text
训练数据

{
问题:
HashMap为什么线程不安全？

答案:
xxxx
}


        ↓


Tokenizer【分词器】

        ↓


Qwen模型

        ↓


计算Loss【损失】

        ↓


调整LoRA参数

        ↓


保存Adapter
```

---

# Day1完成标准

你今天完成：

## 环境

✅ Google Colab  
✅ GPU  
✅ Python环境

## 工具

✅ LLaMA-Factory安装  
✅ Transformers安装

## 模型

✅ Qwen2.5-3B下载

## 数据

✅ 第一份Java训练集

---

# 明天 Day2

进入真正训练：

《第一次 QLoRA 微调实战 Day2：配置 LLaMA-Factory → 训练 Qwen → 查看 Loss → 保存 LoRA → 第一次让模型学会 Java 面试回答》

内容：

1. 注册数据集
    
2. 写 yaml 配置
    
3. 启动训练
    
4. 看 GPU 占用
    
5. 理解 Loss
    
6. 保存 LoRA Adapter
    
7. 测试微调前后区别
    

---

不过在进入 Day2 前，我建议你今天先完成 **Day1 的环境搭建**。

你可以按照顺序执行，每执行一步把结果截图/复制给我，我帮你判断是否正确。不要跳步骤。