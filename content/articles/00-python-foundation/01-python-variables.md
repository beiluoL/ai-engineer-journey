# 从 Java 到 Python：我的第一行 AI 工程代码

> AI Engineer Journey / Phase 0 / Lesson 01 学习笔记
> 面向和我一样有 Java 基础、但 Python 零基础的开发者。

## 写在前面

我写了 6 年 Java，最近决定学 AI 工程。

第一步不是 Transformer，不是 PyTorch，而是——Python 基础。

但我不想学传统 Python 教材。我想直接在 AI 场景里学。

所以我的第一行代码，是做一个「AI Engineer 学习档案生成器」：用户输入信息，Python 接收、保存、输出。

听起来很简单，但这正是后面所有 AI 项目的地基。

## Java 开发者的第一感觉

Java 里写变量：

```java
String name = "Beiluo";
int age = 29;
boolean learningAI = true;
```

Python 里：

```python
name = "Beiluo"
age = 29
learning_ai = True
```

最大的区别：**不用写类型**。Python 在运行时自己判断。

但注意三个关键字首字母大写：

```python
True    # 不是 true
False   # 不是 false
None    # 不是 null
```

这是我从 Java 过来第一个踩的坑。

## input() 的坑

```python
age = input("年龄：")
```

我输入 `29`，以为 age 是 int。结果：

```python
print(type(age))  # <class 'str'>
```

**input() 永远返回字符串。**

需要整数时：

```python
age = int(input("年龄："))
```

这个坑 Java 里没有，因为 Java 的 Scanner 有 nextInt()。

## f-string：比 String.format 直观

Java：

```java
String.format("你好，%s", name)
```

Python：

```python
f"你好，{name}"
```

直接在字符串里插变量，前面加个 `f`。简单、直观、常用。

## 第一个项目

把变量、类型、input、print、f-string 组合起来：

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
你的职业：Java开发工程师

========== 学习档案 ==========
姓名：Beiluo
年龄：29
职业：Java开发工程师
目标：AI Engineer
==============================
```

这就是 Project 01 的起点。

## 最大的认知转变

Java 里变量是「一个固定类型的盒子」。

Python 里变量是「一个名字 → 指向一个对象」：

```python
name = "Beiluo"   # name 指向字符串
name = 29         # name 重新指向整数
```

合法。因为 Python 是动态类型。

但**动态类型 ≠ 没有类型**。`29` 依然是 `int`。

## 下一步

变量和类型只是地基。下一步学 list / dict / JSON，
然后就会看到 LLM API 的 messages 结构——那就是 list + dict 的嵌套。

Python 学习开始和真正的大模型项目接上。
