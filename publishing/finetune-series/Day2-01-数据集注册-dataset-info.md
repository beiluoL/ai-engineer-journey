# 大模型微调实战 Day2-01：把 java_interview.json 注册进 LLaMA-Factory 数据集系统

# 把 `java_interview.json` 注册到 LLaMA-Factory 数据集系统

今天这一节的目标：

> 让 LLaMA-Factory 认识你的训练数据。

现在你的状态：

```text
/content

├── LLaMA-Factory
│
├── data
│   └── java_interview.json
```

但是 LLaMA-Factory 现在不知道：

- 这个文件叫什么
    
- 字段分别代表什么
    
- 哪个字段是问题
    
- 哪个字段是答案
    

所以需要注册。

---

# 一、理解 dataset_info.json 是什么

LLaMA-Factory 使用：

```text
dataset_info.json
```

作为数据说明书。

关系：

```text
java_interview.json

{
 instruction:
 input:
 output:
}


        ↓


dataset_info.json


告诉模型：

instruction 是问题背景

input 是用户问题

output 是标准答案


        ↓


LLaMA-Factory

        ↓

可以训练
```

---

# 二、找到 dataset_info.json

进入 LLaMA-Factory：

Colab执行：

```python
%cd /content/LLaMA-Factory
```

查看目录：

```python
!ls
```

你应该看到：

类似：

```text
assets
data
examples
src
README.md
```

---

进入 data：

```python
%cd data
```

查看：

```python
!ls
```

你会看到：

```text
dataset_info.json
```

这个文件就是注册中心。

---

# 三、查看原来的 dataset_info.json

运行：

```python
!cat dataset_info.json
```

你会看到很多已有数据：

例如：

```json
{
  "alpaca_gpt4_data_en": {
    "file_name": "alpaca_gpt4_data_en.json",
    "columns": {
      "prompt": "instruction",
      "query": "input",
      "response": "output"
    }
  }
}
```

不用害怕。

它只是：

数据集名称 → 文件 → 字段映射。

---

# 四、添加你的 Java 面试数据

不要删除原来的内容。

在最后增加：

```json
"java_interview": {
    "file_name": "java_interview.json",
    "columns": {
        "prompt": "instruction",
        "query": "input",
        "response": "output"
    }
}
```

---

完整类似：

```json
{
    "alpaca_gpt4_data_en": {
        "file_name": "alpaca_gpt4_data_en.json",
        "columns": {
            "prompt": "instruction",
            "query": "input",
            "response": "output"
        }
    },


    "java_interview": {
        "file_name": "java_interview.json",
        "columns": {
            "prompt": "instruction",
            "query": "input",
            "response": "output"
        }
    }
}
```

---

# 五、小白推荐：直接用 Python 修改

不要手改 JSON，容易逗号错误。

执行：

```python
import json


path="/content/LLaMA-Factory/data/dataset_info.json"


with open(path,"r",encoding="utf-8") as f:
    dataset_info=json.load(f)


dataset_info["java_interview"]={
    "file_name":"java_interview.json",
    "columns":{
        "prompt":"instruction",
        "query":"input",
        "response":"output"
    }
}


with open(path,"w",encoding="utf-8") as f:
    json.dump(
        dataset_info,
        f,
        indent=4,
        ensure_ascii=False
    )


print("注册成功")
```

输出：

```text
注册成功
```

---

# 六、确认注册成功

运行：

```python
!grep java_interview dataset_info.json
```

看到：

```text
"java_interview"
```

成功。

---

# 七、把训练数据放到正确位置

注意：

LLaMA-Factory 默认找：

```text
LLaMA-Factory/data/
```

所以你的文件应该：

现在：

可能：

```text
/content/data/java_interview.json
```

但是需要：

```text
/content/LLaMA-Factory/data/java_interview.json
```

复制：

```python
!cp /content/data/java_interview.json /content/LLaMA-Factory/data/
```

检查：

```python
!ls /content/LLaMA-Factory/data | grep java
```

应该：

```text
java_interview.json
```

---

# 八、测试数据是否能被识别

回到：

```python
%cd /content/LLaMA-Factory
```

运行：

```python
!llamafactory-cli train \
examples/train_lora/qwen2_lora_sft.yaml
```

注意：

这里先不要真的训练。

我们只是验证环境。

---

# 九、今天你理解一个关键概念

现在你的链路：

```text
java_interview.json

原始数据

        ↓


dataset_info.json

数据说明


        ↓


LLaMA-Factory


        ↓


训练器知道：

问题在哪里

答案在哪里


        ↓


进入QLoRA训练
```

---

# 十、你的项目数据以后应该这样设计

不要只做：

```json
问题
答案
```

建议升级：

```json
{
"instruction":
"你是Java高级面试官",

"input":
"为什么ConcurrentHashMap使用synchronized？",

"output":
"标准面试回答",

"category":
"Java并发",

"difficulty":
"S",

"tags":[
"ConcurrentHashMap",
"JDK8",
"synchronized"
],

"source":
"个人面试训练"
}
```

以后可以做：

- 自动评测
    
- 错题分析
    
- Agent训练
    
- RAG检索
    
- 面试评分
    

这会成为你自己的：

> Java Engineer Knowledge Dataset【Java工程师知识数据集】

---

# Day2 下一节

## Day2-02：创建 QLoRA 训练配置文件

下一步会做：

```text
train.yaml

↓

告诉LLaMA-Factory：

使用哪个模型

用什么数据

训练方式(LoRA)

训练多少轮

保存哪里

↓

启动第一次微调
```

下一步我们开始写第一个 `train.yaml`。