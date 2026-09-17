# List + Dict = LLM Messages：Python 数据结构如何接上 AI

> 文章大纲（待 Lesson 02 学习时补全正文）

## 选题

面向有 Java 基础的开发者，讲清楚 LLM API 的 messages 结构其实就是 list + dict 的嵌套。

## 大纲

### 1. 从 Java 的 ArrayList 和 HashMap 说起

- Java List 和 Python list 的对照
- Java Map 和 Python dict 的对照

### 2. list + dict 嵌套

- list 里装 dict
- 这就是 Python 处理结构化数据最常见的方式

### 3. JSON：dict 和字符串的转换

- json.dumps / json.loads
- 为什么 LLM API 用 JSON

### 4. messages：LLM API 的核心数据结构

```python
messages = [
    {"role": "system", "content": "你是我的 Python 老师"},
    {"role": "user", "content": "什么是 list？"}
]
```

- system / user / assistant 三个角色
- 这就是一次 LLM API 请求的核心

### 5. 从 Python 基础到 AI 工程的连接点

- list → messages 的外层
- dict → 每条消息
- JSON → API 的数据格式
- 这一刻 Python 学习正式接上 AI 项目

## 待写

正文待 Lesson 02 正式学习后补全。
