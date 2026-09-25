# 大模型微调实战 Day2-03：正式启动第一次 QLoRA 训练

# 正式启动第一次 QLoRA 训练

今天是整个流程中第一个“模型开始学习”的阶段。

目标：

> 让 Qwen2.5-3B 读取你的 Java 面试数据，通过 LoRA 学习你的回答风格。

最终得到：

```text
Qwen2.5-3B

        +

Java面试LoRA Adapter

        ↓

java-interview-lora
```

---

# 一、训练前最后检查

现在你的目录应该是：

```text
/content/LLaMA-Factory

├── train_java.yaml

├── data
│   ├── dataset_info.json
│   └── java_interview.json

├── src
├── examples
```

检查：

```python
!ls
```

应该看到：

```text
train_java.yaml
data
src
```

---

检查数据：

```python
!cat data/java_interview.json
```

确认：

类似：

```json
[
 {
  "instruction":"你是一名Java高级工程师面试官",
  "input":"HashMap为什么线程不安全？",
  "output":"..."
 }
]
```

---

# 二、查看 GPU 状态

训练前：

运行：

```python
!nvidia-smi
```

现在应该：

类似：

```text
GPU Memory Usage

0MiB
```

因为还没加载模型。

---

# 三、启动训练

现在执行：

```python
!llamafactory-cli train train_java.yaml
```

第一次：

会经历：

```text
1. 加载Qwen模型

↓

2. 加载Tokenizer

↓

3. 加载训练数据

↓

4. 创建LoRA模块

↓

5. 开始训练
```

---

# 四、你会看到什么？

正常日志类似：

```text
Loading checkpoint shards...

Loading dataset...

trainable params:
2,359,296

all params:
3,000,000,000

trainable%:
0.07%
```

这里非常重要。

---

## 为什么只有0.07%参数训练？

因为：

不是训练整个模型。

原模型：

```
Qwen

30亿参数

冻结
```

训练：

```
LoRA

几百万参数
```

所以：

速度快。

显存低。

---

# 五、训练过程怎么看？

你会看到：

例如：

```text
Epoch 1/3


step 10

loss: 2.15


step 20

loss: 1.82


step 30

loss: 1.45
```

---

## Loss 是什么？

Loss：

**损失值【模型错误程度】**

简单理解：

模型回答：

```
HashMap为什么线程不安全？
```

第一次：

输出：

```
HashMap是一种Map
```

和你的标准答案差距大。

Loss：

高。

训练后：

输出：

```
因为HashMap没有同步机制...
```

接近答案。

Loss：

下降。

---

# 六、第一次训练时间

你的配置：

```yaml
Qwen2.5-3B

LoRA

T4 GPU

1000条数据
```

大约：

```
20分钟～2小时
```

取决于：

- 数据量
    
- GPU
    
- batch
    

---

# 七、如果出现显存不足

错误：

```text
CUDA out of memory
```

解决：

修改：

## 1. batch 调小

原：

```yaml
per_device_train_batch_size:2
```

改：

```yaml
per_device_train_batch_size:1
```

---

## 2. cutoff_len降低

原：

```yaml
cutoff_len:1024
```

改：

```yaml
cutoff_len:512
```

---

## 3. 开启4bit QLoRA

修改：

增加：

```yaml
quantization_bit: 4
```

完整：

```yaml
quantization_bit: 4

finetuning_type: lora
```

---

# 八、训练完成后生成什么？

成功结束：

会看到：

```text
training completed
```

然后：

查看：

```python
!ls output
```

出现：

```text
java-interview-lora
```

进入：

```python
!ls output/java-interview-lora
```

类似：

```
adapter_config.json

adapter_model.safetensors

training_args.bin

README.md
```

---

# 九、这些文件是什么？

## adapter_model.safetensors

你的：

> Java 面试能力插件

不是完整模型。

结构：

```
Qwen2.5-3B

       +

adapter_model

       ↓

Java Interview Model
```

---

## adapter_config.json

记录：

LoRA配置：

例如：

```json
{
"r":8,
"alpha":16
}
```

---

# 十、训练完成后测试

下一步：

我们不能直接说成功。

必须比较：

## 微调前

Qwen：

问题：

```
如何回答HashMap线程安全吗？
```

可能：

普通解释。

---

## 微调后：

希望：

```
面试回答：

HashMap线程不安全主要原因：

1. put并发覆盖

2. 扩容死循环(JDK7)

3. 数据结构没有同步

实际项目应该使用ConcurrentHashMap...
```

这才说明：

模型学到了你的风格。

---

# 十一、今天你的能力提升

完成这一节，你已经真正接触：

|能力|掌握|
|---|---|
|GPU环境|✅|
|模型加载|✅|
|SFT|✅|
|LoRA|✅|
|训练配置|✅|
|Loss理解|✅|
|Adapter生成|✅|

---

# 下一节 Day3-01

## 第一次微调效果验证

内容：

1. 加载 Base Model
    
2. 加载 LoRA Adapter
    
3. 输入 Java 面试问题
    
4. 对比训练前后输出
    
5. 判断微调有没有效果
    

然后进入：

**Day3：把你的 LoRA 模型接入 Ollama / Spring Boot / LangChain4j**

这一步会把“模型训练”连接到你熟悉的 Java AI 工程。