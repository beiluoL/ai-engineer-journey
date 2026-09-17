# Lesson 01 — Python 变量、类型与输入输出

## 1. 学习目标

完成本课后你能：

- 用 Python 写变量、知道动态类型的含义
- 区分 str / int / float / bool / None
- 用 type() 查看变量类型
- 用 input() 接收用户输入，用 print() 输出
- 用 f-string 格式化字符串
- 把这些知识组合成一个最小项目：学习档案生成器

这是后面所有 Python AI 项目的地基。

---

## 2. Java 开发者如何理解 Python

你已经会 Java，不要把 Python 当一门完全陌生的语言。

Java：

```java
String name = "Beiluo";
int age = 29;
boolean learningAI = true;
```

Python：

```python
name = "Beiluo"
age = 29
learning_ai = True
```

Python 最大的初始区别：

> **通常不需要显式写变量类型。**

```text
Java
变量 = 类型 + 值

Python
变量 = 值
```

Python 会在运行时判断对象的类型。

---

## 3. 变量

Python 里写变量就是写一个名字，然后赋值：

```python
name = "Beiluo"
age = 29
learning_ai = True
```

命名规则：

- 字母、数字、下划线，不能以数字开头
- 区分大小写
- 用下划线分隔单词（snake_case），这是 Python 习惯

```text
Java：learningAI   （驼峰）
Python：learning_ai （下划线）
```

---

## 4. 基础类型

先记这几个：

| Python  | 含义   | Java 类比         |
| ------- | ------ | ----------------- |
| `str`   | 字符串 | `String`          |
| `int`   | 整数   | `int` / `Integer` |
| `float` | 小数   | `double`          |
| `bool`  | 布尔   | `boolean`         |
| `None`  | 空值   | `null`            |

注意三个关键字首字母大写，和 Java 不一样：

```python
True
False
None
```

---

## 5. type()

用 type() 看一个变量的类型：

```python
name = "Beiluo"
age = 29
learning_ai = True
score = 95.5

print(type(name))        # <class 'str'>
print(type(age))         # <class 'int'>
print(type(learning_ai)) # <class 'bool'>
print(type(score))       # <class 'float'>
```

Java 没有直接对应的方法，你可以把它理解成 `obj.getClass()`。

---

## 6. input()

input() 让程序与人交互：

```python
name = input("你的名字：")
print(f"你好，{name}！")
```

运行：

```text
你的名字：Beiluo
你好，Beiluo！
```

**关键坑：input() 默认返回字符串。**

哪怕你输入 `29`，得到的也是 `"29"`（str），不是 29（int）。

```python
age = input("年龄：")
print(type(age))   # <class 'str'>
```

需要整数时要手动转换：

```python
age = int(input("年龄："))
print(type(age))   # <class 'int'>
```

---

## 7. print()

print() 输出到控制台，最简单的用法：

```python
print("Hello, AI Engineer")
print(name)
```

可以一次输出多个值，默认用空格分隔：

```python
print("姓名:", name, "年龄:", age)
```

---

## 8. f-string

f-string 是 Python 最常用的格式化字符串方式：

```python
language = "Python"
days = 1
print(f"我已经学习 {language} {days} 天")
```

输出：

```text
我已经学习 Python 1 天
```

Java 开发者可以理解成更方便的字符串插值（比 String.format 更直观）。

---

## 9. Python 动态类型

Java 初学者容易把变量想成「一个固定类型的盒子」。

Python 更适合理解成「名字 → 指向一个对象」：

```python
name = "Beiluo"   # name 指向字符串
name = 29         # name 重新指向整数
```

所以 Python 是动态类型语言。

但注意：

> **动态类型 ≠ 没有类型。**

`29` 依然是 `int`。

---

## 10. Java vs Python

| 维度 | Java | Python |
|------|------|--------|
| 变量声明 | 必须写类型 | 不需要 |
| 类型 | 静态（编译期确定） | 动态（运行期确定） |
| 布尔 | `true` / `false` | `True` / `False` |
| 空值 | `null` | `None` |
| 命名习惯 | 驼峰 camelCase | 下划线 snake_case |
| 语句结尾 | 分号 `;` | 不需要 |
| 代码块 | 大括号 `{ }` | 缩进 |

---

## 11. 常见坑

### 坑 1：input() 返回字符串

```python
age = input("年龄：")  # 得到 "29" 而不是 29
age = int(age)         # 转成 int
```

### 坑 2：首字母大写

```python
true   # ❌ NameError
True   # ✅
```

### 坑 3：f-string 忘记 f

```python
print("你好，{name}")    # ❌ 原样输出 {name}
print(f"你好，{name}")   # ✅ 输出 你好，Beiluo
```

### 坑 4：变量命名用驼峰

```python
learningAI = True    # ❌ 能跑但不符合 Python 习惯
learning_ai = True   # ✅
```

---

## 12. 最小项目

把本课知识组合起来，写一个学习档案生成器。

代码见 [demo/main.py](demo/main.py)。

运行效果：

```text
你的名字：Beiluo
你的年龄：29
你的职业：Java开发工程师

========== 学习档案 ==========
姓名：Beiluo
年龄：29
职业：Java开发工程师
目标：AI Engineer
==============================
```

这就是 Project 01 的起点。

---

## 13. 主动回忆

先不看上面的答案，自己回答：

### Q1

```python
age = input("年龄：")
```

用户输入 `29` 后，`age` 是什么类型？

### Q2

为什么下面两段代码效果不同？

```python
age = input("年龄：")
```

和

```python
age = int(input("年龄："))
```

### Q3

```python
name = "Beiluo"
print(f"你好，{name}")
```

这里的 `f` 是干什么的？

### Q4

```python
x = 10
x = "hello"
```

在 Python 中合法吗？为什么？

### Q5

用 Python 写：让用户输入自己的名字和学习方向，然后输出：

```text
你好，xxx
你的学习方向是 xxx
你的最终目标是 AI Engineer
```

---

## 14. 练习

见 [exercises/](exercises/)。

练习原则：

```text
基础题 → 理解题 → 代码题 → 项目题
```

---

## 15. 下一章

[Lesson 02 — List / Dict / JSON / AI Messages](../02-list-dict/)

学完 Lesson 02 你会理解：

```text
list
 ↓
dict
 ↓
嵌套结构
 ↓
JSON
 ↓
API 请求数据
 ↓
AI messages（system / user / assistant）
```

Python 学习会开始和真正的大模型项目接上。
