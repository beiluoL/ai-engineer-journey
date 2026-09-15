# 12 — Exception：异常

## 它是什么
运行时错误的处理机制。语法和 Java 几乎一致，但 Python **没有受检异常（checked exception）**——没有人强迫你处理。

## Java 开发者如何理解

```java
// Java
try { ... } catch (IOException | InterruptedException e) {
    throw new RuntimeException("调用失败", e);
} finally { ... }
```

```python
# Python —— catch → except，throws 不存在
try:
    ...
except (TimeoutError, ConnectionError) as e:
    raise RuntimeError("调用失败") from e
finally:
    ...
```

**关键差异**：
1. 没有受检异常：方法签名不声明异常，调用者不处理也不编译报错——**自律全靠自觉**，所以 AI 项目里要主动 try/except 包住所有网络调用。
2. 异常类都自带 `e` 消息，打印 `e` 即可（Java 的 `e.getMessage()` ≈ `str(e)`）。
3. `raise` = Java 的 `throw`。

## 自定义异常（项目规范做法）

```python
class LLMError(Exception):
    """LLM 调用相关错误的基类。"""

class LLMAuthError(LLMError):
    """API Key 无效（401）。"""

class LLMRateLimitError(LLMError):
    """触发限流（429），应重试。"""
```

## 最小可运行 Demo

```python
# demo_exception.py —— API 调用的错误处理骨架（v0.7 的原型）
import random

class LLMError(Exception): ...
class LLMRateLimitError(LLMError): ...

def call_api(attempt_fail: bool) -> str:
    if random.random() < 0.5 or attempt_fail:
        raise LLMRateLimitError("429 Too Many Requests")
    return "模型回答"

def ask_with_retry(question: str, max_retries: int = 3) -> str:
    last_err: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            return call_api(attempt_fail=False)
        except LLMRateLimitError as e:
            last_err = e
            print(f"第 {attempt} 次限流：{e}，等待后重试...")
        except LLMError as e:                     # 子类 except 要放在父类前面
            raise
    raise LLMError(f"重试 {max_retries} 次仍失败") from last_err

print(ask_with_retry("hi"))
```

## 常见错误

1. **裸 `except:`**：会吞掉一切（包括 Ctrl+C 的 KeyboardInterrupt）——最低限度写 `except Exception:`。
2. **吞异常不记录**：`except: pass` 是事故之源，至少 `print(e)` 或记日志。
3. **父类 except 放前面**：`except LLMError` 在 `except LLMRateLimitError` 之前会让后者永远匹配不到。
4. **在 except 里 return 中断重试**：小心逻辑，重试循环里 except 后应继续循环。
5. **忘记 raise 原因链**：包异常时用 `raise NewError(...) from e` 保留原始堆栈（同 Java 的 cause）。

## 常见面试问题
- Python 有 checked exception 吗？→ 没有，所有异常都类似 Java 的 unchecked。
- `else` 子句在 try 里干嘛？→ 无异常时执行；`finally` 则无论有无异常都执行（清理资源）。

## 练习
1. 定义自己的异常层级：`AppError` → `ConfigError` / `NetworkError`。
2. 写一个"最多重试 3 次，每次失败打印原因"的函数。
3. 故意触发 `KeyError` 和 `TypeError`，用 try/except 捕获并打印。

[下一课：13-file →](13-file.md)
