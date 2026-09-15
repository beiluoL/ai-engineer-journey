# 03 — Types：类型

## 它是什么
Python 内置类型：`int`、`float`、`str`、`bool`、`NoneType`。用 `type(x)` 查看，用 `int(x)` 转换。

## 为什么需要它
Project 01 里 `max_tokens=1024` 是 int，`temperature=0.7` 是 float，API Key 是 str——搞混类型程序就错。

## Java 开发者如何理解

| Java | Python | 差异 |
|------|--------|------|
| `int` / `long` | `int` | Python int **无限精度**，没有溢出 |
| `double` | `float` | 都是 IEEE 754 双精度，同样有 0.1+0.2 问题 |
| `String` | `str` | 都不可变 |
| `boolean` | `bool` | 注意：Python 的 `True/False` 首字母**大写** |
| `null` | `None` | `None` 是对象，判断用 `is None` 而不是 `==` |

## 示例（用在 AI 项目里）

```python
model: str = "deepseek-chat"     # 类型提示（仅提示，不强制）
max_tokens: int = 1024
temperature: float = 0.7
stream: bool = False
system_prompt: str | None = None  # 可能为 None
```

类型提示（type hints）像 Java 的声明类型，但**只在检查工具时有用，运行时不强制**——这是和 Java 最大的区别。

## 最小可运行 Demo

```python
# demo_types.py
print(type(1024), type(0.7), type("hi"), type(True), type(None))

# None 判断：用 is
system_prompt = None
if system_prompt is None:
    print("没有系统提示词，使用默认")

# 类型转换
n = int("42")        # Java: Integer.parseInt
f = float("0.5")     # Java: Double.parseDouble
s = str(1024)        # Java: String.valueOf
print(n + 1, f * 2, s + "!")

# 经典坑：0.1 + 0.2 != 0.3（和 Java 一样）
print(0.1 + 0.2 == 0.3)  # False
```

## 常见错误

1. **`true` 小写**：Python 必须是 `True`。
2. **用 `==` 判 None**：能用但不规范，标准写法 `x is None`。
3. **字符串和数字相加**：`"回复数: " + 5` → `TypeError`，必须 `"回复数: " + str(5)` 或用 f-string：`f"回复数: {5}"`。
4. **误信类型提示**：`def f(x: int)` 传 `"abc"` 运行时不报错，需要 mypy 等工具静态检查。

## 常见面试问题
- Python int 会溢出吗？→ 不会，无限精度；Java int 32 位会溢出。
- `is` 和 `==` 区别？→ `==` 比较值，`is` 比较身份（同一对象）。

## 练习
1. 用 `type()` 打印 5 种类型的变量。
2. 把 `"3.14"` 转成 float 并乘以 2。
3. 写一个值为 `None` 的变量并正确判断它。

[下一课：04-string →](04-string.md)
