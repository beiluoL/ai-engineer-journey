# 17 — pip：包管理

## 它是什么
Python 的包管理器，相当于 Java 的 Maven/Gradle 负责依赖的部分。PyPI（pypi.org）= Maven Central。

## Java 开发者如何理解

| Maven | pip |
|-------|-----|
| `pom.xml` | `requirements.txt` |
| `mvn install` | `pip install -r requirements.txt` |
| `mvn dependency:tree` | `pip list` / `pip show <pkg>` |
| Maven Central | PyPI |
| `<dependency>` 坐标 | `包名==版本` |

## 核心命令（venv 激活状态下）

```bash
pip install requests                     # 安装最新版
pip install "requests==2.31.0"           # 锁定版本（教学项目推荐，保证可复现）
pip install "requests>=2.31,<3"          # 范围约束
pip install python-dotenv                # 读 .env 的官方常用库

pip list                                 # 已装了什么
pip show requests                        # 版本/依赖/安装位置
pip freeze > requirements.txt            # 导出当前环境全部依赖（精确版本）
pip install -r requirements.txt          # 按清单还原环境
pip uninstall requests
```

**freeze 与手写 requirements 的区别**：`pip freeze` 导出的是完整依赖树（连依赖的依赖），适合锁定环境；教学项目建议手写直接依赖 + 主版本锁定，语义更清晰。

## 最小可运行 Demo

```bash
# 在 Project 01 目录下
source .venv/bin/activate        # 先激活（没建过就 python3 -m venv .venv && source .venv/bin/activate）
pip install python-dotenv
pip list | grep dotenv
python -c "from dotenv import load_dotenv; print('python-dotenv 可用')"

# requirements.txt 内容示例（v0.1 其实零依赖；引入 dotenv 后才需要它）
# python-dotenv==1.0.1
```

## 本仓库的版本管理原则

1. **不追新**：教学代码在写明版本的环境里验证过才可复现，核心依赖记录"用哪个版本 + 为什么"。
2. **重大 API 变更时更新教程**，而不是悄悄让旧代码失效。
3. 项目 01 v0.1 刻意**零第三方依赖**（标准库 urllib 直连 API），让你先看清 HTTP 调用的本质，Phase 1 再引入 `requests` / `httpx`，并回答"框架替我们解决了什么"。

## 常见错误

1. **pip 装到全局/错环境**：装之前确认激活了 venv（`which pip` 应指向 `.venv/bin/pip`）。养成 `python -m pip install` 的习惯更保险。
2. **Network 报错/超时**：国内可换镜像 `pip install -i https://pypi.tuna.tsinghua.edu.cn/simple <pkg>`。
3. **requirements.txt 忘记更新**：本地能跑、别人 clone 后跑不起来——装新包后随手 freeze 或手写补录。
4. **把构建工具当运行依赖**：`pip install -r requirements.txt` 用于运行环境，开发工具（pytest、mypy）可另放 `requirements-dev.txt`。

## 常见面试问题
- pip、pip3 区别？→ pip3 绑定 Python 3；用 `python -m pip` 最明确。
- venv 里删掉 .venv 会怎样？→ 依赖全没，靠 requirements.txt 一条命令重建——所以清单必须及时维护。

## 练习
1. 在 venv 里安装 python-dotenv 并用 `pip show` 查看信息。
2. freeze 导出 requirements.txt，删掉 .venv 重建后用清单还原。
3. 给 Project 01 写 requirements-dev.txt（先只放 `pytest`，v0.9 用）。

---

**Phase 0 课程全部完成。** 回到 Project 01：阅读 `projects/01-python-ai-assistant/main.py`，
把 02~15 课的知识点逐一对号入座，然后做 `exercises/phase-0/` 练习巩固。
