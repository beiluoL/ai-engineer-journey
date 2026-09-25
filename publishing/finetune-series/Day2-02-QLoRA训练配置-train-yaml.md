# 大模型微调实战 Day2-02：创建 QLoRA 训练配置 train.yaml

# 创建 QLoRA 训练配置文件 `train.yaml`

今天目标：

> 告诉 LLaMA-Factory：我要用哪个模型、哪个数据、用什么方式训练、训练结果保存哪里。

完成后链路：

```text
 id="5e4r9h"
java_interview.json
        |
        ↓
dataset_info.json
        |
        ↓
train.yaml
        |
        ↓
LLaMA-Factory
        |
        ↓
Qwen2.5-3B + QLoRA训练
```

---

# 一、先理解 train.yaml 是什么

如果说：

`dataset_info.json`

是：

> 数据说明书

那么：

`train.yaml`

就是：

> 训练计划书

它告诉训练程序：

例如：

```text
我要训练：

模型：
Qwen2.5-3B-Instruct

数据：
java_interview

方法：
LoRA

训练：
3轮

保存：
java-lora
```

---

# 二、进入 LLaMA-Factory

Colab执行：

```python
%cd /content/LLaMA-Factory
```

确认：

```python
!pwd
```

应该：

```text
/content/LLaMA-Factory
```

---

# 三、查看官方训练模板

LLaMA-Factory 已经准备好了很多例子。

查看：

```python
!ls examples/train_lora
```

你会看到：

类似：

```text
qwen2_lora_sft.yaml
llama3_lora_sft.yaml
```

我们参考它。

---

查看 Qwen 示例：

```python
!cat examples/train_lora/qwen2_lora_sft.yaml
```

里面很多参数。

第一次不用全部理解。

---

# 四、创建自己的配置文件

创建：

```text
train_java.yaml
```

位置：

```text
/content/LLaMA-Factory/train_java.yaml
```

---

Colab里面创建：

```python
%%writefile train_java.yaml


### 模型
model_name_or_path: Qwen/Qwen2.5-3B-Instruct


### 数据
dataset: java_interview

template: qwen


### 训练阶段
stage: sft

do_train: true


### 微调方式
finetuning_type: lora


### LoRA参数
lora_rank: 8

lora_alpha: 16

lora_dropout: 0.05


### 训练参数
learning_rate: 2.0e-4

num_train_epochs: 3

cutoff_len: 1024


### batch
per_device_train_batch_size: 2

gradient_accumulation_steps: 4


### 保存
output_dir: ./output/java-interview-lora


### 日志
logging_steps: 10

save_steps: 100


### GPU优化
fp16: true
```

运行后：

看到：

```text
Writing train_java.yaml
```

---

# 五、逐个解释关键参数

## 1. model_name_or_path

```yaml
model_name_or_path:
 Qwen/Qwen2.5-3B-Instruct
```

意思：

基础模型。

现在：

```text
Qwen
+
你的数据
=
新的能力
```

---

# 2. dataset

```yaml
dataset:
 java_interview
```

对应：

刚才注册：

```json
"java_interview"
```

也就是：

```text
dataset_info.json

        ↓

找到

java_interview.json
```

---

# 3. template

```yaml
template:
 qwen
```

非常重要。

不同模型聊天格式不同。

例如：

Qwen：

```text
<|im_start|>system

<|im_start|>user

<|im_start|>assistant
```

Llama：

格式不同。

所以告诉框架：

> 使用 Qwen 对话模板。

---

# 4. stage

```yaml
stage:
 sft
```

SFT：

**Supervised Fine-Tuning【监督微调】**

目前你的训练：

就是：

输入：

```text
HashMap为什么线程不安全？
```

输出：

```text
标准面试答案
```

---

# 5. finetuning_type

```yaml
finetuning_type:
 lora
```

表示：

不要改整个模型。

原模型：

```text
Qwen

30亿参数

冻结
```

新增：

```text
LoRA参数

训练
```

---

# 6. LoRA参数

## lora_rank

```yaml
lora_rank:8
```

理解：

LoRA容量。

越大：

能力可能越强。

但是：

显存增加。

第一次：

8即可。

---

## learning_rate

```yaml
learning_rate:2e-4
```

学习速度。

太大：

容易学坏。

太小：

学不动。

---

## num_train_epochs

```yaml
num_train_epochs:3
```

训练轮数。

你的数据：

500-1000条。

3轮够。

---

# 六、检查配置文件

运行：

```python
!cat train_java.yaml
```

应该看到完整配置。

---

# 七、检查数据路径

非常重要。

执行：

```python
!ls data | grep java
```

应该：

```text
java_interview.json
```

如果没有：

复制：

```python
!cp /content/data/java_interview.json /content/LLaMA-Factory/data/
```

---

# 八、检查 LLaMA-Factory 是否认识数据

运行：

```python
!python src/train.py train_java.yaml --help
```

如果没有报错：

说明 YAML 基本正确。

---

# 九、第一次训练前，理解显存

你的配置：

```yaml
Qwen2.5-3B

+

LoRA

+

fp16
```

大概：

```text
模型:
6GB左右

训练:
额外几个GB

T4:
15GB
```

可以跑。

---

# 十、今天完成状态

你现在已经完成：

✅ Colab GPU

✅ LLaMA-Factory

✅ Qwen模型

✅ Java训练数据

✅ 数据注册

✅ QLoRA配置

完整链路：

```text
 id="8l5p8a"
Java面试数据

        ↓

dataset_info.json

        ↓

train_java.yaml

        ↓

LLaMA-Factory

        ↓

Qwen2.5-3B

        ↓

LoRA Adapter
```

---

# 下一节 Day2-03

正式开始：

# 第一次 QLoRA 训练启动

内容：

1. 执行训练命令
    
2. 查看 GPU 占用
    
3. 看 Loss 下降
    
4. 训练完成后的文件
    
5. 测试模型是否学会你的 Java 面试风格
    

下一步就是最激动的部分：

```bash
llamafactory-cli train train_java.yaml
```

第一次让你的数据改变模型。