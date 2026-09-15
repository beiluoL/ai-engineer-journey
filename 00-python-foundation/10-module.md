# 10 — Module：模块与包

## 它是什么
`.py` 文件就是模块（module），带 `__init__.py` 的目录就是包（package）。类比 Java：模块 ≈ 单个 .java 文件中的类，包 ≈ Java package。

## 为什么需要它
Project 01 不会把所有代码塞进 main.py——client、config 分文件管理，这就是模块化。

## Java 开发者如何理解

```text
Java:  com.example.ai.LLMClient  →  src/com/example/ai/LLMClient.java
Python:  assistant.client.LLMClient  →  assistant/client.py
```

差异：Python 一个文件可含多个类/函数（Java 一个文件只能一个 public 类）；导入粒度更自由。

## 导入语法

```python
import json                        # 标准库整包导入
import urllib.request              # 带子模块
from json import dumps             # 只导入某个名字，Java: import static
from assistant.client import LLMClient   # 从自己的包导入
from assistant import config       # 导入子模块

import numpy as np                 # 别名惯例
```

**查找顺序**：先当前目录 → 再 `PYTHONPATH` → 再标准库 → 再 site-packages。所以别把自己的文件命名成 `json.py`、`request.py`——会遮蔽标准库！

## `__init__.py`

包的"入口标记"，可以留空，也可以控制对外暴露：

```python
# assistant/__init__.py
from assistant.client import LLMClient   # 让外部能 from assistant import LLMClient
__all__ = ["LLMClient"]
```

## 最小可运行 Demo

```text
demo_pkg/
├── main.py
└── tools/
    ├── __init__.py
    └── greet.py
```

```python
# tools/greet.py
def greet(name: str) -> str:
    return f"Hello, {name}!"
```

```python
# main.py
from tools.greet import greet
print(greet("AI Engineer"))
```

运行：`python3 main.py`（注意要在 demo_pkg 目录下运行）。

Project 01 的真实结构就是按这个模式组织的：

```text
projects/01-python-ai-assistant/
├── main.py               # 入口
└── assistant/
    ├── __init__.py
    ├── config.py          # 读环境变量
    └── client.py          # LLMClient 类
```

## 常见错误

1. **ModuleNotFoundError**：在错误的目录运行，或忘了 `__init__.py`（旧版必需，3.3+ 可省但建议保留）。
2. **循环导入**：a.py 导入 b，b 又导入 a → 崩溃。重构公共部分到第三个模块。
3. **文件名遮蔽标准库**：自建 `json.py` 后 `import json` 导入的是自己的文件，报各种诡异错误。
4. **`__pycache__`**：Python 自动生成的字节码缓存，正常现象，加入 .gitignore 即可。

## 常见面试问题
- module 和 package 区别？→ module 是 .py 文件，package 是含 `__init__.py` 的目录。
- `if __name__ == "__main__":` 是什么？→ 直接运行该文件时 `__name__` 为 `"__main__"`，被导入时不成立——让文件既能当脚本跑又能被安全导入（相当于 Java 区分 main 方法和库类）。

## 练习
1. 建一个两文件小项目并互相导入成功。
2. 故意把文件命名成 `json.py` 观察遮蔽现象，然后改名修复。
3. 给 main.py 加上 `if __name__ == "__main__"` 保护。

[下一课：11-class →](11-class.md)
