# 04 — String：字符串

## 它是什么
文本数据。Project 01 的用户问题、系统提示词、API 响应全是字符串。

## Java 开发者如何理解

```java
// Java
String name = "AI";
String greeting = "Hello, " + name + "!";
String tpl = String.format("model=%s", name);
```

```python
# Python
name = "AI"
greeting = "Hello, " + name + "!"          # + 拼接一样
tpl = f"model={name}"                      # f-string：最常用，类似增强版 String.format
```

核心差异：**f-string 是 Python 拼字符串的首选**，直接在字符串里嵌表达式。

## 常用操作（AI 项目高频）

```python
prompt = "  什么是 RAG？  "
prompt.strip()                  # 去首尾空白，Java: trim()
prompt.strip().lower()          # 链式调用
len(prompt)                     # 长度，Java: length() —— 是函数不是方法
"RAG" in prompt                 # 包含判断，Java: contains() —— 返回 bool
".".join(["a", "b"])            # Java: String.join
"a,b".split(",")                # Java: split（Python 正则参数注意转义）
"line1\nline2"                  # 转义符一致
"""多行
字符串"""                        # 三引号：写多行 Prompt 神器
```

## 最小可运行 Demo

```python
# demo_string.py
question = input("你的问题: ").strip()

if not question:            # 空字符串是 falsy，等价 Java 的 isEmpty()
    print("问题不能为空")
else:
    # f-string 里可以放任意表达式
    print(f"收到 {len(question)} 个字符的问题: {question}")
    print(f"大写: {question.upper()}, 是否包含'AI': {'AI' in question}")

# 多行 system prompt
system_prompt = """你是一个耐心的 AI 助手。
请用简洁的中文回答。
如果不确定，请明确说明。"""
print(system_prompt)
```

## 常见错误

1. **`len` 写成方法**：`s.length()` ❌ → `len(s)` ✅。
2. **字符串不可变**：`s.strip()` 返回新字符串，必须接住 `s = s.strip()`，原串不变（这点和 Java 一致，但容易被链式调用骗）。
3. **split 陷阱**：Java `"a.b".split("\\.")`，Python `"a.b".split(".")`——Python 用正则但普通字符不用双反斜杠。
4. **f-string 忘了 f**：`"model={name}"` 原样输出，不插值。

## 常见面试问题
- Python 字符串可变吗？→ 不可变，修改操作都返回新对象。

## 练习
1. 读入用户输入，去掉空格后打印长度。
2. 用 f-string 输出 `模型 deepseek-chat，温度 0.7`。
3. 用三引号写一段三行 system prompt 并打印。

[下一课：05-list →](05-list.md)
