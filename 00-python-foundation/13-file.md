# 13 — File：文件读写

## 它是什么
读写磁盘文件。Project 01 v0.5 保存对话历史、Phase 3 解析 PDF/Markdown 知识库文档，全靠它。

## Java 开发者如何理解

```java
// Java：七行起步，还要处理 IOException
try (BufferedReader r = new BufferedReader(new FileReader("a.txt"))) {
    r.lines().forEach(System.out::println);
}
```

```python
# Python：with 自动关文件（≈ try-with-resources）
with open("a.txt", encoding="utf-8") as f:
    for line in f:
        print(line, end="")
```

**牢记 `encoding="utf-8"`**：Windows 默认 GBK，中文文件不指定编码迟早乱码。

## 模式与常用操作

```python
# 模式："r"读 / "w"覆盖写 / "a"追加 / "b"二进制（组合如 "rb"）
with open("chat.log", "a", encoding="utf-8") as f:      # a=追加，保存历史用它
    f.write("[user] 什么是 RAG？\n")

with open("chat.log", "r", encoding="utf-8") as f:
    content = f.read()          # 一次全读
    # lines = f.readlines()     # 按行读成 list
    # 逐行遍历大文件最优（内存友好，知识库文档解析就靠它）

from pathlib import Path        # 现代路径操作，替代 os.path
p = Path("data") / "docs" / "readme.md"   # 跨平台拼路径（不用手写 / 或 \）
p.exists(), p.suffix, p.name, p.parent
p.read_text(encoding="utf-8")             # 读小文件一步到位
Path("out").mkdir(parents=True, exist_ok=True)   # 建目录（存在不报错）
```

## 最小可运行 Demo

```python
# demo_file.py —— 对话历史存取（v0.5 的原型）
from pathlib import Path

def save_history(history: list[str], path: str = "chat_history.txt") -> None:
    with open(path, "a", encoding="utf-8") as f:
        for line in history:
            f.write(line + "\n")

def load_history(path: str = "chat_history.txt") -> list[str]:
    p = Path(path)
    if not p.exists():
        return []
    return p.read_text(encoding="utf-8").splitlines()

save_history(["[user] 什么是 Token？", "[assistant] 模型处理文本的最小单位。"])
save_history(["[user] 那 Embedding 呢？"])          # 再存一次验证追加
for line in load_history():
    print(line)
```

## 常见错误

1. **忘 encoding**：中文环境默认编码不一致 → 乱码/`UnicodeDecodeError`。所有文本 open 都显式 `encoding="utf-8"`。
2. **`"w"` 覆盖旧文件**：想追加却用 w，历史直接清空——存日志/历史用 `"a"`。
3. **手写路径分隔符**：`"data\docs"` 在 macOS/Linux 直接坏掉，用 `Path` 或 `/`。
4. **读不存在的文件**：`open` 直接 `FileNotFoundError`，先 `Path.exists()` 或用 try/except。
5. **忘 with**：文件句柄不关闭（Python 有 GC 兜底但不保证时机），坚持 with。

## 常见面试问题
- with 语句的本质？→ 上下文管理器协议（`__enter__`/`__exit__`），保证退出时释放资源，等价 Java try-with-resources。
- 大文件怎么读？→ 逐行迭代或分块 `f.read(chunk_size)`，不要 `read()` 全量进内存。

## 练习
1. 把三行对话追加写入文件再读出来。
2. 用 pathlib 判断 `data/history.json` 是否存在。
3. 逐行读取一个 10 万行的大文件并统计行数（验证内存友好）。

[下一课：14-json →](14-json.md)
