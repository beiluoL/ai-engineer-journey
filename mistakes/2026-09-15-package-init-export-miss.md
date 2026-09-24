# 包 `__init__.py` 漏导出异常类：单测全绿，运行即炸

> 状态：已复盘 · 关联：Project 01 `assistant` 包

## 问题

给 Project 01 写配置加载与异常体系后，运行 `python main.py "测试"` 验证无 Key 时的友好报错。

## 我的错误答案 / 做法与现象

单元测试 6 个全部通过，但一运行 `main.py` 就抛：

```text
ImportError: cannot import name 'LLMConfigError' from 'assistant.errors'
```

奇怪点：`tests/test_all.py` 明明测过配置加载路径，为什么测试是绿的？

## 为什么错

`assistant/__init__.py` 的 `__all__` 与 import 列表里**漏了 `LLMConfigError`**（只导出了 `LLMAuthError` / `LLMRateLimitError` 等）。

而单元测试全部从**深层路径**导入：

```python
from assistant.errors import LLMConfigError   # 绕过了包的 __init__
```

这条导入路径不经过 `assistant/__init__.py` 的导出清单，所以漏导出对测试不可见；
`main.py` 走的是使用路径 `from assistant import ...`，一跑就炸。

## 正确理解

**测试通过 ≠ 没有 bug。测试的导入路径和使用者的导入路径可能不同。**
包的 `__init__.py` 是一份「公共 API 承诺」，`__all__` 漏一项，承诺就缺一块——
而测试如果绕过这份承诺，就等于没测它。

## 代码示例

```python
# 错：__all__ 缺 LLMConfigError
__all__ = ["Config", "load_config", "LLMClient", "LLMError", "LLMAuthError", "LLMRateLimitError"]

# 对：与 errors.py 的定义清单一一对应
__all__ = ["Config", "load_config", "LLMClient", "LLMError", "LLMConfigError",
           "LLMAuthError", "LLMRateLimitError", "LLMResponseError"]
```

修好后再跑测试无效——必须**按使用路径冒烟**：

```bash
python main.py "测试"   # 走 from assistant import ... 的真实路径
```

## 如何避免

- 新增公共类/函数后，`__init__.py` 的 import + `__all__` 同步更新（当成一个原子动作）
- 单测之外永远保留一条「使用路径冒烟」：`python main.py` 实跑一次再提交
- 让 AI 审查代码时加一条固定检查项：**测试路径与使用路径是否一致**

## 复习时间

- [ ] 3 天后（2026-09-18）
- [ ] 2 周后（2026-09-29）
- [ ] 2 个月后（2026-11-15）
