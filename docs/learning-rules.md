# Learning Rules — 学习规则

> 本文件是 AI Engineer Journey 的长期学习规范。每学一个新知识点，按此规范执行。

## 1. 学习闭环

```text
阅读 lesson.md
 ↓
手敲 demo.py 运行
 ↓
做 exercises 练习
 ↓
记录错题到 mistakes/
 ↓
更新 PROGRESS.md / KNOWLEDGE-MAP.md
 ↓
（可选）沉淀文章到 content/articles/
```

## 2. 不允许知识跳跃

严格按依赖顺序推进。学新知识前，先在 KNOWLEDGE-MAP.md 确认前置节点已掌握。

## 3. 不假装学会

代码生成 ≠ 掌握。每课必须有：

```text
讲解 → Demo → 练习 → 我的答案 → 检查
```

## 4. 每章统一文件规范

```text
NN-topic/
├── README.md     # 本章入口
├── lesson.md     # 完整教学
└── demo.py       # 最小可运行代码
```

如果 Demo 较多：

```text
demo/
├── 01_xxx.py
├── 02_xxx.py
└── 03_xxx.py
```

不要把复杂项目代码放进 lesson 目录。

## 5. 每完成一章，必须同步更新

```text
lesson
demo
exercise
PROGRESS.md
KNOWLEDGE-MAP.md
```

如果这一章产生文章：

```text
content/articles/
```

如果产生项目代码：

```text
projects/
```

## 6. 练习原则

```text
基础题 → 理解题 → 代码题 → 项目题
```

不要只做选择题。

## 7. 主动回忆

每课结尾必须有「主动回忆」环节：不看教程，自己回答 3-5 个问题。

## 8. 错题本格式

```text
问题
我的错误答案
为什么错
正确理解
代码示例
如何避免
复习时间
```

## 9. 复杂度自然增长

```text
script
 ↓
function
 ↓
module
 ↓
package
 ↓
application
 ↓
AI service
```

不要提前引入 FastAPI / LangChain / PyTorch / 数据库 / RAG / Agent。
让复杂度随学习进度自然增长。
