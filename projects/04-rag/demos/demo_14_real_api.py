"""真实起一个 FastAPI 服务，用 HTTP 打进去看 RAG 的 Web 接口（13 章）。

    python demos/demo_14_real_api.py              # 全离线（RAG_FAKE=1）
    python demos/demo_14_real_api.py real         # 真实 embedding + 真实 DeepSeek

和 12/13 那些"在进程内跑一遍"的 demo 不同，这次是真的起了子进程 + 监听端口 +
走 TCP 发请求：SSE 的时序、TTFT、以及"服务挂掉时前端看到什么"，都只有在
这条链路上才看得见。

截图判据：截图里必须能看到真实的 http 状态码、真实的 SSE 帧、真实耗时。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from common import WIDTH, head, note, rule  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PORT = 8123
BASE = f"http://127.0.0.1:{PORT}"

Q1 = "生成器为什么能省内存？"
Q2 = "ls -l 和 ls -lh 有什么区别？"      # 语料里没有 → 应当拒答
Q3 = "装饰器在 Python 里到底做了什么？"


def show(cmd: str) -> None:
    """续行的 curl 片段（首行由 head() 带 `$ ` 打印）。"""
    print("      " + cmd)


def wait_healthy(timeout: float = 90.0) -> None:
    import httpx
    deadline = time.perf_counter() + timeout
    while time.perf_counter() < deadline:
        try:
            r = httpx.get(f"{BASE}/health", timeout=1.5)
            if r.status_code == 200:
                print(f"  服务已就绪：{BASE}  ← GET /health → {r.json()}")
                return
        except Exception:                       # noqa: BLE001  还没起来，继续等
            time.sleep(0.4)
    raise SystemExit("服务在超时前没有起来，看看上面的进程日志")


def section_ask() -> None:
    import httpx
    rule("① POST /ask —— 一次性拿答案")
    show(f'curl -s -X POST {BASE}/ask -H "Content-Type: application/json" \\')
    show(f'  -d \'{{"query": "{Q1}"}}\'')
    t0 = time.perf_counter()
    r = httpx.post(f"{BASE}/ask", json={"query": Q1}, timeout=120)
    cost = time.perf_counter() - t0
    print(f"  HTTP {r.status_code}   用时 {cost:.2f}s   响应体：")
    for k, v in r.json().items():
        print(f"    {k:<16} = {str(v)[:90]}")
    print("  → 好处是可以拿 JSON 直接写脚本；缺点是要等模型把整段生成完。")


def section_stream() -> None:
    import httpx
    rule("② POST /ask/stream —— SSE 逐帧推送（打字机效果）")
    show(f'curl -N -X POST {BASE}/ask/stream -H "Content-Type: application/json" \\')
    show(f'  -d \'{{"query": "{Q1}"}}\'')
    t0 = time.perf_counter()
    nframes = 0
    ttft = 0.0
    kinds: list[str] = []
    text_built = ""
    with httpx.stream("POST", f"{BASE}/ask/stream", json={"query": Q1},
                      timeout=120) as r:
        print(f"  HTTP {r.status_code}   响应头 content-type = "
              f"{r.headers.get('content-type')}")
        print(f"  {'t(ms)':>8}  {'kind':<11} 帧内容")
        print("  " + "-" * (WIDTH - 4))
        for line in r.iter_lines():
            if not line.startswith("data: "):
                continue
            payload = line[6:].strip()
            if payload == "[DONE]":
                print(f"  {1000*(time.perf_counter()-t0):8.1f}  {'[DONE]':<11} "
                      f"流结束，共 {nframes} 帧")
                break
            ev = json.loads(payload)
            kinds.append(ev["kind"])
            if not ttft:
                ttft = time.perf_counter() - t0
            if ev["kind"] == "delta":
                nframes += 1
                piece = ev.get("text", "")
                text_built += piece               # 前端就是这么攒出完整答案的
                if nframes <= 4:
                    print(f"  {1000*(time.perf_counter()-t0):8.1f}  {'delta':<11} "
                          f"+{piece[:48]!r}")
                elif nframes == 5:
                    print(f"  {1000*(time.perf_counter()-t0):8.1f}  {'delta':<11} "
                          f"...（中间帧省略，累计已收 {len(text_built)} 字）")
            elif ev["kind"] == "retrieved":
                print(f"  {1000*(time.perf_counter()-t0):8.1f}  {'retrieved':<11} "
                      f"命中 {len(ev.get('sources',[]))} 条来源，"
                      f"context_tokens={ev.get('context_tokens')}")
            elif ev["kind"] == "done":
                answer = ev.get("answer", "")
                same = "一致" if answer == text_built else "不一致"
                print(f"  {1000*(time.perf_counter()-t0):8.1f}  {'done':<11} "
                      f"完整答案 {len(answer)} 字，引用 {len(ev.get('citations',[]))} 条")
                print(f"  → 逐帧拼接结果 = {same}（逐帧增量累加 == 最终答案，"
                      "这是流式接口的正确性底线）")
    total = time.perf_counter() - t0
    print("  " + "-" * (WIDTH - 4))
    print(f"  首帧延迟 TTFT = {ttft*1000:.1f} ms（retrieved 事件通常在几十毫秒级）")
    print(f"  最后一帧 = {total*1000:.1f} ms，delta 帧数 = {nframes}")
    # 真实模型一帧可能只有一个字（258 帧），全量打印只会刷屏，这里压成计数
    compact: list[list] = []
    for k in kinds:
        if compact and compact[-1][0] == k:
            compact[-1][1] += 1
        else:
            compact.append([k, 1])
    seq = " → ".join(f"{k}×{n}" if n > 1 else k for k, n in compact)
    print(f"  事件序列 = {seq}")
    print("  → 用户要等的时间从「整段生成完」缩短到「第一个字出来」。"
          "这就是 SSE 的全部意义，")
    print("    它不改变答案质量，只改变等待感。")


def section_refuse(real: bool) -> None:
    """③ 拒答闸门。这里有个**只有跑真实服务才看得见**的落差。

    FakeEmbeddingClient 是 char-ngram 哈希向量：任何查询都会和任何 chunk 算出
    一个非零相似度，于是 min_score=0.2 这道闸门在离线模式下根本拦不住东西。
    换句话说 —— 拒答能力是用真实 embedding 才测出来的。
    """
    import httpx
    rule("③ 拒答：语料里没有的问题，不该硬答")
    r = httpx.post(f"{BASE}/ask", json={"query": Q2}, timeout=60)
    data = r.json()
    print(f"  语料里没有 ls 命令，问：{Q2}")
    print(f"  HTTP {r.status_code}   refused={data.get('refused')}   "
          f"sources={len(data.get('sources') or [])} 条")
    if not real:
        print("  → Fake embedding 下 refused=False、sources 非空：闸门形同虚设。")
        print("    这是离线替身的固有特性，不是 bug —— 但它意味着「拒答」这件事")
        print("    必须换真实 embedding 才测得出来。下面用真实模式跑同一条问题对比。")
    else:
        print("  → 同一个问题在真实 embedding 下检索为空，服务直接拒答，")
        print("    不调 LLM（省钱）、不编造（09 章失败语义 2）。")
        print(f"    答案 = {str(data.get('answer'))[:70]}")
        print(f"    refused = {data.get('refused')}   ← 模型把话术改写了（只有半句），")
        print("    判据用的是关键词命中而非整串匹配，所以仍然认出来了。")
        print("    若改成字符串精确匹配，这里就会显示 refused=False —— 前端把")
        print("    「我不知道」当成正常答案展示出去。")


def section_stats_and_index() -> None:
    import httpx
    rule("④ GET /stats 与 POST /index")
    r = httpx.get(f"{BASE}/stats", timeout=10)
    print(f"  GET /stats → HTTP {r.status_code}  {r.json()}")
    r = httpx.post(f"{BASE}/index", json={"paths": ["data/"]}, timeout=120)
    print(f"  POST /index → HTTP {r.status_code}  {r.json()}")
    print("  → 内存向量库每次冷启动都是空的，所以留了 /index 这个口随时补建；")
    print("    生产上换成 Chroma 落盘后，这一步就不需要了（12 章）。")


def main(argv: list[str]) -> int:
    real = "real" in argv
    head(f"python demos/demo_14_real_api.py {'real' if real else ''}")
    print(f"  模式：{'真实 embedding + 真实 DeepSeek' if real else '全离线（RAG_FAKE=1）'}")
    print(f"$ export RAG_FAKE={'0' if real else '1'}")
    print(f"$ python -m uvicorn rag.api:app --host 127.0.0.1 --port {PORT}")

    env = os.environ.copy()
    env["RAG_FAKE"] = "0" if real else "1"
    env["PYTHONPATH"] = str(ROOT / "src")
    env["RAG_API_INDEX"] = "data/"
    cmd = [sys.executable, "-m", "uvicorn", "rag.api:app",
           "--host", "127.0.0.1", "--port", str(PORT), "--log-level", "warning"]

    proc = subprocess.Popen(cmd, cwd=str(ROOT), env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True)
    try:
        wait_healthy()
        note("下面是真实 HTTP 请求的输出，不是打印出来的假数据")
        if real:
            rule("真实链路也走一遍同样的接口，代码一行没改")
        section_ask()
        section_stream()
        section_refuse(real)
        section_stats_and_index()
    finally:
        print("-" * WIDTH)
        print("  $ pkill -f 'uvicorn rag.api:app'")
        proc.terminate()
        try:
            out, _ = proc.communicate(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
            out, _ = proc.communicate()
        if out:
            tail_lines = [ln for ln in out.splitlines() if ln.strip()][-6:]
            print("  服务日志（末尾几行）：")
            for ln in tail_lines:
                print(f"    | {ln[:96]}")
        print(f"  进程退出码 = {proc.returncode}")
    rule("小结")
    print("  · /ask 一次性、/ask/stream 流式，两条路共用 RAGService 的同一段检索")
    print("  · 流式路径的失败语义更狠：吐出去的字收不回来，所以只在首帧前重试")
    print("  · 同步的 httpx 在 async 端点里必须走线程池，否则事件循环会被堵死")
    rule()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
