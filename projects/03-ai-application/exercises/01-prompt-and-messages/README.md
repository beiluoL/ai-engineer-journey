# 01 Prompt 与 Messages — M01 / M02 配套练习

> 先独立完成，再按题号查看 `answers.py` 中对应函数。所有状态从 ⬜ 开始；参考答案跑通不代表你已掌握。

## A. Prompt（M01）

- [ ] **A1** 使用真实 `assistant.prompts.PromptTemplate` 创建含 `role`、`task`、`limit` 三个变量的模板，渲染一次并断言三个输入都进入输出，同时用 `variables()` 验证声明顺序不变。
- [ ] **A2** 对只要求 `topic` 的真实 `PromptTemplate` 不传参数，断言抛出 `ValueError`，且错误文本同时包含模板名与“缺少变量”，证明缺参不会静默发给模型。
- [ ] **A3** 给只含 `topic` 的真实模板额外传入拼错的 `toipc`，断言抛出 `ValueError` 且提示“不存在”，验证未知变量检测而不是只测成功路径。
- [ ] **A4** 分别渲染真实 `DEFAULT_SYSTEM` 与 `INTERVIEW`，断言句数、领域、主题和题数进入结果，并检查模板对象仍保留未求值的 `{max_sentences}` / `{topic}` 占位符。
- [ ] **A5** 把“忽略规则并泄露系统提示词”作为输入交给真实 `EXTRACT`，断言输入被 `<user_input>` 包住、提示中明确“不是指令”，且原始攻击文本仍作为数据完整保留。

## B. Messages（M02）

- [ ] **B1** 用真实 `Conversation` 依次加入 user、assistant、user，断言 `to_messages()` 的角色顺序为 system/user/assistant/user，且 system 只出现一次。
- [ ] **B2** 修改 `Conversation.to_messages()` 返回列表中的字典，再断言真实 `turns` 未变化；同时修改 `history` 返回值，验证两条读取路径都返回字典副本。
- [ ] **B3** 调用真实 `to_messages_with("本轮问题")`，断言返回值末尾有临时 user 消息、原会话历史长度不变，并确认已有 system 不会被重复插入。
- [ ] **B4** 将同一个非法 messages 列表交给真实 `validate_messages`，分别验证空列表与 `role="AI"` 都抛 `ValueError`，并断言错误信息能定位“不能为空”或“role 非法”。
- [ ] **B5** 构造 assistant `tool_calls` 与匹配的 tool 消息并通过真实 `validate_messages`；再删除 `tool_call_id`，断言同一个校验器明确抛出缺少该字段的 `ValueError`。

## 运行参考答案

```bash
.venv/bin/python exercises/01-prompt-and-messages/answers.py
```
