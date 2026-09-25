# Exercises 03-project — Milestone 07-09 配套练习

> 对应：`07-file-json.md` · `08-venv-pip.md` · `09-http-api.md`
> 状态：⬜ 题目已播种，未开始做。
> 这一档不再是小片段，而是往 `projects/01-python-ai-cli/src/` 里真的加功能。
> 规则：每题都在**虚拟环境**里跑（Milestone 08 教的），写完记得跑一遍 `tests/test_all.py` 确认没把项目搞坏。

---

## G. 文件与 JSON 持久化（Milestone 07）

- [ ] **G1** 给 Assistant 加「会话存档」：把 `messages` 写进 `history.json`，下次启动自动读回继续聊
- [ ] **G2** 用 `pathlib.Path` 改写 G1 里的路径拼接（别再手动拼字符串），并把文件放到用户目录下而不是项目目录
- [ ] **G3** 处理三种坏情况：文件不存在 → 新建；文件是空 → 当作空列表；JSON 坏了 → 备份原文件后重建
- [ ] **G4** 写 `tests/test_history.py`：测「存进去再读出来一致」和「文件损坏时不崩溃」两条
- [ ] **G5（挑战）** 实现「按日期分文件存档」：`history/2026-09-25.json`，并列出最近 7 天的会话

> Java 类比：`pathlib.Path` ≈ `java.nio.file.Path`；`with open(...)` ≈ try-with-resources。

## H. venv / pip / 环境（Milestone 08）

- [ ] **H1** 从零建一个干净 venv：`python3 -m venv .venv && source .venv/bin/activate`，确认 `which python3` 指向 venv 里
- [ ] **H2** 用 `pip freeze > requirements.txt` 导出依赖，再在**另一个**新建的 venv 里 `pip install -r requirements.txt` 还原
- [ ] **H3** 故意在系统 Python 里跑项目（不激活 venv），观察报什么错；再回到 venv 里跑通
- [ ] **H4** 把 `.venv/` 加进 `.gitignore`，用 `git status` 验证它确实不会被提交
- [ ] **H5（挑战）** 说明：为什么项目坚持「零第三方依赖」（只用 stdlib `urllib` 而不用 `requests`）？代价是什么？写在你的错题本里

## I. HTTP / API（Milestone 09）

- [ ] **I1** 读懂 `src/assistant/client.py`：画出「构造请求 → 发送 → 解析响应」的完整链路
- [ ] **I2** 用 stdlib `urllib` 手写一次 GET 请求（打 `https://httpbin.org/get`），打印状态码和响应体
- [ ] **I3** 改造成 POST：带 `Authorization: Bearer <key>` 头和 JSON body，看服务端回显
- [ ] **I4** 给 client 加超时（`timeout`）和重试，模拟超时（把 timeout 设成 0.001）验证异常被捕获
- [ ] **I5** 给 client 写单元测试：用 `unittest.mock` 假掉网络，测「正常解析」「HTTP 非 200」「响应 JSON 缺字段」三种路径
- [ ] **I6（挑战）** 对比 stdlib `urllib` 与 `requests` 的同样一段代码，说明为什么教学项目先选 urllib

---

## 验收标准

G1-G4 + H1-H4 + I1-I5 全部亲手跑通 = Milestone 07-09 可标记 🎓，此时项目应达到 v0.5（能真实联网）。
每做完一题跑一次 `cd src && python3 -m unittest discover -s tests`，**测试必须保持全绿**。
