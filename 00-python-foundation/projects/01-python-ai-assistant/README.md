# Project 01 — Python AI CLI Assistant

> Phase 0 的主线项目。贯穿整个 Python Foundation 阶段，每学一课就升级一版。

## 项目定位

这是整个 AI Engineer Journey 的第一个项目。从最简单的输入输出开始，
随着 Python 知识积累，逐步升级成完整的命令行 AI 助手。

复杂度自然增长：

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

## 版本路线

| 版本 | 功能 | 依赖课程 |
|------|------|----------|
| v0.1 | 单轮输入输出 | Lesson 01 变量 / 类型 / input / print |
| v0.2 | list / dict 管理消息 | Lesson 02 list / dict / messages |
| v0.3 | 连续对话 | Lesson 03 条件与循环 |
| v0.4 | 函数封装 | Lesson 04 function |
| v0.5 | 模块拆分 | Lesson 05 module / package |
| v0.6 | 配置管理 | Lesson 13 config / env |
| v0.7 | 异常处理 | Lesson 07 exception |
| v0.8 | 文件 / JSON | Lesson 08 file / json |
| v0.9 | API / HTTP | Lesson 10 http / api |
| v1.0 | 完整 Python AI CLI Assistant | 全部 |

> 当前只建立骨架，不提前实现 v1.0。

## 当前结构

```text
01-python-ai-assistant/
├── README.md
└── src/
    └── main.py
```

## 运行

```bash
cd 00-python-foundation/projects/01-python-ai-assistant
python src/main.py
```

## 学习目标

- 把每个 Python 知识点立刻用到一个真实项目上
- 理解"复杂度自然增长"：从 script 到 application
- 最终看懂一次完整的 LLM API 调用链路

## 参考

仓库根目录 `projects/01-python-ai-assistant/` 有一个更完整的参考实现
（已实现真实 DeepSeek API 调用），可作为学习对照。
本目录是随课程逐步搭建的学习版本。
