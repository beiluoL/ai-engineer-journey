"""Milestone 03 实验：if / elif / else、for、while、break、continue。

配套文档: milestones/03-condition-loop.md

直接运行即可，不需要输入:
    python3 demos/03-condition-loop.py

第 3 节里为了方便演示，用列表假装"用户输入"，效果和你真的敲键盘一样。
"""

print("===== 1. if / elif / else：根据不同的分数给不同结果 =====")

for score in (95, 85, 70, 45):
    if score >= 90:
        level = "A（优秀）"
    elif score >= 80:
        level = "B（良好）"
    elif score >= 60:
        level = "C（及格）"
    else:
        level = "D（不及格）"

    print(f"分数 {score} -> {level}")

print("\n命令路由（AI CLI Assistant 里就是这么判断的）")

for command in ("/exit", "/help", "你好"):
    if command == "/exit":
        print(f"收到 {command} -> 准备退出")
    elif command == "/help":
        print(f"收到 {command} -> 显示帮助")
    else:
        print(f"收到 {command} -> 当作普通消息")

print("\n===== 2. for：遍历列表、range、enumerate =====")

directions = ["Python", "LLM", "RAG", "Agent"]

for direction in directions:
    print(f"- {direction}")

for index in range(1, 4):          # 从 1 数到 3
    print(f"range(1, 4) 第 {index} 轮：index = {index}")

for no, direction in enumerate(directions, start=1):
    print(f"{no}. {direction}")

for role, content in {"user": "你好", "assistant": "在的"}.items():
    print(f"{role} -> {content}")

print("\n===== 3. while + break + continue：CLI 主循环 =====")

# 假装这是键盘输入，依次喂进来
inputs = ["/history", "你好", "", "  ", "/exit"]
messages = []

index = 0
while True:                        # 一直循环，直到 break
    user_input = inputs[index]
    index += 1

    print(f"\nYou: {user_input}")

    if user_input == "/exit":
        print("AI: 再见！")
        break                      # 直接跳出整个循环，程序结束

    if user_input == "/history":
        print("---------- Conversation ----------")
        for message in messages:
            print(f"{message['role']}: {message['content']}")
        print("---------------------------------")
        continue                   # 命令处理完了，不往下走，进入下一轮

    if not user_input.strip():
        print("AI: 空消息，跳过。")
        continue                   # 空消息也跳过

    messages.append({"role": "user", "content": user_input})
    print(f"AI: 已记录：{user_input}")

print(f"\n退出时 messages 里有 {len(messages)} 条消息")

print("\n===== 4. 小程序：统计这段话里的中英文和字符频率 =====")

TEXT = "Python 很有趣，python 也很实用；Python 第 3 天，python 第一天。"

print(f"文本：{TEXT}")
print()

zh_count = 0
en_count = 0
digit_count = 0
other_count = 0
freq = {}

index = 0
while index < len(TEXT):
    ch = TEXT[index]
    index += 1

    if ch.isspace():               # 空格不统计
        continue

    if ord(ch) > 127:              # 中文
        zh_count += 1
    elif ch.isalpha():             # 英文字母
        en_count += 1
    elif ch.isdigit():             # 数字
        digit_count += 1
    else:                          # 标点符号等其他字符
        other_count += 1

    freq[ch] = freq.get(ch, 0) + 1

print(f"中文字数   = {zh_count}")
print(f"英文字数   = {en_count}")
print(f"数字字符数 = {digit_count}")
print(f"标点等其他 = {other_count}")
print(f"合计（不含空格） = {zh_count + en_count + digit_count + other_count}")
print("注意：大小写算两个字符，所以 P 和 p 是分开统计的。")

top5 = sorted(freq.items(), key=lambda kv: kv[1], reverse=True)[:5]
print("\n出现最多的 5 个字符：")
for ch, times in top5:
    print(f"  {ch!r} 出现了 {times} 次")
