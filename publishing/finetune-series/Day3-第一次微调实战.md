# 第一次微调实战 Day3

# 把 LoRA 模型接入 Ollama / Spring Boot / LangChain4j

今天进入最关键的工程化阶段：

> 昨天你只是“训练出了一个模型插件”，今天要让 Java 程序真正调用它。

最终目标：

做出：

# Java AI Interview Agent【Java AI 面试智能体】

架构：

```text
 id="2e0v8d"
用户
 |
 ↓
Vue 前端
 |
 ↓
Spring Boot
 |
 ↓
LangChain4j
 |
 ↓
LLM接口
 |
 ↓
Qwen + Java Interview LoRA
 |
 ↓
面试回答
```

---

# 一、先理解：LoRA 不能直接给 Ollama

这是很多新手第一个坑。

你训练出来：

```text
java-interview-lora
```

它不是完整模型。

它只是：

```text
Adapter【适配器】
```

类似：

你买了一台手机：

```
Qwen模型 = 手机本体

LoRA = 一个专业插件
```

两个组合：

```
Qwen
 +
Java Interview LoRA

=
Java面试专家模型
```

---

所以流程：

```text
LoRA

↓

合并

↓

完整模型

↓

Ollama加载
```

---

# 二、Day3整体路线

今天：

```text
Step1
Colab合并LoRA


Step2
导出HuggingFace模型


Step3
转换GGUF


Step4
导入Ollama


Step5
Spring Boot调用


Step6
LangChain4j接入
```

---

# 三、Step1：合并 LoRA

回到 Colab。

假设：

你的输出：

```
output/java-interview-lora
```

现在需要：

```
Qwen2.5-3B

+

adapter

↓

merged model
```

---

安装：

```python
!pip install peft transformers accelerate
```

---

创建：

```python
merge_lora.py
```

内容：

```python
from transformers import AutoModelForCausalLM, AutoTokenizer

from peft import PeftModel


base_model = "Qwen/Qwen2.5-3B-Instruct"

adapter_path = "./output/java-interview-lora"


# 加载基础模型

model = AutoModelForCausalLM.from_pretrained(
    base_model,
    device_map="auto"
)


# 加载LoRA

model = PeftModel.from_pretrained(
    model,
    adapter_path
)


# 合并

model = model.merge_and_unload()


# 保存

model.save_pretrained(
    "./java-interview-qwen"
)


tokenizer = AutoTokenizer.from_pretrained(
    base_model
)


tokenizer.save_pretrained(
    "./java-interview-qwen"
)


print("merge success")
```

运行：

```bash
python merge_lora.py
```

得到：

```
java-interview-qwen
```

---

# 四、Step2：测试合并后的模型

先不用 Ollama。

Python测试：

```python
from transformers import pipeline


pipe = pipeline(
    "text-generation",
    model="./java-interview-qwen"
)


result = pipe(
"""
HashMap为什么线程不安全？
""",
max_new_tokens=300
)


print(result)
```

观察：

有没有你的面试风格。

---

# 五、Step3：转换 Ollama 支持格式

Ollama 推荐：

GGUF。

为什么？

原模型：

```
float16

几十GB
```

GGUF：

```
量化

几GB
```

适合个人电脑。

---

安装 llama.cpp：

Mac：

```bash
brew install llama.cpp
```

下载：

```bash
git clone https://github.com/ggerganov/llama.cpp
```

---

转换：

```bash
python convert_hf_to_gguf.py \
java-interview-qwen \
--outfile java-interview.gguf
```

得到：

```
java-interview.gguf
```

---

# 六、Step4：导入 Ollama

你的 Mac 已经有：

Ollama。

创建：

```
Modelfile
```

内容：

```dockerfile
FROM ./java-interview.gguf


PARAMETER temperature 0.7


SYSTEM """
你是一名Java高级工程师面试官。
回答需要按照：
1.核心原理
2.源码分析
3.项目实践
4.面试话术
输出。
"""
```

---

创建模型：

```bash
ollama create java-interviewer \
-f Modelfile
```

查看：

```bash
ollama list
```

应该：

```
java-interviewer
```

---

# 七、测试 Ollama

运行：

```bash
ollama run java-interviewer
```

输入：

```
ConcurrentHashMap为什么线程安全？
```

期待：

类似：

```
JDK8取消Segment。

核心：

1.CAS
2.synchronized
3.Node
4.TreeBin

面试回答：
...
```

---

# 八、Step5：Spring Boot 接入

你的技术栈：

你熟悉：

```
Spring Boot
+
LangChain4j
```

添加依赖：

Maven：

```xml
<dependency>
    <groupId>
        dev.langchain4j
    </groupId>

    <artifactId>
        langchain4j-ollama-spring-boot-starter
    </artifactId>

    <version>
        最新版本
    </version>

</dependency>
```

---

配置：

application.yml

```yaml
langchain4j:

  ollama:

    chat-model:

      base-url:
        http://localhost:11434


      model-name:
        java-interviewer


      temperature:
        0.7
```

---

# 九、创建 AI Service

Java代码：

```java
public interface InterviewAssistant {


    String answer(
        String question
    );

}
```

---

绑定：

```java
@Bean
InterviewAssistant assistant(
    OllamaChatModel model
){

return AiServices.create(
        InterviewAssistant.class,
        model
);

}
```

---

调用：

```java
assistant.answer(
"HashMap为什么线程不安全？"
);
```

流程：

```
Spring Boot

↓

LangChain4j

↓

Ollama

↓

java-interviewer

↓

Qwen+LoRA

↓

答案
```

---

# 十、升级成真正 AI Agent

你现在已经有：

模型能力：

```
Java Interview LLM
```

下一步：

加入：

## RAG

查询：

```
你的面试笔记
项目文档
源码分析
```

然后：

```
RAG
 +
Fine-tuning
```

架构：

```
用户问题

↓

Retriever

↓

Java知识库

↓

Qwen LoRA

↓

回答
```

---

# 十一、你最终简历项目

可以包装成：

## Java AI Interview Agent

技术：

```
Spring Boot
LangChain4j
Qwen2.5
QLoRA
LoRA
LLaMA-Factory
Ollama
Milvus
RAG
Agent
```

功能：

- 上传简历
    
- 自动生成面试题
    
- AI模拟面试
    
- 评分
    
- 错题复习
    
- 个性化回答
    

---

# 但是这里有一个现实问题

你现在的 Mac：

```text
16G ARM
```

可以：

✅ Ollama运行3B/7B量化模型  
✅ 开发Spring Boot  
✅ 做RAG

但是：

❌ 不适合长期运行合并后的16bit模型。

所以生产建议：

```
LoRA训练
        ↓
云GPU

        ↓

导出GGUF

        ↓

Mac Ollama测试

        ↓

服务器vLLM部署
```

---

下一步建议进入：

# Day4：把 RAG + LoRA 结合

因为真正企业项目不是：

> “训练一个模型”

而是：

> **RAG 提供企业知识 + Fine-tuning 改变模型行为**

下一步我们做：

```
Java AI Interview Agent V1

=
Qwen LoRA
+
Milvus知识库
+
LangChain4j
+
Spring Boot
```

这会直接贴近你现在的 Java + AI 求职方向。