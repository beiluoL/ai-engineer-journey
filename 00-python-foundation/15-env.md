# 15 — Env：环境变量与 .env

## 它是什么
操作系统级的配置传递机制。**API Key 的唯一正确存放位置**——绝不写进代码、不提交 git。

## 为什么需要它
Project 01 要调 DeepSeek API。Key 写死在代码里 = 只要代码进过 git，Key 就算永久泄漏（历史提交里都能翻出来）。

## Java 开发者如何理解

```java
// Java
String key = System.getenv("DEEPSEEK_API_KEY");   // 环境变量
// Spring 里: @Value("${DEEPSEEK_API_KEY}") 或 application.yml
```

```python
# Python 标准库 os
import os
key = os.environ.get("DEEPSEEK_API_KEY")   # 不存在返回 None（不抛异常，推荐）
key = os.environ["DEEPSEEK_API_KEY"]       # 不存在抛 KeyError
```

## .env 文件约定

`.env` 放本地真实密钥；`.env.example` 放模板提交 git：

```bash
# .env.example （提交到 git）
DEEPSEEK_API_KEY=your-api-key-here
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEFAULT_MODEL=deepseek-chat
```

```bash
# .env （gitignore，永不提交）
DEEPSEEK_API_KEY=sk-真实密钥
```

程序读取 `.env`：Phase 0 用最朴素的方式（或引入 `python-dotenv`，见 17-pip）。设置环境变量也可以直接：

```bash
export DEEPSEEK_API_KEY="sk-xxx"    # 当前终端有效
python main.py
```

## 最小可运行 Demo

```python
# demo_env.py —— Project 01 config.py 的原型
import os

def get_api_key() -> str:
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        raise RuntimeError(
            "未找到 DEEPSEEK_API_KEY。\n"
            "请设置环境变量: export DEEPSEEK_API_KEY='sk-...'\n"
            "或复制 .env.example 为 .env 并填入真实 Key。"
        )
    return key

if __name__ == "__main__":
    try:
        key = get_api_key()
        print(f"Key 已加载（长度 {len(key)}，前缀 {key[:3]}***）")  # 只打印掩码，绝不打印完整 Key
    except RuntimeError as e:
        print(e)
```

## 安全红线（本仓库硬规则）

1. ❌ Key 写进代码 / README / 注释 / 日志
2. ❌ `.env` 提交 git（`.gitignore` 必须含 `.env`）
3. ❌ 打印完整 Key（日志只允许打长度/前缀掩码）
4. ✅ 泄漏应急：立刻在服务商后台吊销重发，而不是删除代码里的 Key

## 常见错误

1. **export 了但程序读不到**：export 只对当前终端有效，换终端/IDE 运行要重新设置；或 IDE 运行配置里没配环境变量。
2. **`.env` 放错位置**：必须在运行目录或明确指定路径。
3. **`.env.example` 也放了真 Key**：模板里只允许占位符。
4. **以为 .gitignore 能救已提交的 Key**：不能，git 历史里还在，必须吊销重发。

## 练习
1. export 一个测试变量并用 Python 读取。
2. 创建 `.env.example` 和（本地的）`.env`，确认 `git status` 看不到 `.env`。
3. 运行 demo_env.py，验证无 Key 时的友好报错。

[下一课：16-venv →](16-venv.md)
