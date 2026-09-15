# 01 — Installation：安装 Python

## 它是什么
Python 解释器是把 `.py` 源码翻译成机器动作的程序。类比 Java：写 `.java` 要先装 JDK，写 `.py` 要先装 Python。

## 为什么需要它
没有解释器，任何 Python 代码都跑不起来。它是整条 AI Engineer 路线的第一块地基。

## Java 开发者如何理解
| Java | Python |
|------|--------|
| JDK | Python 解释器 |
| `java -version` | `python3 --version` |
| `javac` 编译成 .class | 无需单独编译，直接解释执行（但有 .pyc 字节码缓存） |

> 注意：Python 不是"没有编译"，而是把编译步骤隐藏了。这与 Java 的机制不完全相同。

## 安装与验证

macOS 推荐用 [Homebrew](https://brew.sh)：

```bash
brew install python@3.12
python3 --version   # Python 3.12.x
```

Windows：去 [python.org](https://www.python.org/downloads/) 下载安装包，**勾选 "Add Python to PATH"**。

## 最小可运行 Demo

新建 `hello.py`：

```python
print("Hello, AI Engineer Journey!")
```

运行：

```bash
python3 hello.py
```

也可以交互式尝试（相当于 Java 的 jshell）：

```bash
python3
>>> 1 + 1
2
>>> exit()
```

## 常见错误

1. **`command not found: python`**：macOS 只有 `python3` 命令，没有 `python`。
2. **版本太老**：`python3 --version` 低于 3.9 会影响后续 AI 库（很多要求 3.10+）。
3. **Windows 忘了加 PATH**：重装并勾选 Add to PATH。

## 练习

1. 输出你的 Python 版本号。
2. 交互模式下计算 `1024 * 768`。
3. 写 `hello.py` 打印三行自我介绍，运行成功。

[下一课：02-variables →](02-variables.md)
