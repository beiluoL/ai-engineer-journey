#!/usr/bin/env python3
"""命令行待办清单 —— python-practice/01-todo-cli

任务卡与讲解：python-practice/01-todo-cli/README.md

设计原则（也是本练习的知识点）：
1. **零第三方依赖** —— 只用标准库 argparse / json / dataclasses / datetime / pathlib。
   目的是先把 Python 本身吃透，而不是先学会调库。
2. **数据与界面分离** —— Store 只管读写文件，CLI 只管打印和解析参数。
   分开之后你才能给 Store 写单元测试（见 README「进阶挑战」）。
3. **错误要讲人话** —— 用户输错 id 时不应该看到 traceback，而是
   「没有 id=99 的待办」。所以用自定义 TodoError + main() 统一兜底。

运行：
    python3 todo.py add "读完官方教程第 3 章"
    python3 todo.py list
    python3 todo.py done 1
    python3 todo.py rm 1
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

# 待办数据默认存到「当前目录」的 todos.json。
# 刻意不用 ~/.todo.json：练习项目希望数据就在眼前，方便你 cat 出来看结构。
DEFAULT_FILE = Path("todos.json")

# 打印表格时的列宽。中文在终端里按「字符数」对齐会歪，所以最后统一用
# 等宽空格补齐；真正的宽字符对齐方案留作 README 的进阶挑战。
W_ID = 4
W_STATE = 5


class TodoError(Exception):
    """用户级错误：打印一句话即可，不需要 traceback。

    区分「用户级错误」和「程序 bug」是工程习惯：
    前者是 PEBKAC（输错命令），后者该炸就炸并保留堆栈。
    """


@dataclass
class Item:
    """一条待办。dataclass 自动生成 __init__ / __repr__ / __eq__。"""

    id: int
    text: str
    done: bool = False
    created: str = ""

    @classmethod
    def new(cls, item_id: int, text: str) -> "Item":
        """工厂方法：统一给 created 打时间戳，避免调用方到处写 strftime。"""
        return cls(
            id=item_id,
            text=text,
            done=False,
            created=datetime.now().strftime("%Y-%m-%d %H:%M"),
        )


class Store:
    """JSON 文件仓库。所有落盘都经过这里，路径可注入 —— 方便测试。"""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.items: list[Item] = []
        self.next_id: int = 1
        self._load()

    # ---------- 读写 ----------

    def _load(self) -> None:
        """文件不存在 = 全新开始（不是错误）。文件坏了 = 报人话错误。"""
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise TodoError(
                f"{self.path} 不是合法 JSON（{exc.msg} @ 第 {exc.lineno} 行）"
                f" —— 修好它，或者直接删掉重新开始"
            ) from exc
        self.next_id = int(raw.get("next_id", 1))
        # 逐条构造 Item 而不是直接 dict 用到底：这样字段少了/多了会当场报错，
        # 而不是安静地带着脏数据跑下去。
        self.items = [Item(**it) for it in raw.get("items", [])]

    def save(self) -> None:
        data = {"next_id": self.next_id, "items": [asdict(i) for i in self.items]}
        # ensure_ascii=False 让中文以原样写入（否则会变成 \u4e2d\u6587，人看不懂）；
        # 末尾补一个换行，是 Git 友好 + 命令行工具的好习惯。
        self.path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    # ---------- 业务 ----------

    def add(self, text: str) -> Item:
        text = text.strip()
        if not text:
            raise TodoError("待办内容不能为空")
        item = Item.new(self.next_id, text)
        self.next_id += 1
        self.items.append(item)
        self.save()
        return item

    def find(self, item_id: int) -> Item:
        for it in self.items:
            if it.id == item_id:
                return it
        raise TodoError(f"没有 id={item_id} 的待办（先跑 `list` 看现有编号）")

    def done(self, item_id: int) -> Item:
        it = self.find(item_id)
        if it.done:
            raise TodoError(f"id={item_id} 早就完成了（{it.text}）")
        it.done = True
        self.save()
        return it

    def rm(self, item_id: int) -> Item:
        it = self.find(item_id)
        self.items.remove(it)
        self.save()
        return it

    # ---------- 展示 ----------

    def render(self) -> str:
        if not self.items:
            return "（还没有待办。用 `add \"要做的事\"` 添加第一条）"
        lines = [f"{'ID':<{W_ID}}{'状态':<{W_STATE}}内容"]
        for it in self.items:
            mark = "[x]" if it.done else "[ ]"
            lines.append(f"#{it.id:<{W_ID - 1}}{mark:<{W_STATE}}{it.text}   ({it.created})")
        left = sum(1 for i in self.items if not i.done)
        lines.append(f"\n共 {len(self.items)} 项，{left} 项未完成")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# 命令行入口
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="todo",
        description="命令行待办清单（零依赖，数据存本地 JSON）",
    )
    p.add_argument(
        "--file",
        type=Path,
        default=DEFAULT_FILE,
        help=f"数据文件路径（默认 ./{DEFAULT_FILE}）",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add", help="新增一条待办")
    a.add_argument("text", help="待办内容")

    sub.add_parser("list", help="列出全部待办")

    d = sub.add_parser("done", help="把某条标记为完成")
    d.add_argument("id", type=int, help="待办编号")

    r = sub.add_parser("rm", help="删除某条待办")
    r.add_argument("id", type=int, help="待办编号")

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    store = Store(args.file)

    try:
        if args.cmd == "add":
            item = store.add(args.text)
            print(f"已添加 #{item.id}: {item.text}")
        elif args.cmd == "list":
            print(store.render())
        elif args.cmd == "done":
            item = store.done(args.id)
            print(f"已完成 #{item.id}: {item.text}")
        elif args.cmd == "rm":
            item = store.rm(args.id)
            print(f"已删除 #{item.id}: {item.text}")
        else:  # pragma: no cover - argparse 已保证不会走到
            raise TodoError(f"未知命令 {args.cmd}")
    except TodoError as exc:
        # 只打印「人话」，并把退出码设成 1 —— 这样脚本里可以 if 判断
        print(f"错误：{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
