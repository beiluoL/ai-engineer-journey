# Exercises 04-challenge — Milestone 10 综合挑战

> 对应：`10-real-llm-api.md`（串起全部知识，完成 v1.0）
> 状态：⬜ 未开始。**先做完 01 / 02 / 03 三档再来**，这里是验收级任务，不是片段练习。
> 目标：把 `projects/01-python-ai-cli/` 做到真正可用的 v1.0，并能在简历里讲清楚。

---

## 挑战一：让 CLI 真的能聊天（必做）

- [ ] **X1** 接真实 LLM API：把 `src/assistant/client.py` 的调用跑通（Key 走环境变量，绝不写进代码）
- [ ] **X2** 支持多轮上下文：每轮把历史 messages 一起发，验证模型「记得」上一轮说了什么
- [ ] **X3** 支持流式输出：一个字一个字往外吐（打字机效果），而不是等全部返回
- [ ] **X4** 加命令行参数：`--model` / `--temperature` / `--max-tokens` / `--system`
- [ ] **X5** 会话存档接入：启动时 `--resume` 读回上次会话，`--new` 开新档

## 挑战二：把它做成一个能交代的工程（必做）

- [ ] **Y1** 补齐异常路径：网络超时、401 Key 无效、429 限流、响应缺字段，每种都要有友好提示而不是堆栈
- [ ] **Y2** 加 `logging`：区分 INFO / WARNING / ERROR，把请求耗时和 token 用量记下来
- [ ] **Y3** 测试覆盖到 80%：client / config / history 三条主链路都要有测试，`unittest discover` 全绿
- [ ] **Y4** 写一份 README 级别的「使用说明」：安装 → 配 Key → 跑起来 → 常见问题
- [ ] **Y5** 把踩过的坑写进 `mistakes/`：至少 3 条真实记录（日期 + 现象 + 原因 + 修复）

## 挑战三：往简历里搬（选做但建议做）

- [ ] **Z1** 能口述这个项目：从「零依赖调 LLM」讲到「异常分层 / 配置外置 / 会话持久化」
- [ ] **Z2** 准备 3 个面试追问：「为什么不用 requests」「异常为什么要分层」「Key 为什么不能入库」
- [ ] **Z3** 把它打包成可 pip 安装的形式（Milestone 08 + Project 02 的 packaging 内容）

---

## 验收标准（v1.0 定义）

X1-X5 + Y1-Y5 全部完成，且 `python3 -m unittest discover -s tests` 全绿 = **Project 01 毕业**。
此时在 `PROGRESS.md` 里把 Project 01 从 🔄 改成 ✅，并开工 Project 02（工程化改造）。

> 铁律：文档读完 ≠ 学会。X 系列必须**亲手跑通真实 API**才算数。
