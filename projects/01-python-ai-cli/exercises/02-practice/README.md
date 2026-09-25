# Exercises 02-practice — Milestone 03-06 配套练习

> 对应：`03-condition-loop.md` · `04-function.md` · `05-module-package.md` · `06-exception.md`
> 状态：⬜ 题目已播种，未开始做。做到哪题就把前面的 `- [ ]` 改成 `- [x]`。
> 规则同 01：**亲手敲，不复制粘贴**。写完的代码放本目录（如 `03_answers.py`）。

---

## C. 条件与循环（Milestone 03）

- [ ] **C1** 写 `guess_number(answer, guess)`：返回 `"大了" / "小了" / "猜对了"` 三选一（用 `if / elif / else`）
- [ ] **C2** 遍历 `messages` 列表，只打印 `role == "user"` 的 content（用 `for ... in`）
- [ ] **C3** 用 `while` 写一个「一直问，直到输入 quit 才退出」的循环，注意别写成死循环
- [ ] **C4** 对比 `range(5)`、`list(range(5))`、`enumerate(["a","b"])` 各自打印什么；用 `enumerate` 重写 C2，把序号一起打印
- [ ] **C5（挑战）** 用列表推导式把 `["1","2","3"]` 转成 `[1,2,3]`，再写出等价的普通 for 版本，体会两者的可读性差异

> Java 类比：`for x in list` ≈ 增强 for；Python 没有 `for(int i=0;...)`，要下标就用 `enumerate`。

## D. 函数（Milestone 04）

- [ ] **D1** 写 `add(a, b=1)`，分别用 `add(3)` 和 `add(3, 5)` 调用，观察默认参数
- [ ] **D2** 写 `sum_all(*nums)`，接收任意个数字并返回总和（可变参数）
- [ ] **D3** 故意踩坑：写 `def bad(items=[]): items.append(1); return items`，连续调用 3 次看结果，然后解释为什么（提示：默认参数只求值一次）
- [ ] **D4** 写 `divide(a, b)`，用类型注解 `-> float`，并用 `help(divide)` 看注解是否显示
- [ ] **D5（挑战）** 写一个 `retry(func, times)`：把任意函数包一层，失败就重试 N 次（函数当参数传，Java 里要靠接口/Lambda）

## E. 模块与包（Milestone 05）

- [ ] **E1** 在本目录建 `mymath.py`（放一个 `square(n)`），再从另一个文件 `import mymath` 调用它
- [ ] **E2** 建包 `tools/`（含 `__init__.py`、`tools/strutil.py`、`tools/numutil.py`），从外部 `from tools import strutil` 调用
- [ ] **E3** 在 `mymath.py` 底部加 `if __name__ == "__main__":` 自测代码，分别「直接运行」和「被 import」两种方式跑，观察区别
- [ ] **E4** 故意漏写 `__init__.py`，看报什么错；再补回来（Python 3 的命名空间包能 import，但显式写更稳）
- [ ] **E5（挑战）** 对照 `projects/01-python-ai-cli/src/assistant/` 这个真实包，画出它的模块依赖关系，说明 `__init__.py` 在这里承担什么职责

## F. 异常（Milestone 06）

- [ ] **F1** 触发并捕获三种异常：`ZeroDivisionError` / `KeyError` / `FileNotFoundError`，各自打印友好提示
- [ ] **F2** 写 `safe_divide(a, b)`：失败时返回 `None` 而不是抛异常，并说明什么时候该返回 None、什么时候该抛
- [ ] **F3** 用 `try / except / else / finally` 完整四段写一遍文件读取，观察 `finally` 在异常时是否仍执行
- [ ] **F4** 自定义异常 `class ConfigError(Exception)`，在「配置缺 key」时抛出，并在调用方捕获
- [ ] **F5（挑战）** 读 `projects/01-python-ai-cli/src/assistant/errors.py`，说明它定义的异常层级（基类 → 子类）是怎么设计的，为什么这么分层

---

## 验收标准

C1-C4 + D1-D4 + E1-E4 + F1-F4 全部亲手跑通 = Milestone 03-06 可标记 🎓。
C5 / D5 / E5 / F5 是思考题，做不出来先跳过，回头再补。
