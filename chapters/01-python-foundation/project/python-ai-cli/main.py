"""AI CLI Assistant —— Project 01 入口（v0.1 单轮问答）。

用法：
    python main.py                # 交互式输入一个问题
    python main.py "你的问题"     # 命令行参数直接提问

功能链路：
    输入问题 → 构造请求体 → 调用 DeepSeek API → 输出答案
"""

from __future__ import annotations

import sys

from assistant import LLMClient, LLMConfigError, LLMError, load_config


def main() -> int:
    # 命令行参数或交互输入
    question = " ".join(sys.argv[1:]).strip()
    if not question:
        try:
            question = input("你的问题: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n已取消。")
            return 0

    if not question:
        print("问题不能为空。")
        return 1

    try:
        config = load_config()
    except LLMConfigError as e:
        print(f"[配置错误]\n{e}")
        return 1

    client = LLMClient(config)

    print("思考中...")
    try:
        answer = client.ask(question)
    except LLMError as e:
        print(f"[调用失败] {e}")
        return 1
    except KeyboardInterrupt:
        print("\n已取消。")
        return 0

    print("\n" + "=" * 40)
    print(answer)
    print("=" * 40)
    return 0


if __name__ == "__main__":
    sys.exit(main())
