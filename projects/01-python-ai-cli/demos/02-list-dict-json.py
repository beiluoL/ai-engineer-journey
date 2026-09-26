"""Milestone 02 实验：List / Dict / 列表推导式 / JSON / AI messages。

配套文档: milestones/02-list-dict-json.md

直接运行即可，不需要输入:
    python3 demos/02-list-dict-json.py
"""

import json

print("===== 1. List：一个变量保存多个值 =====")

directions = ["Python", "LLM", "RAG", "Agent"]
print(f"directions = {directions}")
print(f"长度 len() = {len(directions)}")
print(f"下标 0 是 {directions[0]}，下标 -1 是 {directions[-1]}")

directions.append("Transformer")
print(f"append 之后 = {directions}")

print("\n===== 2. List 推导式：一行生成新列表 =====")

upper_names = [d.upper() for d in directions]
print(f"[d.upper() for d in directions] = {upper_names}")

short = [d for d in directions if len(d) <= 3]
print(f"[d for d in directions if len(d) <= 3] = {short}")

print("\n===== 3. Dict：一条数据里有多个字段 =====")

python_skill = {
    "name": "Python",
    "status": "学习中",
    "progress": 80,
}

print(f"python_skill = {python_skill}")
print(f'python_skill["name"]     = {python_skill["name"]}')
print(f'python_skill["progress"] = {python_skill["progress"]}')

# 直接取不存在的 key 会崩，.get() 更安全
print(f'python_skill.get("level")           = {python_skill.get("level")}')
print(f'python_skill.get("level", "未设置") = {python_skill.get("level", "未设置")}')
print(f'"status" 在不在里面？ {"status" in python_skill}')

print("\n===== 4. List + Dict：真正的结构化数据 =====")

skills = [
    {"name": "Python", "status": "学习中", "progress": 80},
    {"name": "LLM", "status": "学习中", "progress": 20},
    {"name": "RAG", "status": "未开始", "progress": 0},
]

print(f"skills[0]           = {skills[0]}")
print(f'skills[0]["name"]   = {skills[0]["name"]}')
print(f'skills[2]["name"]   = {skills[2]["name"]}')

total = sum(s["progress"] for s in skills)
print(f"所有技能进度之和 = {total}")

print("\n===== 5. AI messages：List + Dict 就是对话历史 =====")

messages = [
    {"role": "system", "content": "你是一名 Python 教师。"},
    {"role": "user", "content": "什么是 list？"},
    {"role": "assistant", "content": "list 是有顺序的一组数据。"},
    {"role": "user", "content": "它和 Java 的 List 类似吗？"},
]

for message in messages:
    print(f"{message['role']}: {message['content']}")

print("\n===== 6. json.dumps：Python 对象 -> JSON 字符串 =====")

json_text = json.dumps(messages, ensure_ascii=False, indent=2)
print(json_text)

print("\n===== 7. json.loads：JSON 字符串 -> 读回 Python 对象 =====")

loaded = json.loads(json_text)

print(f"读回来的类型 = {type(loaded).__name__}")
print(f"第 0 条消息 = {loaded[0]}")
print(f"读回来的第 3 条 role = {loaded[3]['role']}")
print(f"和原来一模一样吗？ {loaded == messages}")

print("\n===== 8. 不加 indent 的样子（对比用） =====")

print(json.dumps(messages, ensure_ascii=False))
print("上面是一整行；indent=2 会展开成前面那种好看的格式。")
print("真正写进文件用 json.dump()，读回文件用 json.load()，第 07 章会做。")
