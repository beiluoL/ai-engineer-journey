"""08 章：把检索结果组装成最终 prompt 的【参考资料】段。

看四件事：① 编号 [1][2] 与 source#锚点；② citations 列表；
③ 预算怎么吃掉的（装不下就整条截断，不切一半）；④ min_score 过滤噪声。
"""

from __future__ import annotations

from common import head, note, rule

from rag.assembler import ContextAssembler
from rag.cli import build_components
from rag.chunker import estimate_tokens

QUERY = "生成器为什么能省内存"


def main() -> int:
    head("python demos/demo_08_assemble.py")
    settings, embedding, store, retriever, service = build_components(
        profile="dev", fake=True, top_k=5, index_paths=["data/"])
    budget = settings.effective_budget()

    scored = retriever.retrieve(QUERY, top_k=5, mode="vector")
    print(f"\n问题：{QUERY}")
    print(f"检索到 {len(scored)} 个 chunk（分数 "
          f"{scored[0].score:.4f} ~ {scored[-1].score:.4f}）")
    print(f"settings：budget_tokens={settings.budget_tokens}  "
          f"context_window={settings.context_window}  "
          f"reserved_output={settings.reserved_output}")
    print(f"effective_budget() = min({settings.budget_tokens}, "
          f"{settings.context_window} − {settings.reserved_output}) = {budget}")

    rule("① 组装：ContextAssembler(min_score=...).build(query, scored, budget)")
    assembler = ContextAssembler(min_score=settings.min_score)
    ctx = assembler.build(QUERY, scored, budget)
    print(f"用了 {ctx.n_used} 条 / 检索 {len(scored)} 条，占用 {ctx.context_tokens} token")
    lines = ctx.context_text.splitlines()
    print("--- context_text 结构预览（前 4 行）---")
    for ln in lines[:4]:
        print(f"  | {ln}")
    print("    ...")
    print(f"--- 共 {len(ctx.context_text)} 字符 / {len(lines)} 行，"
          f"estimate_tokens = {estimate_tokens(ctx.context_text)} ---")
    print("    每条的格式都是 `[编号] (source: 文件#锚点)` + 正文")

    rule("② citations：引用列表（临时编号 + 可回原文档的稳定定位键）")
    for c in ctx.citations:
        print(f"    [{c.no}] {c.source}  index={c.chunk_index}  "
              f"start_char={c.start_char}  anchor={c.anchor()}")
    print("    编号 no 是本次问答临时的；source/chunk_index/start_char 才能回到原文档")

    rule("③ 预算不够：整条丢弃，绝不切一半进来")
    mid = assembler.build(QUERY, scored, 400)
    tiny = assembler.build(QUERY, scored, 200)
    print(f"    budget=400 → 用 {mid.n_used} 条，{mid.context_tokens} token")
    print(f"    budget=200（比最小的一块还装不下） → 用 {tiny.n_used} 条，"
          f"{tiny.context_tokens} token")
    print("    预算是按「条」切的：半句话进来会让模型读断，宁可少放一条完整的")

    rule("④ min_score 过滤：把阈值抬到 0.49，低于它的资料整条丢弃")
    strict = ContextAssembler(min_score=0.49).build(QUERY, scored, budget)
    print(f"    min_score=0.49 → 用 {strict.n_used} 条（检索给的是 {len(scored)} 条）")
    for h in scored:
        print(f"    score={h.score:.4f} "
              f"{'装' if h.score >= 0.49 else '丢'}  chunk#{h.chunk.index}")

    rule("⑤ 去重：overlap 块近似重复，第二次遇到的会被跳过")
    dup_pair = [(scored[0], scored[0].chunk.text)]
    print(f"    同一段文字塞两次 → 第二次被 seen 集合拦掉："
          f"{len(assembler.build(QUERY, list(scored) + [scored[0]], budget).citations)} 条引用"
          f"（只放了一次，原始 {len(scored) + 1} 条）")

    note("编号与 citations 在同一次遍历里生成；排序、去重、预算任一步改顺序，两者天然一致")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
