"""Project 05 —— Milestone 07/08/09：MCP 协议 / Server / Client 的真实演示。

三章一次跑完，因为拆开讲协议没意义 —— 它只有在两端真的对上话时才成立。

    1. 四种消息形状          —— 请求/通知/响应/错误
    2. stdio 帧为什么是一行   —— 内容里的换行必须被转义
    3. 握手三步              —— initialize → notify → tools/list
    4. 两类错误不能混         —— 协议错误 vs 工具执行失败
    5. 真的拉起一个子进程     —— client 与 server 跨进程对话
    6. 桥接进 Agent          —— Agent 不知道工具在另一个进程里
    7. 真实模型（--real）     —— DeepSeek 用 MCP 工具答题

    python demos/demo_07_mcp.py
    python demos/demo_07_mcp.py --real
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agent.mcp import (  # noqa: E402
    METHOD_INITIALIZE,
    METHOD_TOOLS_CALL,
    METHOD_TOOLS_LIST,
    NOTIFY_INITIALIZED,
    PROTOCOL_VERSION,
    ProtocolError,
    decode_frame,
    encode_frame,
    make_error,
    make_notification,
    make_request,
    make_response,
    parse_message,
)
from agent.mcp.client import mcp_tools, spawn_default_server  # noqa: E402
from agent.mcp.server import MCPServer, MCPToolSpec  # noqa: E402

WIDTH = 72


def show(title: str) -> None:
    print()
    print("─" * WIDTH)
    print(f"  {title}")
    print("─" * WIDTH)


def dump(label: str, message: dict) -> None:
    print(f"  {label}")
    print(f"    {json.dumps(message, ensure_ascii=False)}")


# ────────────────────────────────────────────────────────────────────── 1
def section_1() -> None:
    show("1. JSON-RPC 2.0 的四种消息")
    dump("请求（有 id，要等回应）", make_request(1, METHOD_TOOLS_LIST))
    dump("通知（**没有 id**，不等回应）", make_notification(NOTIFY_INITIALIZED))
    dump("响应", make_response(1, {"tools": []}))
    dump("错误响应", make_error(1, -32601, "方法不存在"))
    print()
    print("id 是区分「请求」与「通知」的唯一依据 —— 也是并发时配对的凭据。")
    print("自己发明一套 {cmd, args} 也能跑，但这三个问题就都要自己解决一遍。")


# ────────────────────────────────────────────────────────────────────── 2
def section_2() -> None:
    show("2. stdio 传输：一帧就是一行 JSON")
    frame = encode_frame(make_response(1, {"text": "第一行\n第二行"}))
    print(f"  编码后：{frame!r}")
    print(f"  换行数：{frame.count(chr(10))}（必须是 1 —— 末尾那个）")
    print()
    print("如果手工拼字符串而不是 json.dumps，内容里的换行会把一帧切成两帧，")
    print("对端解析到第二半时直接 PARSE_ERROR，而且从日志很难看出为什么。")
    print()
    for bad in ("{not json", "[1,2,3]", "   "):
        try:
            decode_frame(bad)
        except ProtocolError as exc:
            print(f"  {bad!r:<14} → {exc}")


# ────────────────────────────────────────────────────────────────────── 3
def section_3() -> None:
    show("3. 握手三步：initialize → notify → tools/list")
    srv = MCPServer()
    srv.register(
        MCPToolSpec(
            name="echo",
            description="回声",
            input_schema={"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
            handler=lambda text: "你说了：" + text,
        )
    )
    print("  ① initialize（客户端声明版本）：")
    dump("请求", make_request(1, METHOD_INITIALIZE, {"protocolVersion": PROTOCOL_VERSION}))
    result = srv.handle(make_request(1, METHOD_INITIALIZE, {"protocolVersion": PROTOCOL_VERSION}))
    dump("响应", result)
    print()
    print("  ② notifications/initialized（单向通知，服务端不回）：")
    print(f"    {json.dumps(make_notification(NOTIFY_INITIALIZED), ensure_ascii=False)}")
    print(f"    → 服务端返回 {srv.handle(make_notification(NOTIFY_INITIALIZED))}（None = 不回应）")
    print()
    print("  ③ tools/list：")
    dump("响应", srv.handle(make_request(2, METHOD_TOOLS_LIST)))
    print()
    print("  如果跳过 ② 会怎样 —— 试试在握手前就调 tools/list：")
    fresh = MCPServer()
    resp = fresh.handle(make_request(1, METHOD_TOOLS_LIST))
    print(f"    {json.dumps(resp, ensure_ascii=False)}")
    print("  错误看起来像「服务端没实现这个方法」，其实只是握手没做完 —— 很误导。")


# ────────────────────────────────────────────────────────────────────── 4
def section_4() -> None:
    show("4. 两类错误不能混")
    srv = MCPServer()
    srv.handle(make_request(1, METHOD_INITIALIZE, {}))
    srv.handle(make_notification(NOTIFY_INITIALIZED))
    srv.register(
        MCPToolSpec(
            name="boom",
            description="会炸的工具",
            input_schema={"type": "object", "properties": {}},
            handler=lambda: (_ for _ in ()).throw(RuntimeError("查不到")),
        )
    )
    print("  ① 工具执行失败 → **result 里的 isError**（这是一次正常结果，模型该换个词再查）")
    dump("", srv.handle(make_request(2, METHOD_TOOLS_CALL, {"name": "boom"})))
    print()
    print("  ② 工具名不存在 → **JSON-RPC error**（调用方写错了，该改代码）")
    dump("", srv.handle(make_request(3, METHOD_TOOLS_CALL, {"name": "nope"})))
    print()
    print("  ③ 方法不存在 → -32601")
    dump("", srv.handle(make_request(4, "resources/list")))
    print()
    print("  把 ① 写成 ② 是这里最容易犯的错：它会让模型拿不到「查不到」这个信息，")
    print("  整轮任务直接被打死 —— 和 Milestone 01 讲的「工具失败不要抛异常」是同一件事。")
    print()
    print("  顺带：② 用 -32602（参数不合法）而不是 -32603（内部错误）。")
    print("  后者会让客户端以为是服务端崩了，从而发起毫无意义的重试。")
    print()
    print("  ④ 消息形状不对也要按协议的形状回：")
    dump("", MCPServer().handle({"jsonrpc": "1.0", "id": 1, "method": "x"}))


# ────────────────────────────────────────────────────────────────────── 5
def section_5() -> None:
    show("5. 真的拉起一个子进程（stdio 传输的全部坑都在这）")
    client = spawn_default_server()
    client.start()
    try:
        info = client.initialize()
        print(f"  握手成功：server={info['serverInfo']}  协议={client.protocol_version}")
        print(f"  子进程活着：{client.alive}")
        print()
        names = [t["name"] for t in client.list_tools()]
        print(f"  tools/list → {names}")
        print()
        print("  tools/call（真的在另一个进程里执行的）：")
        print(f"    calculator(6*7) = {client.call_tool('calculator', {'expression': '6*7'}).strip()}")
        hit = client.call_tool("rag_search", {"query": "Project 04 会话落盘"}).splitlines()[0]
        print(f"    rag_search(...) = {hit[:60]}…")
        print()
        print("  未知工具：")
        try:
            client.call_tool("does_not_exist")
        except Exception as exc:
            print(f"    {type(exc).__name__}: {exc}")
        print()
        print("  连续三次调用（验证 id 没有错位）：")
        for i in range(3):
            print(f"    calculator({i}+1) = {client.call_tool('calculator', {'expression': f'{i}+1'}).strip()}")
    finally:
        client.close()
    print()
    print("  stdio 上的三个坑，全部只在真进程上出现，mock 一片绿：")
    print("    · 子进程 stdout 要行缓冲（bufsize=1），否则读不到")
    print("    · 写完必须 flush，否则服务端一直等")
    print("    · 读到空行 = 对端关了，要把 stderr 带出来才知道为什么")


# ────────────────────────────────────────────────────────────────────── 6
def section_6() -> None:
    show("6. 桥接：Agent 不知道工具在另一个进程里")
    from agent.agent import ReActAgent
    from agent.llm import LLMMessage, ScriptedLLM
    from agent.registry import ToolRegistry
    from agent.settings import AgentSettings
    from agent.tools import ToolCall

    client = spawn_default_server()
    client.start()
    try:
        client.initialize()
        bridged = mcp_tools(client)
        print(f"  从 MCP 桥接过来的工具：{[t.name for t in bridged]}")
        print()
        print("  客户端补的那层外壳（服务端只给纯 JSON Schema）：")
        print(f"    {json.dumps(bridged[0].schema(), ensure_ascii=False)[:150]}…")
        print()
        registry = ToolRegistry(bridged)
        print(f"  registry 里：{registry.names()}")
        print("  此刻 registry 和 Agent 都不知道这些工具在另一个进程 —— 这就是 MCP 要的效果。")
        print()
        agent = ReActAgent(
            ScriptedLLM(
                LLMMessage(
                    role="assistant",
                    tool_calls=[ToolCall(id="c1", name="calculator", arguments={"expression": "1024*4"})],
                ),
                LLMMessage(role="assistant", content="1024 乘以 4 等于 4096。"),
            ),
            registry,
            settings=AgentSettings(max_steps=4),
        )
        result = agent.run("1024 乘以 4 是多少？")
        print(result.trace())
    finally:
        client.close()


# ────────────────────────────────────────────────────────────────────── 7
def section_7() -> None:
    show("7. 真实模型用 MCP 工具答题（--real）")
    from agent.agent import ReActAgent
    from agent.llm import DeepSeekLLM
    from agent.registry import ToolRegistry
    from agent.settings import AgentSettings

    client = spawn_default_server()
    client.start()
    try:
        client.initialize()
        agent = ReActAgent(
            DeepSeekLLM(AgentSettings()),
            ToolRegistry(mcp_tools(client)),
            settings=AgentSettings.from_env(max_steps=6),
            system_prompt=(
                "你是一个研究助手。回答问题前先用提供的工具检索，"
                "不要编造工具返回的内容。"
            ),
        )
        result = agent.run("Project 04 的会话是怎么落盘的？")
        print(result.trace())
        print()
        print(f"步数 {result.steps_used} / 工具调用 {len(result.tool_calls)}")
        print("每一次「调用」都是一次跨进程的 JSON-RPC 往返 —— 模型完全不知情。")
    finally:
        client.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="MCP 协议 / Server / Client 演示")
    parser.add_argument("--real", action="store_true", help="调真实 DeepSeek 跑第 7 节")
    args = parser.parse_args()

    print("=" * WIDTH)
    print("  Project 05 · Milestone 07/08/09 —— MCP：协议 / Server / Client")
    print("=" * WIDTH)

    for fn in (section_1, section_2, section_3, section_4, section_5, section_6):
        fn()
    if args.real:
        section_7()
    else:
        show("7. 真实模型（跳过）")
        print("  加 --real 会让 DeepSeek 用 MCP 工具答一题")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
