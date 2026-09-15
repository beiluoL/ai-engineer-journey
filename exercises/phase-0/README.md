# exercises/phase-0 — 练习体系

> 教程看懂 ≠ 掌握。每个课程都有练习，答案写在对应目录后自查或让 AI 检查。

## 目录约定

```text
01-basic      基础题：语法直接对应课程 Demo
02-practice   综合题：多个知识点组合
03-project    项目题：为 Project 01 写真实小功能
04-challenge  挑战题：开放性思考
```

## 第一批任务（做完再进 Phase 1）

| 来源课程 | 任务 | 放置位置 |
|----------|------|----------|
| 02-variables / 03-types | 打印 5 种类型变量 + 类型转换 | 01-basic/ex_02_03.py |
| 05-list | 模拟 3 轮对话 history 并遍历 | 01-basic/ex_05.py |
| 06-dict | 构造完整 LLM 请求体 dict | 02-practice/ex_06.py |
| 09-function | 写 build_payload 并解包元组返回 | 02-practice/ex_09.py |
| 12-exception | 自定义异常层级 + 3 次重试 | 03-project/ex_12.py |
| 15-env | 实现带掩码打印的 get_api_key | 03-project/ex_15.py |

挑战题（04-challenge）：不运行代码，肉眼推断 Project 01 `client.py` 的 `ask()` 在
Key 错误 / 断网 / 响应缺字段三种情况下分别抛什么异常，再实际验证。
