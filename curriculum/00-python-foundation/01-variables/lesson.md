

# Lesson 01 — Python 变量、类型与输入输出

> AI Engineer Journey · Phase 0 — Python Foundation  
> 学习目标：从 Java 开发者视角建立 Python 基础，并完成第一个 Python 小项目。

---

## 1. 本章学习目标

学完本章，你应该能够：

- 理解 Python 变量的基本使用方式
    
- 理解 Python 常见基础数据类型
    
- 使用 `print()` 输出内容
    
- 使用 `input()` 获取用户输入
    
- 使用 `type()` 查看对象类型
    
- 使用 `f-string` 格式化字符串
    
- 理解 Python 的动态类型
    
- 能看懂简单 Python 程序
    
- 能独立写一个简单的交互式 Python 程序
    
- 理解 Python 基础知识如何服务于后面的 AI 项目
    

本章暂时不学习：

- 面向对象
    
- 异步
    
- FastAPI
    
- PyTorch
    
- Transformer
    
- RAG
    
- Agent
    

这些内容会随着后续项目逐步加入。

---

# 2. 为什么 AI 工程要先学 Python

Python 是当前 AI / 机器学习 / 大模型开发中非常重要的语言之一。

我们后面会接触：

```text
Python
 ↓
PyTorch
 ↓
Transformers
 ↓
Hugging Face
 ↓
RAG
 ↓
Agent
 ↓
Fine-tuning
 ↓
Model Deployment
```

因此现在学习 Python，不是为了成为“传统 Python 程序员”，而是为了建立后续 AI 开发需要的基础。

我们的学习方式也不是：

```text
先学几个月 Python
↓
再学 AI
```

而是：

```text
Python 基础
↓
马上进入 AI 项目
↓
遇到问题
↓
继续补 Python
```

这也是 AI Engineer Journey 的核心学习方法：

> **在真实项目中学习 Python。**

---

# 3. Java 开发者应该如何理解 Python

你已经有 Java 基础，所以没有必要把 Python 当成完全陌生的编程语言。

很多基础编程思想是一样的：

```text
变量
条件
循环
函数
类
异常
模块
数据结构
```

真正需要适应的是 Python 的语法和运行模型。

先看一个最简单的对比。

### Java

```java
String name = "Beiluo";
int age = 29;
boolean learningAI = true;
```

### Python

```python
name = "Beiluo"
age = 29
learning_ai = True
```

最大的区别之一：

> Python 通常不需要在变量定义时显式写类型。

---

# 4. 什么是变量

变量可以先理解为：

> **给一个数据绑定一个名字，方便程序后面继续使用它。**

例如：

```python
name = "Beiluo"
age = 29
```

可以理解为：

```text
name
 ↓
"Beiluo"

age
 ↓
29
```

后面使用：

```python
print(name)
print(age)
```

输出：

```text
Beiluo
29
```

---

# 5. Python 变量赋值

基本形式：

```python
变量名 = 值
```

例如：

```python
name = "Beiluo"
age = 29
score = 95.5
learning_ai = True
```

这里：

```text
name         → 字符串
age          → 整数
score        → 浮点数
learning_ai  → 布尔值
```

---

# 6. Python 常见基础类型

本章先掌握 4 个最重要的类型。

## 6.1 `str` —— 字符串

表示文本。

```python
name = "Beiluo"
language = "Python"
```

类型：

```python
print(type(name))
```

输出：

```text
<class 'str'>
```

`str` 是：

> String【字符串】

---

## 6.2 `int` —— 整数

例如：

```python
age = 29
days = 7
count = 100
```

类型：

```python
print(type(age))
```

输出：

```text
<class 'int'>
```

`int` 是：

> Integer【整数】

---

## 6.3 `float` —— 浮点数

表示带小数的数字。

```python
score = 95.5
temperature = 36.5
```

类型：

```python
print(type(score))
```

输出：

```text
<class 'float'>
```

`float` 是：

> Floating-point number【浮点数】

---

## 6.4 `bool` —— 布尔值

只有两个值：

```python
True
False
```

例如：

```python
learning_ai = True
finished_python = False
```

类型：

```python
print(type(learning_ai))
```

输出：

```text
<class 'bool'>
```

注意 Python 的写法：

```python
True
False
```

而不是 Java 的：

```java
true
false
```

---

# 7. `None` —— 空值

Python 中常见的空值：

```python
result = None
```

它表示：

> 当前没有值。

例如：

```python
answer = None
```

可以理解成：

```text
answer
 ↓
当前没有结果
```

Java 开发者可以先把它理解成和 `null` 类似的概念，但两者并不是完全相同的语言机制。

---

# 8. 使用 `type()` 查看类型

Python 中可以使用：

```python
type()
```

查看一个对象的类型。

例如：

```python
name = "Beiluo"
age = 29
score = 95.5
learning_ai = True

print(type(name))
print(type(age))
print(type(score))
print(type(learning_ai))
```

结果：

```text
<class 'str'>
<class 'int'>
<class 'float'>
<class 'bool'>
```

你应该养成一个习惯：

> **不确定一个变量是什么类型时，先使用 `type()` 看看。**

---

# 9. Python 是动态类型语言

这是 Python 和 Java 的一个重要区别。

Java：

```java
String name = "Beiluo";
int age = 29;
```

声明变量时通常明确写类型。

Python：

```python
name = "Beiluo"
age = 29
```

Python 根据运行时对象判断类型。

例如：

```python
x = 10
print(type(x))

x = "hello"
print(type(x))
```

输出：

```text
<class 'int'>
<class 'str'>
```

说明：

```text
第一次：
x → int

第二次：
x → str
```

这就是动态类型语言的典型特征。

---

# 10. 动态类型不等于“没有类型”

这是初学者非常容易产生的误区。

Python 虽然不要求你在变量定义时写类型：

```python
x = 10
```

但 `10` 仍然有明确类型：

```python
int
```

所以正确理解是：

> **Python 是动态类型语言，但 Python 中的对象依然有类型。**

---

# 11. Python 变量更适合怎样理解

Java 初学者有时会把变量理解成：

```text
一个固定类型的盒子
```

Python 可以先理解成：

```text
变量名
 ↓
引用某个对象
```

例如：

```python
x = 10
```

可以粗略理解：

```text
x
 ↓
10
```

然后：

```python
x = "hello"
```

变成：

```text
x
 ↓
"hello"
```

所以同一个变量名可以先绑定整数，之后再绑定字符串。

---

# 12. `print()`：输出内容

最简单：

```python
print("Hello Python")
```

输出：

```text
Hello Python
```

输出多个内容：

```python
name = "Beiluo"
age = 29

print(name)
print(age)
```

也可以：

```python
print(name, age)
```

---

# 13. `input()`：获取用户输入

这是我们第一个真正的交互功能。

```python
name = input("请输入你的名字：")
print(name)
```

运行：

```text
请输入你的名字：Beiluo
Beiluo
```

程序执行过程：

```text
程序
 ↓
input()
 ↓
等待用户输入
 ↓
用户输入
 ↓
Python 得到结果
 ↓
继续执行
```

---

# 14. `input()` 有一个非常重要的特点

无论用户输入什么：

```python
age = input("请输入年龄：")
```

得到的默认都是：

```text
str
```

例如用户输入：

```text
29
```

看起来是数字，但 Python 得到的是字符串：

```python
age = input("请输入年龄：")

print(age)
print(type(age))
```

结果：

```text
29
<class 'str'>
```

---

# 15. 字符串转整数

如果你真的需要整数：

```python
age = int(input("请输入年龄："))
```

这里发生了：

```text
用户输入
 ↓
"29"
 ↓
int()
 ↓
29
```

现在：

```python
print(type(age))
```

结果：

```text
<class 'int'>
```

---

# 16. 类型转换

最常见的几个转换：

```python
int("29")
float("3.14")
str(100)
bool(1)
```

例如：

```python
age = int("29")
score = float("95.5")
count = str(100)
```

注意：

并不是任何字符串都可以转换成整数。

例如：

```python
int("hello")
```

会报错。

这个问题后面学习异常处理时会再次遇到。

---

# 17. f-string：Python 很常用的字符串格式化

例如：

```python
name = "Beiluo"
age = 29

print(f"我的名字是 {name}，今年 {age} 岁。")
```

输出：

```text
我的名字是 Beiluo，今年 29 岁。
```

这种写法叫：

> f-string【格式化字符串】

最简单的理解：

```text
f"普通文字 {变量}"
```

Python 会把变量的值放进字符串。

---

# 18. Java 和 Python 的字符串拼接对比

Java：

```java
String name = "Beiluo";
int age = 29;

System.out.println(
    "我的名字是 " + name + "，今年 " + age + " 岁。"
);
```

Python：

```python
name = "Beiluo"
age = 29

print(f"我的名字是 {name}，今年 {age} 岁。")
```

Python 的 f-string 在日常开发中非常方便。

---

# 19. 第一个完整 Demo

下面把本章内容组合起来：

```python
name = input("你的名字：")
age = int(input("你的年龄："))
role = input("你的职业：")

print("\n========== 学习档案 ==========")
print(f"姓名：{name}")
print(f"年龄：{age}")
print(f"职业：{role}")
print("目标：AI Engineer")
print("==============================")
```

运行：

```text
你的名字：Beiluo
你的年龄：29
你的职业：Java 开发工程师

========== 学习档案 ==========
姓名：Beiluo
年龄：29
职业：Java 开发工程师
目标：AI Engineer
==============================
```

---

# 20. 第一个小项目

现在正式把它当作一个小项目：

# Python Learning Profile

目标：

> 使用 Python 创建一个简单的学习档案生成器。

用户输入：

```text
姓名
年龄
职业
```

程序输出：

```text
学习档案
```

这个项目看起来很简单，但它有一个重要意义：

```text
Python 输入
 ↓
变量
 ↓
数据类型
 ↓
数据处理
 ↓
格式化
 ↓
输出
```

这其实就是后面 AI 程序的基础模式。

---

# 21. 项目代码

建议文件：

```text
01-variables/
└── demo/
    └── profile.py
```

代码：

```python
name = input("你的名字：")
age = int(input("你的年龄："))
role = input("你的职业：")

print("\n========== 学习档案 ==========")
print(f"姓名：{name}")
print(f"年龄：{age}")
print(f"职业：{role}")
print("学习目标：AI Engineer")
print("==============================")
```

---

# 22. 从这个项目开始建立 AI Engineer 思维

现在暂时不要认为：

> “我只是学了几个 Python 基础语法。”

我们换一个角度：

```text
用户输入
 ↓
程序接收
 ↓
数据保存
 ↓
数据处理
 ↓
结果输出
```

以后：

```text
用户输入问题
 ↓
Python 接收
 ↓
构造 messages
 ↓
调用 LLM
 ↓
模型返回结果
 ↓
Python 处理
 ↓
前端展示
```

你会发现：

> 基本的软件工程链路没有变。

只是：

```text
普通程序
```

逐渐变成：

```text
AI 程序
```

---

# 23. 本章知识地图

```text
Python 基础
│
├── Variable【变量】
│
├── Data Type【数据类型】
│   ├── str
│   ├── int
│   ├── float
│   ├── bool
│   └── None
│
├── Input
│   └── input()
│
├── Output
│   └── print()
│
├── Type Inspection
│   └── type()
│
├── Type Conversion
│   ├── int()
│   ├── float()
│   ├── str()
│   └── bool()
│
└── String Formatting
    └── f-string
```

---

# 24. 知识联系描述

变量负责给数据绑定名称，数据类型描述数据是什么，`input()` 负责从用户获取数据，`print()` 负责向用户展示结果，`type()` 可以帮助我们确认数据类型，而类型转换可以让输入的数据变成程序真正需要的类型。f-string 则把处理后的变量重新组织成用户能够理解的文本。

整体关系可以理解成：

```text
用户
 ↓
input()
 ↓
变量
 ↓
数据类型
 ↓
类型转换 / 数据处理
 ↓
f-string
 ↓
print()
 ↓
用户
```

这条链是后面所有 AI 应用输入输出流程的基础。

---

# 25. 常见错误

## 错误 1：把 `input()` 认为是数字

错误理解：

```python
age = input("年龄：")
```

然后直接：

```python
age + 1
```

这会出问题，因为 `age` 是字符串。

正确：

```python
age = int(input("年龄："))
```

---

## 错误 2：Python 的布尔值写成小写

错误：

```python
learning_ai = true
```

正确：

```python
learning_ai = True
```

---

## 错误 3：认为动态类型就是没有类型

错误理解：

> Python 没有类型。

正确理解：

> Python 有类型，只是不要求在变量定义时显式声明类型。

---

## 错误 4：看到 `f""` 不知道是什么

例如：

```python
f"你好，{name}"
```

这里的 `f` 表示这是一个格式化字符串。

---

# 26. Java → Python 快速对照

|Java|Python|
|---|---|
|`String`|`str`|
|`int`|`int`|
|`double`|`float`|
|`boolean`|`bool`|
|`null`|`None`|
|`System.out.println()`|`print()`|
|`Scanner`|`input()`|
|`Integer.parseInt()`|`int()`|
|字符串拼接|f-string|
|显式变量类型|动态类型|

注意：

> 这里只是帮助建立直觉，不代表 Java 和 Python 的底层机制完全相同。

---

# 27. 主动回忆

不要重新查看上面的内容，先自己回答。

### Q1

下面：

```python
age = input("年龄：")
```

如果用户输入：

```text
29
```

那么 `age` 是什么类型？

---

### Q2

为什么：

```python
age = input("年龄：")
```

和：

```python
age = int(input("年龄："))
```

结果不一样？

---

### Q3

下面代码中的 `f` 有什么作用？

```python
name = "Beiluo"
print(f"你好，{name}")
```

---

### Q4

下面代码是否合法？

```python
x = 10
x = "hello"
```

为什么？

---

### Q5

下面几个值分别是什么类型？

```python
"Java"
29
95.5
True
None
```

---

# 28. 练习

## Exercise 01：个人信息

编写程序：

```text
请输入姓名：
请输入年龄：
请输入职业：
请输入学习方向：
```

最终输出：

```text
========== 我的学习档案 ==========

姓名：
年龄：
职业：
学习方向：

目标：
AI Engineer

==================================
```

要求：

- 年龄必须使用 `int`
    
- 使用 f-string
    
- 不要把结果直接写死
    

---

## Exercise 02：类型观察

编写程序：

```python
a = "100"
b = 100
c = 100.0
d = True
```

分别打印：

```text
值
类型
```

---

## Exercise 03：类型转换

尝试理解：

```python
x = "100"

print(x)
print(type(x))

x = int(x)

print(x)
print(type(x))
```

解释：

> 为什么转换前后 `type()` 不一样？

---

# 29. Challenge：学习目标生成器

写一个小程序：

```text
请输入你的名字：
请输入当前技术栈：
请输入每天学习小时数：
```

最终输出：

```text
你好，XXX！

你的当前技术栈：XXX
每天学习：X 小时

你的目标：

成为 AI Engineer
```

额外要求：

- 学习小时数使用 `float`
    
- 使用 f-string
    
- 使用至少 3 个变量
    
- 不要写死用户输入
    

---

# 30. 本章完成标准

不是：

> “看完了。”

而是你能够做到：

### Level 1：看懂

能够理解：

```python
name = "Beiluo"
age = 29
```

---

### Level 2：跟做

能够自己运行：

```python
input()
print()
type()
```

---

### Level 3：独立修改

能够把：

```python
role = input("你的职业：")
```

修改成：

```python
goal = input("你的学习目标：")
```

---

### Level 4：独立实现

不用看答案，可以自己写出“个人学习档案”程序。

---

### Level 5：解释

能够解释：

> 为什么 `input()` 默认得到字符串？

> 什么是动态类型？

> `str`、`int`、`float`、`bool` 分别是什么？

---

# 31. 与后续 AI 项目的关系

这一章虽然没有调用大模型，但它已经在为后面的项目铺路。

未来：

```text
input()
 ↓
用户问题
```

会逐渐变成：

```text
input()
 ↓
User Message
 ↓
messages
 ↓
LLM API
 ↓
AI Response
```

因此：

```text
Python 输入输出
```

最终会发展成：

```text
AI 应用输入输出
```

这是本章与后续 AI 工程的连接点。

---

# 32. 本章自媒体素材

本章以后可以加工成：

### 文章

> 《Java 开发者第一次学 Python，到底应该学什么？》

> 《Python 的变量为什么不像 Java 一样声明类型？》

> 《input() 踩坑：为什么我输入 29，Python 却说它是字符串？》

### 视频

> 《Java 程序员 10 分钟理解 Python 变量》

> 《Python 和 Java 到底有哪些区别？》

这些属于 Publishing 层内容，不放在本章 `lesson.md` 中。

---

# 33. 下一章

下一章：

# Lesson 02 — Python List / Dict、JSON 与 AI Messages

路线：

```text
List【列表】
 ↓
Dict【字典】
 ↓
List + Dict
 ↓
Nested Data【嵌套数据】
 ↓
JSON
 ↓
AI API
 ↓
messages
 ↓
system / user / assistant
```

最终你会第一次真正理解：

> **为什么 LLM API 中的 `messages` 本质上就是 Python 的 `list + dict` 结构。**

---

# 34. 本章一句话总结

> **Python 的变量负责保存和引用数据，基础类型描述数据的种类，`input()` 获取数据，`print()` 输出数据，类型转换处理数据，而这些最基础的能力最终都会成为 AI 应用输入、处理和输出的基础。**