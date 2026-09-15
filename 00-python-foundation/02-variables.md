# 02 — Variables：变量

## 它是什么
给数据起个名字。类比 Java：`String name = "Tom";` → Python：`name = "Tom"`。

## 为什么需要它
Project 01 里要保存用户的问题、API 地址、模型名——都是变量。

## Java 开发者如何理解

```java
// Java：必须声明类型
final String model = "deepseek-chat";
int maxTokens = 1024;
```

```python
# Python：不声明类型，类型跟着值走
model = "deepseek-chat"
max_tokens = 1024
```

三大差异（务必记住）：

1. **动态类型**：变量没有固定类型，`x = 1` 之后 `x = "abc"` 合法（Python 不会拦你，运行时才可能出错）。
2. **命名规范**：Java 用驼峰 `maxTokens`，Python 用蛇形 `max_tokens`（PEP 8 强制）。
3. **没有常量**：约定全大写 `API_KEY` 表示"别改它"，但语言本身不阻止。

## 示例（用在 AI 项目里）

```python
model = "deepseek-chat"        # 模型名
api_base = "https://api.deepseek.com"   # API 地址
max_tokens = 1024              # 限制回复长度
temperature = 0.7              # 随机性 0~2
```

## 最小可运行 Demo

```python
# demo_variables.py
question = "什么是 Embedding？"
print("用户问题:", question)

# 动态类型演示：同一变量可以换类型（Java 里不可能）
x = 100
print(x, type(x))
x = "一百"
print(x, type(x))
```

运行：`python3 demo_variables.py`

## 常见错误

1. **拼写不一致**：`max_tokens` 和 `maxTokens` 是两个变量，Python 不会报"未定义字段"，只会报 `NameError`。
2. **先使用后赋值**：`print(count)` 在 `count = 0` 之前 → `NameError: name 'count' is not defined`。
3. **试图写常量**：`PI = 3.14; PI = 3` 合法但不规范——全大写就是给人看的约定。

## 常见面试问题
- Python 是强类型还是弱类型？→ **强类型 + 动态类型**：`"1" + 1` 会直接 TypeError（强），但变量类型可变（动态）。

## 练习
1. 定义你的名字、城市、目标三个变量并打印。
2. 验证 `"1" + 1` 会报什么错（体验强类型）。
3. 把 Java 风格的 `String userName` 改写成 Python 规范命名。

[下一课：03-types →](03-types.md)
