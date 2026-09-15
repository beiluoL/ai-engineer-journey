# mistakes/ — 错题本

> 格式固定：问题 / 我的错误答案 / 为什么错 / 正确理解 / 代码示例 / 如何避免 / 复习时间。
> 目标不是"看懂"，是"不再错"。每次练习或写代码踩坑后，立即新增一条。

## 文件命名

```text
2026-09-15-包导出遗漏导致ImportError.md
YYYY-MM-DD-关键词.md
```

## 第一条（真实踩坑，初始化项目时记录）

```text
问题：python main.py 报 ImportError: cannot import name 'LLMConfigError' from 'assistant'
我的错误答案：以为异常定义在 errors.py 里就能直接 from assistant import 用
为什么错：包的 __init__.py 里没有显式导出 LLMConfigError（只导出了另外三个异常）；
          单测直接从 assistant.errors 导入，恰好绕过了包出口，所以测试没拦住
正确理解：from package import X 只能拿到 __init__.py 里可见的名字；
          测试路径和真实使用路径不同，覆盖面就不同
代码示例：__init__.py 需写全
          from assistant.errors import (LLMAuthError, LLMConfigError, LLMError,
                                        LLMRateLimitError, LLMResponseError)
如何避免：①__all__ 与异常定义保持同步；②测试要 import 包出口而非深路径
复习时间：2026-09-22
```
