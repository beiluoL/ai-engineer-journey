"""生成侧的最小契约（对应 milestone 09 §3.1「模型层」）。

RAG 的在线问答链路和 P03 的 chat 应用几乎一模一样：
    system + user → LLM → 回答
RAG 只多了两件事 —— 前置的检索阶段和一条离线索引链路。
所以生成侧不重新发明：真实接入层直接复用 P03 的 DeepSeek client；
这里只留下**离线契约**，让 `RAGService.ask()` 能在不联网、不花钱的前提下端到端跑通。

FakeLLMClient 的行为是确定性的：从【参考资料】里挑出和问题最相关的一两句，
带上 [n] 编号拼成答案。它不改变流水线结构，只替换掉"生成"这一步的实现。
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod

from .errors import RAGError

_CONTEXT_BLOCK_RE = re.compile(r"(?m)^\[(\d+)\] \(source: ([^)]+)\)$")
_HEADING_RE = re.compile(r"^\s*#{1,6}\s")
_CJK = r"[一-鿿]"


def _iter_blocks(system: str) -> list[tuple[int, str, str]]:
    r"""把【参考资料】切成 [(编号, 来源, 正文)]。

    为什么不用「一次正则吃掉整块」：块的正文里有换行，`.` 默认不匹配换行，
    写 ``^\[(\d+)\] \(source: ([^)]+)\)\n(.*)$`` 会**只截到块的第一行** ——
    正文的其余部分全丢，最后只能抽到标题行。这里改成先按块首标记切，
    再取该标记到下一个块首之间的内容。
    """
    marks = list(_CONTEXT_BLOCK_RE.finditer(system))
    blocks: list[tuple[int, str, str]] = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(system)
        body = system[m.end():end].lstrip("\n")
        blocks.append((int(m.group(1)), m.group(2), body))
    return blocks


class BaseLLMClient(ABC):
    """生成侧抽象。接真实模型时实现 chat() 即可，RAGService 一行不用改。"""

    model_name: str = ""

    @abstractmethod
    def chat(self, messages: list[dict]) -> str:
        """messages = [{"role": "system"|"user", "content": str}] → 回答文本。"""


class FakeLLMClient(BaseLLMClient):
    """离线替身：从 system 里的【参考资料】中抽取与 user 问题重叠最多的句子。

    它让 09 章的失败语义（检索为空直接拒答、citations 随答案一起产出）
    在没有 API Key 的情况下也能被完整测到。
    """

    model_name = "fake-llm"

    def __init__(self, max_sentences: int = 6, min_overlap: int = 3):
        self.max_sentences = max_sentences
        # 至少命中这么多个 query 词才肯作答，否则视作「资料与问题无关」→ 拒答。
        # 这一条对应 09 章的失败语义 2：宁可说「不知道」，也不要胡编。
        self.min_overlap = min_overlap

    def chat(self, messages: list[dict]) -> str:
        system = next((m["content"] for m in messages if m["role"] == "system"), "")
        user = next((m["content"] for m in messages if m["role"] == "user"), "")
        query_tokens = set(re.findall(_CJK, user)) | {
            w.lower() for w in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", user)}

        picked: list[tuple[int, float, int, str, str]] = []
        for no, source, body in _iter_blocks(system):
            for sent in _split_sentences(body):
                if _HEADING_RE.match(sent):
                    continue          # 标题行不当答案（"## 为什么能省内存" 不是回答）
                toks = set(re.findall(_CJK, sent)) | {
                    w.lower() for w in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", sent)}
                covered = len(toks & query_tokens)
                if covered < self.min_overlap:
                    continue
                # 主排序看「覆盖了多少 query 词」，保证答案里带上关键概念，
                # 次排序看重叠比例，避免挑到最长的那段
                picked.append((covered, covered / max(len(toks), 1), int(no),
                               sent.strip(), source, toks))

        # 按「覆盖了多少 query 词」降序取前几句：候选句子已经按句切好，
        # 排序键是 (覆盖词数, 覆盖比例, 出处编号)，先保概念全，再保句子短。
        # 注意这里不做贪心集合覆盖 —— 先覆盖再覆盖别的词会让第一句（标题行）
        # 把所有词都「占」掉，后面真正带关键词的句子一个都选不进来。
        pool = sorted(picked, key=lambda x: (-x[0], -x[1], x[2]))
        chosen = [(p[2], p[3], p[4]) for p in pool[: self.max_sentences]]
        if not chosen:
            return "知识库中没有相关资料，无法回答这个问题。"
        lines = [f"[{no}] {sent}（来源: {source}）" for no, sent, source in chosen]
        return "根据知识库资料回答：" + "；".join(lines) + "。"


class RAGLLMError(RAGError):
    """生成侧调用失败（09 章失败语义 3：重试一次，仍失败要明确报错）。"""


def _split_sentences(text: str) -> list[str]:
    """按中英文句末标点切句，供 FakeLLMClient 抽取句子用。"""
    parts = re.split(r"(?<=[。！？!?])", text)
    return [p for p in (s.strip() for s in parts) if p]


# --------------------------------------------------------------------------
# 真实接入层
# --------------------------------------------------------------------------
# 踩坑记录（milestone 12）：
#   1. httpx 默认超时只有 5 秒，DeepSeek 首次推理经常 20s+ → 必须显式设 timeout，
#      否则表现为「本地跑得好好的，上线后间歇性 500」。
#   2. 重试只有一层。RAGService 已经会重试一次，client 内部再退避重试就是
#      两层叠加（4 次请求），一次网络抖动的花费翻倍 —— 边界划在「谁离网络近谁重试」。
#   3. 流式的第一个 chunk 常常只有 role、content 为 None，直接拼接会写出 "None"。
# --------------------------------------------------------------------------


_REF_RE = re.compile(r"\[(\d+)\]")


class OpenAICompatibleLLMClient(BaseLLMClient):
    """OpenAI /chat/completions 协议的骨架。

    现在几乎所有国产模型（DeepSeek、通义、智谱、Moonshot……）都兼容这个协议，
    区别只有 base_url 和模型名。把协议骨架抽出来，接新厂商只改两个类属性
    —— 这一点和 03 章的 embedding 层是同一套做法。

    对外只暴露两个方法：
        chat(messages) -> str          同步一次拿全（RAGService 的契约）
        stream(messages) -> Iterator   增量吐字（给 Web 端做 SSE 用，P03 已验证）
    """

    BASE_URL = "https://api.deepseek.com/chat/completions"
    MODEL = "deepseek-chat"
    TIMEOUT = 60.0          # 不是 5 秒：生成类接口首 token 可能等十几秒

    def __init__(self, api_key: str, *, model: str = "", timeout: float = TIMEOUT,
                 temperature: float = 0.0):
        if not api_key:
            raise RAGLLMError("api_key 为空，无法调用大模型接口")
        self.api_key = api_key
        self.model_name = model or self.MODEL
        self.timeout = timeout
        # 12 章：RAG 是「把一段资料复述出来」的任务，不需要创意。
        # temperature 默认给 0：同一个问题两次调用应当基本同结果，
        # 否则你的评测报告每次都在变，前后对比失去意义。
        self.temperature = temperature
        # 12 章：把真实花费记下来。RAG 问答是「每次请求都要付钱」的在线链路，
        # 没计量就等于没上线 —— 出问题时你不知道是模型变贵了还是 prompt 变长了。
        self.last_usage: dict | None = None

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"}

    def chat(self, messages: list[dict]) -> str:
        import httpx

        payload = {"model": self.model_name, "messages": messages,
                   "stream": False, "temperature": self.temperature}
        # 显式 timeout：httpx 默认 5s，对生成接口远远不够
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(self.BASE_URL, headers=self._headers(),
                               json=payload)
            if resp.status_code >= 400:
                raise RAGLLMError(
                    f"LLM 返回 {resp.status_code}: {resp.text[:200]}")
            data = resp.json()
        # 返回体里的 model 可能和你请求时写的不一致（deepseek-chat 实际跑的是
        # deepseek-flash），计费与追踪别拿请求参数当模型名，读返回体。
        self.last_usage = data.get("usage") or None
        choices = data.get("choices") or []
        if not choices:
            raise RAGLLMError(f"LLM 返回没有 choices: {str(data)[:200]}")
        return (choices[0].get("message") or {}).get("content") or ""

    def stream(self, messages: list[dict]) -> str:
        """返回整段文本（demo 里演示流式，但对外仍收成一个字符串）。

        直接 yield token 的生成器更利于 SSE；这里先收敛成字符串，
        是为了和 chat() 共用一套调用点，避免「流式路径和同步路径行为不一致」。
        """
        import httpx

        payload = {"model": self.model_name, "messages": messages,
                   "stream": True, "temperature": self.temperature}
        chunks: list[str] = []
        with httpx.Client(timeout=self.timeout) as client:
            with client.stream("POST", self.BASE_URL, headers=self._headers(),
                               json=payload) as resp:
                if resp.status_code >= 400:
                    raise RAGLLMError(
                        f"LLM 返回 {resp.status_code}: {resp.text[:200]}")
                for line in resp.iter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    payload_str = line[5:].strip()
                    if payload_str in ("[DONE]", ""):
                        continue
                    import json

                    delta = json.loads(payload_str)["choices"][0]["delta"]
                    # 坑 3：有的 chunk 只有 role，content 是 None
                    if delta.get("content"):
                        chunks.append(delta["content"])
        return "".join(chunks)


class DeepSeekLLMClient(OpenAICompatibleLLMClient):
    """DeepSeek 直连（兼容 OpenAI 协议）。

    用法：
        client = DeepSeekLLMClient(api_key=os.environ["DEEPSEEK_API_KEY"])
    没配 key 时直接抛 RAGLLMError，不要用默认值糊过去。
    """

    BASE_URL = "https://api.deepseek.com/chat/completions"
    MODEL = "deepseek-chat"


def parse_answer_refs(answer: str) -> list[int]:
    """从答案里抽模型标出来的引用编号，去重并保持出现顺序。

    真实模型经常不按 prompt 里写的格式标 [1]，而是写在括号里或干脆不标。
    拿不到编号时 cites_nothing=True，上层据此决定「整段算来源不明」。
    """
    seen: list[int] = []
    for m in _REF_RE.finditer(answer or ""):
        n = int(m.group(1))
        if n not in seen:
            seen.append(n)
    return seen
