# 03 Memory、Token、Tools 与应用架构 — M05 / M07 / M08 / M09 配套练习

> 先独立完成，再按题号查看 `answers.py` 中对应函数。所有状态从 ⬜ 开始；参考答案跑通不代表你已掌握。

## A. 会话记忆（M05）

- [ ] **A1** 用真实 `SessionStore` 创建 A/B 两个会话并写入不同偏好，断言内容互不串台、相同 session_id 返回同一对象；reset A 后再 get，断言 A 得到空的新会话而 B 不受影响。
- [ ] **A2** 给真实 `Conversation` 写入多轮长消息并以 user 消息收尾，调用 `trim_to_budget`，断言确实丢弃历史、system 仍在首位、最后一个 user 输入仍保留，并打印裁剪前后真实 token 数。
- [ ] **A3** 对真实 `Conversation.tokens()` 与 `estimate_messages_tokens(conv.to_messages())` 做同输入对比，断言结果完全一致；clear 后断言 turns 为空但 system 仍由 `to_messages()` 保留。

## B. Token / Context Window（M07）

- [ ] **B1** 对空串、纯中文、纯英文和中英混排分别调用真实 `estimate_tokens`，再按 `tokens.py` 的 CJK×0.9、其他字符÷3.5 规则独立计算并逐项断言一致，不能写死结果数字。
- [ ] **B2** 用真实 `estimate_messages_tokens` 证明完整 messages 的估值大于仅 content 的估值；再构造真实 `Budget(1000, 200, 0.5)`，断言 `history_budget` 与 ok/trim/overflow 三个边界判断。
- [ ] **B3** 用真实 `cost_cny` 对同样数量的输入与输出 token 分别计价，断言当前 `deepseek-chat` 输出成本更高、未知模型使用默认价格，并打印本次动态算出的费用。

## C. Function Calling（M08）

- [ ] **C1** 从真实 `schemas()` 找到 `add`，断言参数 `a/b` 都是 JSON Schema 的 number 且均 required；再注册一个带默认参数的临时工具，断言默认参数不会进入 required，最后清理注册表。
- [ ] **C2** 用真实 `dispatch` 验证 add 与 multiply 的计算结果；再分别传坏 JSON、缺参数和未知工具名，断言三种失败都返回含 `error` 的字典而不是向外抛异常。
- [ ] **C3** 用真实 `FakeClient` 编排一次 add 工具调用和最终回答，运行真实 `run_agent`，断言第二次请求包含 role=tool、`tool_call_id` 原样回灌、content 中是真实计算结果。
- [ ] **C4** 让真实 `FakeClient` 连续请求工具超过 `max_iterations=3`，断言真实 `run_agent` 抛 `ToolLoopError`，且客户端调用次数严格等于上限而不是继续循环。

## D. 应用架构（M09）

- [ ] **D1** 用真实 `build_service(Settings(...), FakeClient(...))` 注入模型替身，连续调用 `ask`，断言编排层返回替身答案、记录 usage 调用次数，并在第二次请求里带上第一次完整问答历史。
- [ ] **D2** 用真实 `create_app()`、依赖覆盖与 FastAPI `TestClient` 在进程内访问 `/health`、`/chat`、`/reset`，断言 HTTP 层复用注入的 service、空消息返回 422、reset 后指定会话历史为空且全程不启动端口。

## 运行参考答案

```bash
.venv/bin/python exercises/03-memory-tokens-tools/answers.py
```
