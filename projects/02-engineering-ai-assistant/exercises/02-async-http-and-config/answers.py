"""Exercises 02-async-http-and-config 参考答案（对应 M01 / M02 / M05）。

用法:
    .venv/bin/python exercises/02-async-http-and-config/answers.py

规矩:
    先自己把 9 题敲一遍、跑通了再来看这个文件。卡住了只看对应那一个函数，不要整份抄。
    本文件纯离线：不联网、不建真实 HTTP 连接、不读真实 API Key，所有「LLM」都是测试替身。

判卷标记:
    每题跑完打印 "[PASS] <题号> <这次真的看到的东西>"，判卷脚本靠它计数。
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import time
from dataclasses import replace

from assistant.client import FakeClient
from assistant.errors import LLMRateLimitError, LLMConfigError, LLMError
from assistant.settings import DEFAULT_BASE_URL, Settings, load_dotenv

# 题库里统一用这个打印过关标记，判卷脚本靠 "[PASS]" 这五个字符计数。
def _pass(qid: str, note: str) -> None:
    print(f"[PASS] {qid} {note}")


# ---------- A. async / await（Milestone 01） ----------


async def greet(name: str) -> str:
    """A1: 最简单的协程。里面没有任何阻塞调用，只有一个让出点。"""
    await asyncio.sleep(0)
    return f"你好 {name}"


def a1() -> None:
    """A1: 协程对象 vs 协程结果。"""
    coro = greet("Beiluo")
    print(f"  不 await 时 type(greet('Beiluo')) = {type(coro).__name__}")
    assert type(coro).__name__ == "coroutine", "A1: async def 调用得到的是协程对象"

    out = asyncio.run(greet("Beiluo"))
    print(f"  asyncio.run 后 = {out!r}")
    assert out == "你好 Beiluo"
    coro.close()  # 没 await 的协程要关掉，否则会有 "never awaited" 警告

    _pass("A1", "async def 调用先得到协程对象，asyncio.run 执行后拿到字符串结果")


async def chat_all(prompts: list[str], fake: FakeClient) -> list[str]:
    """A2: 并发扇出。gather 保证返回顺序与输入顺序一致。"""
    return list(await asyncio.gather(*(fake.chat([{"role": "user", "content": p}]) for p in prompts)))


class EchoClient:
    """A2: 回显替身 —— 回复里带上原始请求，这样才能验证 gather 保序。"""

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def chat(self, messages: list[dict[str, str]]) -> str:
        self.calls.append(messages[-1]["content"])
        return messages[-1]["content"]


def a2() -> None:
    """A2: gather 并发扇出，并验证「返回顺序 == 输入顺序」。"""
    fake = FakeClient(reply="回答")
    prompts = ["问题1", "问题2", "问题3", "问题4", "问题5"]
    answers = asyncio.run(chat_all(prompts, fake))

    print(f"  输入 {len(prompts)} 条 -> 返回 {len(answers)} 条: {set(answers)}")
    print(f"  fake.calls 记录了 {len(fake.calls)} 次调用")
    assert len(answers) == 5 and len(fake.calls) == 5, "A2: 调用次数不对"
    assert answers == ["回答"] * 5

    # 上面内容都一样，看不出顺序；换回显替身才能验证 gather 的保序保证
    echo = EchoClient()
    out2 = asyncio.run(chat_all(prompts, echo))
    print(f"  回显顺序 = {out2}")
    assert out2 == prompts, "A2: gather 不保证顺序的话，这里就会失败"
    assert echo.calls == prompts and len(echo.calls) == 5

    _pass("A2", "5 条 prompts 触发 5 次 chat，返回顺序与输入顺序完全一致")


class DelayClient:
    """A3 / B2: 纯本地替身 —— 每次调用只 sleep，绝不联网。"""

    def __init__(self, delay: float = 0.15) -> None:
        self.delay = delay

    async def chat(self, messages: list[dict[str, str]]) -> str:
        await asyncio.sleep(self.delay)
        return f"回答({messages[-1]['content']})"

    async def aclose(self) -> None:
        return None


async def serial_three(client: DelayClient) -> list[str]:
    """A3 的串行版：一个一个 await。"""
    out = []
    for i in range(3):
        out.append(await client.chat([{"role": "user", "content": f"q{i}"}]))
    return out


async def concurrent_three(client: DelayClient) -> list[str]:
    """A3 的并发版：gather。"""
    return await asyncio.gather(*(client.chat([{"role": "user", "content": f"q{i}"}]) for i in range(3)))


def a3() -> None:
    """A3: 用墙钟耗时证明并发真的省时间（比值必须 > 1）。"""
    t0 = time.perf_counter()
    serial = asyncio.run(serial_three(DelayClient()))
    t1 = time.perf_counter()
    concurrent = asyncio.run(concurrent_three(DelayClient()))
    t2 = time.perf_counter()

    serial_cost = t1 - t0
    concurrent_cost = t2 - t1
    ratio = serial_cost / concurrent_cost

    print(f"  串行耗时 = {serial_cost:.3f}s，结果 {serial}")
    print(f"  并发耗时 = {concurrent_cost:.3f}s，结果 {concurrent}")
    print(f"  并发/串行 = {ratio:.2f}x")
    assert ratio > 1.0, f"A3: 并发没省时间（比值 {ratio:.2f}），异步白写了？"
    assert serial == concurrent, "A3: 两种写法结果应一致"

    _pass(f"A3", f"真实墙钟：串行 {serial_cost:.3f}s vs 并发 {concurrent_cost:.3f}s，比值 {ratio:.2f}x > 1")


# ---------- B. 异步 HTTP 与测试替身（Milestone 02） ----------


def b1() -> None:
    """B1: 用仓库自带的 FakeClient 做并发（不联网）。"""
    fake = FakeClient(reply="固定回答")
    prompts = ["a", "b", "c", "d"]
    out = asyncio.run(chat_all(prompts, fake))

    print(f"  返回 {len(out)} 条: {out}")
    print(f"  fake.calls 条数 = {len(fake.calls)}，最后一条内容 = {fake.calls[-1][0]['content']!r}")
    assert len(fake.calls) == 4, "B1: FakeClient 应记到 4 次调用"
    assert [c[0]["content"] for c in fake.calls] == prompts, "B1: 调用顺序应与输入一致"
    # 拿它和真实客户端对比：替身身上没有 httpx 的 _client，自然不可能联网
    assert not hasattr(fake, "_client"), "B1: 替身身上不该有 httpx 客户端"

    _pass("B1", "FakeClient 被并发调用了 4 次，调用记录与返回顺序都正确")


def b2() -> None:
    """B2: wait_for 超时 —— 被取消的那一次已经发出了请求。"""
    slow = DelayClient(delay=0.5)
    fake_calls: list[str] = []

    async def counting_chat(messages: list[dict[str, str]]) -> str:
        fake_calls.append(messages[-1]["content"])
        return await slow.chat(messages)

    t0 = time.perf_counter()
    try:
        asyncio.run(asyncio.wait_for(counting_chat([{"role": "user", "content": "慢请求"}]), timeout=0.05))
    except asyncio.TimeoutError as e:
        elapsed = time.perf_counter() - t0
        print(f"  等了 {elapsed:.3f}s 后抛 {type(e).__name__}")
    else:  # pragma: no cover
        raise AssertionError("B2: 超时应抛 asyncio.TimeoutError")

    assert fake_calls == ["慢请求"], "B2: 被取消的请求也要算作「发出过」"
    print(f"  超时前已经发出的请求 = {fake_calls}")

    # 反过来：超时给足就能拿到结果
    got = asyncio.run(asyncio.wait_for(counting_chat([{"role": "user", "content": "快请求"}]), timeout=5.0))
    assert got == "回答(快请求)"

    _pass("B2", "wait_for 在 0.05s 抛 asyncio.TimeoutError，且超时前请求已发出；给足超时则正常返回")


async def _retry_until_ok(fake: FakeClient) -> tuple[str, int]:
    """B3 的退避重试循环：退避用 sleep(0)，不真等。"""
    for attempt in range(1, 6):
        try:
            return await fake.chat([{"role": "user", "content": "hi"}]), attempt
        except LLMRateLimitError:
            if attempt == 5:
                raise
            await asyncio.sleep(0)  # 真实代码里这里换成 2 ** (attempt - 1)
    raise AssertionError("不该走到这")  # pragma: no cover


def b3() -> None:
    """B3: 前两次限流、第三次成功；超过重试次数则抛 LLMRateLimitError。"""
    fake = FakeClient(fail_times=2, reply="第 3 次终于成功")
    text, attempt = asyncio.run(_retry_until_ok(fake))
    print(f"  第 {attempt} 次拿到回复: {text!r}（fake 共被调用 {len(fake.calls)} 次）")
    assert attempt == 3 and len(fake.calls) == 3
    assert text == "第 3 次终于成功"

    # 一直限流：抛 LLMRateLimitError，且能被 LLMError 基类接住
    stuck = FakeClient(fail_times=99)
    try:
        asyncio.run(_retry_until_ok(stuck))
    except LLMRateLimitError as e:
        print(f"  一直限流抛 {type(e).__name__}；它是 LLMError 的子类吗: {isinstance(e, LLMError)}")
        assert isinstance(e, LLMError)
        assert not isinstance(e, LLMConfigError)

    _pass("B3", "前两次限流第三次成功（共 3 次调用）；持续限流抛 LLMRateLimitError 且属 LLMError 子类")


# ---------- C. frozen 配置与环境（Milestone 05） ----------


def c1() -> None:
    """C1: 优先级 真实环境变量 > .env > 代码默认值。跑完必须清理环境变量。"""
    tmpdir = tempfile.mkdtemp(prefix="ex02-config-")
    dotenv_path = os.path.join(tmpdir, ".env")
    with open(dotenv_path, "w", encoding="utf-8") as f:
        f.write(
            "DEEPSEEK_API_KEY=sk-from-dotenv\n"
            "DEEPSEEK_MODEL=from-dotenv\n"
            "DEEPSEEK_MAX_RETRIES=7\n"
        )

    keys = ["DEEPSEEK_API_KEY", "DEEPSEEK_MODEL", "DEEPSEEK_MAX_RETRIES", "DEEPSEEK_TIMEOUT"]
    saved = {k: os.environ.get(k) for k in keys}
    for k in keys:                       # 先清干净，避免用户本机环境干扰这次判断
        os.environ.pop(k, None)
    # 真实环境变量：覆盖 .env 里的同名键
    os.environ["DEEPSEEK_API_KEY"] = "sk-from-real-env"
    os.environ["DEEPSEEK_MODEL"] = "from-real-env"

    try:
        s = Settings.from_env(dotenv_path=dotenv_path)
        print(f"  api_key  = {s.api_key!r}  ← 真实环境变量盖掉了 .env")
        print(f"  model    = {s.model!r}  ← 真实环境变量")
        print(f"  max_retries = {s.max_retries}  ← .env（环境变量里没有这一项）")
        print(f"  base_url = {s.base_url!r}  ← 代码默认值（两个来源都没有）")
        assert s.api_key == "sk-from-real-env", "C1: 真实环境变量应优先于 .env"
        assert s.model == "from-real-env"
        assert s.max_retries == 7, "C1: 应取 .env 的值"
        assert s.base_url == DEFAULT_BASE_URL, "C1: 应落到代码默认值"

        # load_dotenv 本身也用 setdefault：已有环境变量不被覆盖
        os.environ["DEEPSEEK_MODEL"] = "changed-after-loaded"
        load_dotenv(dotenv_path)
        print(f"  load_dotenv 之后再读 model = {os.environ['DEEPSEEK_MODEL']!r}（setdefault 不覆盖）")
        assert os.environ["DEEPSEEK_MODEL"] == "changed-after-loaded"
    finally:
        for k in keys:
            os.environ.pop(k, None)
            if saved[k] is not None:
                os.environ[k] = saved[k]
        os.unlink(dotenv_path)
        os.rmdir(tmpdir)

    assert "DEEPSEEK_MODEL" not in os.environ, "C1: 跑完必须把环境变量清干净"
    _pass("C1", "三档优先级逐一验证成立（真实环境变量 > .env > 代码默认值），且跑完清掉了临时环境变量")


def c2() -> None:
    """C2: frozen 配置在并发里也是安全的。"""
    base = Settings(api_key="sk-test")

    async def variant(level: str) -> Settings:
        return replace(base, log_level=level)

    # 坑：asyncio.run(gather(...)) 这种写法会炸。
    # 实参是在 asyncio.run 之前求值的，那时还没有事件循环，gather 里 ensure_future 就会
    # 报 "RuntimeError: There is no current event loop"。
    # 正确顺序：先建协程列表，再包一层 async 函数交给 asyncio.run。
    tasks = [variant(level) for level in ("DEBUG", "INFO", "WARNING", "ERROR")]

    async def run_all() -> list[Settings]:
        return list(await asyncio.gather(*tasks))

    out = asyncio.run(run_all())

    print(f"  原对象 log_level = {base.log_level!r}，并发变体 = {[v.log_level for v in out]}")
    assert base.log_level == "INFO", "C2: 原对象被并发写坏了"
    assert [v.log_level for v in out] == ["DEBUG", "INFO", "WARNING", "ERROR"]
    assert len({id(v) for v in out}) == 4, "C2: 每次 replace 都应是新对象"
    assert all(v.api_key == "sk-test" for v in out)

    _pass("C2", "4 个并发 replace 互不干扰，原 Settings 仍是 INFO")


def c3() -> None:
    """C3: 配置校验失败也要有明确报错。"""
    keys = ["DEEPSEEK_TIMEOUT", "DEEPSEEK_API_KEY"]
    saved = {k: os.environ.get(k) for k in keys}
    for k in keys:
        os.environ.pop(k, None)
    os.environ["DEEPSEEK_API_KEY"] = "sk-test"      # 先把 Key 备好，才能走到 timeout 解析那一步
    os.environ["DEEPSEEK_TIMEOUT"] = "不是数字"

    try:
        try:
            Settings.from_env(dotenv_path="")
        except LLMConfigError as e:
            print(f"  from_env 抛: {e}")
        else:  # pragma: no cover
            raise AssertionError("C3: timeout 非数字竟然没抛错")

        bad = Settings(api_key="k", base_url="ftp://不合规")
        try:
            bad.validate()
        except LLMConfigError as e:
            print(f"  validate 抛: {e}")
        else:  # pragma: no cover
            raise AssertionError("C3: base_url 非法竟然没抛错")
    finally:
        for k in keys:
            os.environ.pop(k, None)
            if saved[k] is not None:
                os.environ[k] = saved[k]

    _pass("C3", "timeout 非数字与 base_url 非法都抛 LLMConfigError，且错误信息带上当前值")


def main() -> None:
    print("--- A ---")
    a1()
    a2()
    a3()

    print("\n--- B ---")
    b1()
    b2()
    b3()

    print("\n--- C ---")
    c1()
    c2()
    c3()

    print(f"\n全部 9 题跑完，退出码 0（Python {sys.version.split()[0]}）")


if __name__ == "__main__":
    main()
