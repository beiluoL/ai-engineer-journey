# 16 — venv：虚拟环境

## 它是什么
每个项目独立的 Python 环境（独立解释器链接 + 独立第三方包目录），互不污染。

## 为什么需要它
项目 A 要 `requests==2.31`，项目 B 要 `2.32`——没有隔离就互相覆盖（Java 用 Maven 按项目隔离，Python 靠 venv）。

## Java 开发者如何理解

| Maven | venv |
|-------|------|
| 项目级 `pom.xml` 依赖 | 项目级 `.venv/` 目录 |
| `~/.m2` 全局仓库 | venv 内 `site-packages`（随 venv 走） |
| JDK 版本切换 | 可指定不同 Python 版本创建 venv |

差异：Maven 依赖是"声明 + 全局仓库缓存"，venv 是"每个项目真实拷贝一份"。

## 核心命令

```bash
# 创建（在项目根目录执行，会生成 .venv/ 目录）
python3 -m venv .venv

# 激活 —— macOS/Linux
source .venv/bin/activate
# 激活 —— Windows PowerShell
.venv\Scripts\Activate.ps1

# 激活后：python 和 pip 都指向 venv 内的
which python      # .../.venv/bin/python
python --version

# 退出
deactivate
```

**识别标志**：激活后命令行前面出现 `(.venv)` 前缀。

`.venv/` **必须加入 .gitignore**（本仓库已配置）——它是本机环境产物，不属于代码。

## 最小可运行 Demo

```bash
# 一步步来
mkdir venv-demo && cd venv-demo
python3 -m venv .venv
source .venv/bin/activate

python -c "import sys; print(sys.executable)"   # 确认指向 .venv 内
pip list                                        # 只有基础包，干干净净
deactivate
python -c "import sys; print(sys.executable)"   # 退回系统 Python
```

## 常见错误

1. **激活了 venv 却用绝对路径 python**：`/usr/bin/python3 main.py` 用的是系统解释器，包全装错地方。激活后直接用 `python`。
2. **把 .venv 提交了 git**：几十 MB 垃圾进仓库，`.gitignore` 加 `.venv/`。
3. **删除项目目录忘了 venv 还挂着**：终端里的激活失效，重新 source 即可。
4. **以为 venv 改 Python 版本**：venv 基于**创建时**的解释器版本，要 3.12 就用 `python3.12 -m venv .venv`。

## 常见面试问题
- venv 和 conda 区别？→ venv 只管 Python 包；conda 是跨语言环境管理器，还能换 Python 本身版本、装 CUDA 相关二进制。教学路线先用 venv + pip。
- 为什么 AI 项目必须用 venv？→ torch/transformers 依赖树巨大且版本敏感，不隔离几乎必然版本冲突。

## 练习
1. 给 venv-demo 创建并激活 venv，确认 `sys.executable` 指向 .venv。
2. 确认 `.venv` 被 git 忽略（`git status` 干净）。
3. deactivate 后再打印 `sys.executable` 对比。

[下一课：17-pip →](17-pip.md)
