"""Project 08 —— 路径与跨项目导入。

P08 自己**不重写** Transformer / 自动微分，而是直接复用 P06（Project 06）
手写的 Decoder-Only Transformer。这带来一个必须先解决的问题：``model`` 和
``tokenizer`` 这两个包住在 **P06 的 src 目录**下，不在 P08 里。

于是本模块做两件事：

1. :func:`ensure_p06_importable` —— 把 P06 的 ``src`` 插进 ``sys.path``，
   路径用 :class:`pathlib.Path` 从 ``__file__`` **逐级往上推**（P06 与 P08 是
   同级目录），绝不硬编码绝对路径 —— 这样仓库换台机器 clone 下来照样能跑。
2. 暴露几个常量路径（P07 的 Java 面试数据集、P08 的模型缓存目录），让所有
   demo / 测试引用同一份真实数据，而不是各自抄一份字符串。

设计上刻意「先校验再插入」：如果 P06 目录不存在，抛出带完整路径的清晰错误，
而不是让后面某行 ``from model import ...`` 抛一个看不懂的 ModuleNotFoundError。

另外还有一个不上文档就一定会踩的坑，见 :func:`enable_deterministic_autograd`：
P06 的 ``Tensor._prev`` 是 Python ``set``，反向传播的拓扑序依赖对象地址，
**跨进程不可复现**。本项目要拿真实数字下结论，所以必须在这里补一个
「只改遍历顺序、不改数学」的稳定性开关。
"""

from __future__ import annotations

import itertools
import sys
from pathlib import Path

# ---------------------------------------------------------------- 路径推导
# src/ft/paths.py → parents[0]=src/ft → [1]=src → [2]=projects/08-fine-tuning
P08_ROOT: Path = Path(__file__).resolve().parents[2]
P08_SRC: Path = P08_ROOT / "src"
P08_MODELS: Path = P08_ROOT / "models"

#: P06 与 P08 是 projects/ 下的同级目录
P06_ROOT: Path = P08_ROOT.parent / "06-mini-transformer-llm"
P06_SRC: Path = P06_ROOT / "src"

#: P07 手写、P08 只读的领域数据集（Alpaca 结构）
P07_ROOT: Path = P08_ROOT.parent / "07-open-source-llm"
JAVA_INTERVIEW_JSON: Path = P07_ROOT / "data" / "java_interview.json"


def ensure_p06_importable() -> Path:
    """把 P06 的 ``src`` 加入 ``sys.path``，使其 ``model`` / ``tokenizer`` 可导入。

    返回 P06 的 ``src`` 路径。已插入过则直接返回（幂等）。
    """
    if not P06_SRC.is_dir():
        raise FileNotFoundError(
            "找不到 P06（mini-transformer-llm）的源码目录：\n"
            f"  期望路径: {P06_SRC}\n"
            "P08 的基座模型、自动微分、分词器全部复用 P06，请先确认仓库完整。"
        )
    text = str(P06_SRC)
    if text not in sys.path:
        # 插到最前面：保证 import model 命中的是 P06 的那份，而不是别的同名包
        sys.path.insert(0, text)
    return P06_SRC


def ensure_p07_dataset() -> Path:
    """校验 P07 的 Java 面试数据集存在（只读使用，绝不修改）。"""
    if not JAVA_INTERVIEW_JSON.is_file():
        raise FileNotFoundError(
            "找不到领域数据集：\n"
            f"  期望路径: {JAVA_INTERVIEW_JSON}\n"
            "该文件属于 Project 07，P08 以只读方式复用。"
        )
    return JAVA_INTERVIEW_JSON


# ================================================================ 可复现性
#: 每创建一个 Tensor 递增的序号（见 :func:`enable_deterministic_autograd`）
_SEQ = itertools.count()


def ordered_prev(nodes) -> list:
    """把 ``_prev`` / ``_children`` 变成**按创建顺序排列**的 list。

    P06 里 ``Tensor._prev`` 是 ``set``，set 的迭代顺序由 ``hash(obj)``（即对象
    地址）决定 —— 同一份代码换个进程跑，地址不同 → 反向遍历顺序不同 →
    梯度累加顺序不同 → 每步差 1 ulp。单步看不出来，训 150 步能把困惑度
    从 406 甩到 428（实测）。

    改成按创建序号排序后，遍历顺序由**代码**决定，与地址无关。
    """
    return sorted(set(nodes), key=lambda t: getattr(t, "_seq", -1))


def enable_deterministic_autograd() -> bool:
    """给 P06 的 ``Tensor`` 打一个「只改遍历顺序」的稳定性补丁（幂等）。

    **不修改 P06 的任何文件**（P06 对本任务是只读依赖），只在 P08 进程内
    包一层 ``Tensor.__init__``：

    1. 给每个 Tensor 记一个自增序号 ``_seq``（= 创建顺序）；
    2. 把 ``self._prev`` 从 ``set`` 换成 :func:`ordered_prev` 的结果。

    数学上完全等价 —— 加法换顺序只影响浮点舍入，梯度定义没变。
    但它把「跨进程可复现」从玄学变成了事实：实测开启后，150 步 SFT 的
    困惑度在三个独立进程里逐位相同（412.5235067621249 / 572.4313426261176）。

    返回 True 表示本次真的打了补丁，False 表示之前已经打过。
    """
    ensure_p06_importable()
    from model.autograd import Tensor  # noqa: PLC0415  (必须先插入 sys.path)

    if getattr(Tensor, "_p08_deterministic", False):
        return False

    original_init = Tensor.__init__

    def __init__(self, *args, **kwargs):  # noqa: N807
        original_init(self, *args, **kwargs)
        self._seq = next(_SEQ)
        self._prev = ordered_prev(self._prev)

    Tensor.__init__ = __init__
    Tensor._p08_deterministic = True
    return True


def ensure_dir(path: "str | Path") -> Path:
    """``mkdir -p`` 的 Path 版，返回该目录。"""
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


__all__ = [
    "JAVA_INTERVIEW_JSON",
    "P06_ROOT",
    "P06_SRC",
    "P07_ROOT",
    "P08_MODELS",
    "P08_ROOT",
    "P08_SRC",
    "enable_deterministic_autograd",
    "ensure_dir",
    "ensure_p06_importable",
    "ensure_p07_dataset",
    "ordered_prev",
]

# ⚠ 必须在任何 Tensor 被创建**之前**生效。ft 的每个子模块第一行都是
#   ``from .paths import ...``，所以在 paths 里就地打补丁是唯一可靠的时机。
enable_deterministic_autograd()
