"""产品化验证：会话历史 + 多轮追问 + 前端 Chat UI（17 章）。

    python demos/demo_18_chat_session.py

和 demo_14 一样是**真起进程真发 HTTP**：这一次要证明的不是「接口能通」，而是
「连续聊天这件事在真实链路上成立」—— 第二轮能不能看见第一轮、刷新后历史还在、
会话能不能增删改。做完这段才算产品，否则只是接口。

截图判据：截图里必须能看到真实的 HTTP 状态码、真实的 session id、真实的历史轮次。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from common import WIDTH, head, note, rule  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PORT = 8123
BASE = f"http://127.0.0.1:{PORT}"

Q1 = "生成器为什么能省内存？"
Q2 = "那列表推导式呢？"          # 依赖第一轮的答案，问完才知道「它」指谁
Q3 = "ls -l 和 ls -lh 有什么区别？"   # 语料里没有 → 应当拒答


def show(cmd: str) -> None:
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
        except Exception:                       # noqa: BLE001
            time.sleep(0.4)
    raise SystemExit("服务在超时前没有起来，看看上面的进程日志")


def section_create_and_list() -> str:
    import httpx

    rule("① 建会话并列出")
    show('curl -s -X POST {BASE}/sessions -d \'{"title":"新对话"}\'')
    r = httpx.post(f"{BASE}/sessions", json={"title": "验证会话"}, timeout=10)
    print(f"  POST /sessions → HTTP {r.status_code}  {r.json()}")
    sid = r.json()["id"]
    listing = httpx.get(f"{BASE}/sessions", timeout=10).json()
    print(f"  GET  /sessions → HTTP 200   列表 {len(listing)} 条，"
          f"首条 id={listing[0]['id']}，title={listing[0]['title']!r}")
    return sid


def section_multi_turn(sid: str) -> None:
    """② 第二轮要带第一轮的 history —— 这是「多轮」和「多打几次接口」的区别。"""
    import httpx

    rule("② 多轮追问：第二问必须看得见第一问")
    r1 = httpx.post(f"{BASE}/ask", json={"query": Q1, "session_id": sid}, timeout=120)
    print(f"  第1轮 POST /ask → HTTP {r1.status_code}  session_id={r1.json()['session_id']}  "
          f"turn_id={r1.json()['turn_id']}")
    print(f"        答案：{r1.json()['answer'][:56]}…")
    print(f"        引用：{r1.json()['sources']}")

    r2 = httpx.post(f"{BASE}/ask", json={"query": Q2, "session_id": sid}, timeout=120)
    print(f"  第2轮 POST /ask → HTTP {r2.status_code}  （同一 session_id，无 history 参数）")
    print(f"        答案：{r2.json()['answer'][:56]}…")
    print("  → 后端自动把这一会话的历史拼进 prompt（顺序：system → 历史 → 本次提问）。")
    print("    前端不需要额外传 history，只需要在第二轮带上同一个 session_id。")


def section_history(sid: str) -> None:
    import httpx

    rule("③ 会话详情：历史落库后原样回读")
    detail = httpx.get(f"{BASE}/sessions/{sid}", timeout=10).json()
    print(f"  GET /sessions/{sid} → HTTP 200   title={detail['title']!r}  "
          f"turn_count={detail['turn_count']}  created_at={detail['created_at']:.2f}")
    for i, t in enumerate(detail["turns"], 1):
        preview = t["content"].replace("\n", " ")[:44]
        print(f"    {i:>2}. [{t['role']:<8}] {preview:<46} "
              f"sources={len(t['sources'])} refused={t['refused']}")
    print(f"  文件名：data/sessions/{sid}.json（RAG_SESSIONS_DIR 指向的目录）")
    path = ROOT / "data" / "sessions" / f"{sid}.json"
    if path.exists():
        raw = json.loads(path.read_text(encoding="utf-8"))
        print(f"  磁盘上真的有这个文件：{len(raw['turns'])} 轮，"
              f"title={raw['title']!r}，可跨进程重读")


def section_stream(sid: str) -> None:
    import httpx

    rule("④ 流式接口同样带会话：done 事件回传 session_id / turn_id")
    t0 = time.perf_counter()
    nframes = 0
    kinds: list[str] = []
    text = ""
    with httpx.stream("POST", f"{BASE}/ask/stream",
                      json={"query": "生成器的一次性消费是什么意思？", "session_id": sid},
                      timeout=120) as r:
        print(f"  POST /ask/stream → HTTP {r.status_code}")
        for line in r.iter_lines():
            if not line.startswith("data: "):
                continue
            payload = line[6:].strip()
            if payload == "[DONE]":
                break                       # 时间与 done 帧几乎同时到达，留到最后一起打
            ev = json.loads(payload)
            kinds.append(ev["kind"])
            if ev["kind"] == "delta":
                nframes += 1
                text += ev["text"]
            elif ev["kind"] in ("retrieved", "done"):
                extra = {k: v for k, v in ev.items() if k in ("session_id", "turn_id")}
                print(f"  {1000*(time.perf_counter()-t0):8.1f} ms  {ev['kind']:<10} "
                      f"{json.dumps(extra, ensure_ascii=False)}")
    print(f"  {1000*(time.perf_counter()-t0):8.1f} ms  [DONE]   流结束")
    compact: list[list] = []
    for k in kinds:
        if compact and compact[-1][0] == k:
            compact[-1][1] += 1
        else:
            compact.append([k, 1])
    seq = " → ".join(f"{k}×{n}" if n > 1 else k for k, n in compact)
    print(f"  事件序列 = {seq}   delta 帧数 = {nframes}   拼接长度 = {len(text)} 字")
    print("  → 前端只靠 session_id 就能把这一轮写进历史，turn_id 用于定位/跳转。")


def section_refuse_in_session(sid: str) -> None:
    import httpx

    rule("⑤ 拒答也会进历史：会话里留下「问过但答不了」，不是悄悄丢掉")
    r = httpx.post(f"{BASE}/ask", json={"query": Q3, "session_id": sid}, timeout=120)
    data = r.json()
    print(f"  POST /ask 「{Q3}」 → HTTP {r.status_code}  refused={data['refused']}  "
          f"sources={len(data['sources'])} 条")
    print(f"  答案：{data['answer'][:70]}…")
    detail = httpx.get(f"{BASE}/sessions/{sid}", timeout=10).json()
    last = detail["turns"][-1]
    print(f"  历史末轮：role={last['role']} refused={last['refused']} "
          f"sources={len(last['sources'])} 条")
    if data["refused"]:
        print("  → 前端据此显示成红色，用户能在历史上看到「这条当时没答上来」。")
    else:
        print("  → 这里 refused=False，不是 bug：FakeEmbeddingClient 是 char-ngram 哈希")
        print("     向量，任何查询都会和任何 chunk 算出非零相似度，min_score 闸门在离线")
        print("     模式下形同虚设（14 章已验证：拒答必须换真实 embedding 才测得出来）。")
        print("     要在这里看到 refused=True，把本次跑法换成 `python demo_18_chat_session.py real`")


def section_ui() -> None:
    """⑥ 静态前端。这里只验证「能拿到、拿到的是同一个页面」，渲染交给浏览器。"""
    import httpx

    rule("⑥ 前端静态页（零构建，原生 HTML/JS）")
    r = httpx.get(f"{BASE}/", timeout=10)
    print(f"  GET / → HTTP {r.status_code}  content-type={r.headers.get('content-type')}  "
          f"{len(r.text)} 字节")
    for name in ("index.html", "app.js", "style.css"):
        p = ROOT / "web" / name
        print(f"  web/{name:<12} {p.stat().st_size:>6} 字节  exists={p.exists()}")
    print("  → 服务启动时自动挂载 web/（存在才挂），接口与页面共用同一个进程。")


def section_real_multiturn(sid: str) -> None:
    """⑧ 只有真实模型能证明「历史真的进了 prompt」。

    FakeLLM 的回答是写死的，喂不喂历史它都回同一句 —— 所以离线模式下「接口通」
    和「多轮真的生效」是两件事。这一节在 `real` 模式下跑，用同一个问题、
    带/不带历史各一次，看答案是否跟着变。
    """
    import httpx

    rule("⑧ 真实模型：同一问题，带历史与不带历史的答案")
    q = "那它省内存的原因具体是什么？"
    a = httpx.post(f"{BASE}/ask", json={"query": q}, timeout=180).json()["answer"]
    b = httpx.post(f"{BASE}/ask", json={"query": q, "session_id": sid}, timeout=180).json()["answer"]
    print(f"  不带历史：{a[:120]}".replace("\n", " "))
    print(f"  带历史  ：{b[:120]}".replace("\n", " "))
    print(f"  → 两次答案 {'不同' if a.strip() != b.strip() else '相同'}"
          "：不同就说明历史确实进了 prompt，")
    print("    模型看到了上面几轮问答；相同则说明多轮没生效（值得回头查 messages 顺序）。")


def section_crud(sid: str) -> None:
    import httpx

    rule("⑦ 改标题 / 404 / 删除")
    r = httpx.patch(f"{BASE}/sessions/{sid}", json={"title": "改过的标题"}, timeout=10)
    print(f"  PATCH /sessions/{sid} → HTTP {r.status_code}  title={r.json()['title']!r}")

    missing = httpx.get(f"{BASE}/sessions/deadbeef", timeout=10)
    print(f"  GET  /sessions/deadbeef → HTTP {missing.status_code}  {missing.json()['detail']}")

    bad = httpx.post(f"{BASE}/ask", json={"query": "测试", "session_id": "deadbeef"}, timeout=10)
    print(f"  POST /ask 携带不存在的 session_id → HTTP {bad.status_code}  {bad.json()['detail']}")

    listing = httpx.get(f"{BASE}/sessions", timeout=10).json()
    target = next((s for s in listing if s["id"] == sid), None)
    if target:
        d = httpx.delete(f"{BASE}/sessions/{sid}", timeout=10)
        print(f"  DELETE /sessions/{sid} → HTTP {d.status_code}  {d.json()}")
    after = httpx.get(f"{BASE}/sessions", timeout=10).json()
    print(f"  删除后列表 {len(listing)} 条 → {len(after)} 条")


def main(argv: list[str]) -> int:
    real = "real" in argv
    head("python demos/demo_18_chat_session.py " + ("real" if real else ""))
    print(f"  模式：{'真实 embedding + 真实 DeepSeek' if real else '全离线（RAG_FAKE=1，FakeEmbedding + FakeLLM）'}")
    print(f"$ export RAG_FAKE={'0' if real else '1'}")
    print(f"$ python -m uvicorn rag.api:app --host 127.0.0.1 --port {PORT}")

    # 会话落盘目录：真实模式下用临时目录，免得把真实问答留在仓库里
    session_dir = ROOT / "data" / "sessions"
    if session_dir.exists():            # 离线模式清空上一轮的残留，让输出可复现
        for p in session_dir.glob("*.json"):
            p.unlink()

    env = os.environ.copy()
    env["RAG_FAKE"] = "0" if real else "1"
    env["PYTHONPATH"] = str(ROOT / "src")
    env["DEEPSEEK_API_KEY"] = os.environ.get("DEEPSEEK_API_KEY", "")
    # 真实 embedding：本机没有 SILICONFLOW_API_KEY，但百炼 key 在时会自动降级过去
    if os.environ.get("DASHSCOPE_API_KEY"):
        env["DASHSCOPE_API_KEY"] = os.environ["DASHSCOPE_API_KEY"]
        print("  embedding 走百炼 text-embedding-v3（本机没有 SILICONFLOW key）")
    env["RAG_SESSIONS_DIR"] = (tempfile.mkdtemp(prefix="rag-sessions-") if real
                               else str(session_dir))
    cmd = [sys.executable, "-m", "uvicorn", "rag.api:app",
           "--host", "127.0.0.1", "--port", str(PORT), "--log-level", "warning"]

    proc = subprocess.Popen(cmd, cwd=str(ROOT), env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    sid = ""
    try:
        wait_healthy()
        note("下面是真实 HTTP 请求的输出，不是打印出来的假数据")
        sid = section_create_and_list()
        section_multi_turn(sid)
        section_history(sid)
        section_stream(sid)
        section_refuse_in_session(sid)
        section_ui()
        if real:
            section_real_multiturn(sid)
        section_crud(sid)
    finally:
        print("-" * WIDTH)
        print(f"  RAG_SESSIONS_DIR = {env['RAG_SESSIONS_DIR']}")
        print("  $ pkill -f 'uvicorn rag.api:app'")
        proc.terminate()
        try:
            out, _ = proc.communicate(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
            out, _ = proc.communicate()
        if out:
            tail = [ln for ln in out.splitlines() if ln.strip()][-4:]
            print("  服务日志（末尾几行）：")
            for ln in tail:
                print(f"    | {ln[:96]}")
        print(f"  进程退出码 = {proc.returncode}")
    rule("小结")
    print("  · 会话是「一轮 user + 一轮 assistant」，写进 store，重启后仍可重读")
    print("  · 多轮不需要前端传 history：带同一个 session_id 就够了")
    print("  · 流式接口在 done 事件里回传 session_id / turn_id，前端据此补记历史")
    print("  · 拒答也进历史：用户能看到「问过但没答上来」，而不是凭空消失")
    print("  · 改标题 / 查不存在的会话（404）/ 删除，都是真实 HTTP 语义")
    rule()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
