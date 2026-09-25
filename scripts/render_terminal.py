#!/usr/bin/env python3
"""把「命令 + 输出」文本渲染成终端窗口风格的配图。

为什么不用截图：终端截图会带出用户名、路径、无关历史命令，还得手动裁；
而文档要的是"这段代码跑起来是什么样"。用真实 stdout 渲染，内容可控、可复现、可进 git。

用法:
    python3 scripts/render_terminal.py input.txt --out assets/xx.png --title "bash — python3 main.py"
    cat out.txt | python3 scripts/render_terminal.py - --out x.png

约定:
- 以 `$ ` 开头的行 = 命令（绿色提示符）
- 含「错误 / Error / Traceback / FAIL」的行 = 红字
- 以 `# ` 开头的行 = 注释（灰）
- 其余 = 普通输出
- `--prompt` 可改提示符样式（默认 `$ `）
- 长行自动按宽度折行
"""
import argparse
import sys
from PIL import Image, ImageDraw, ImageFont

MONO = "/System/Library/Fonts/Menlo.ttc"
CJK = "/System/Library/Fonts/Hiragino Sans GB.ttc"
BG = (30, 30, 30)
BAR = (58, 58, 58)
FG = (212, 212, 212)
CMD = (126, 231, 135)
ERR = (255, 107, 107)
NOTE = (128, 128, 128)
DOTS = [(255, 95, 86), (255, 189, 46), (39, 201, 63)]


def load(path, size):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default(size)


def split_runs(line):
    """按「ASCII 用等宽 / 非 ASCII 用中文字体」切成片段。"""
    runs, buf, cur = [], "", None
    for ch in line:
        kind = "mono" if ord(ch) < 128 else "cjk"
        if cur is None:
            cur = kind
        if kind != cur:
            runs.append((cur, buf))
            buf, cur = "", kind
        buf += ch
    if buf:
        runs.append((cur, buf))
    return runs


def draw_text(d, x, y, line, mono, cjk, fill):
    for kind, chunk in split_runs(line):
        f = mono if kind == "mono" else cjk
        d.text((x, y), chunk, font=f, fill=fill)
        x += f.getlength(chunk)
    return x


def text_width(line, mono, cjk):
    return sum((mono if k == "mono" else cjk).getlength(c) for k, c in split_runs(line))


def wrap(line, mono, cjk, max_w):
    if text_width(line, mono, cjk) <= max_w:
        return [line]
    out, cur = [], ""
    for ch in line:
        if text_width(cur + ch, mono, cjk) > max_w and cur:
            out.append(cur)
            cur = ch.lstrip() if ch == " " else ch
        else:
            cur += ch
    if cur:
        out.append(cur)
    return out


def color_of(line, is_cmd):
    if is_cmd:
        return CMD
    if any(k in line for k in ("错误", "Error", "Traceback", "FAIL", "失败")):
        return ERR
    return FG


def render(text, out, title="bash", width=960, size=15, scale=2, pad=18, bar_h=34):
    lines = text.rstrip("\n").split("\n")
    mono = load(MONO, size * scale)
    cjk = load(CJK, size * scale)
    lh = int(size * 1.6 * scale)
    max_w = (width - pad * 2) * scale

    wrapped = []
    for raw in lines:
        is_cmd = raw.startswith("$ ")
        body = raw[2:] if is_cmd else raw
        fill = color_of(body, is_cmd)
        if body.lstrip().startswith("# "):
            fill = NOTE
        for w in wrap(body, mono, cjk, max_w) or [""]:
            wrapped.append((w, fill, is_cmd))

    h = bar_h * scale + pad * 2 * scale // 2 + lh * len(wrapped) + pad * scale
    img = Image.new("RGB", (width * scale, h), BG)
    d = ImageDraw.Draw(img)

    d.rectangle([0, 0, width * scale, bar_h * scale], fill=BAR)
    r = 6 * scale
    cy = bar_h * scale // 2
    for i, c in enumerate(DOTS):
        cx = (14 + i * 20) * scale
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=c)
    title_f = load(CJK, int(12 * scale))
    tw = title_f.getlength(title)
    d.text(((width * scale - tw) / 2, cy - int(12 * scale) / 2), title, font=title_f, fill=(190, 190, 190))

    y = bar_h * scale + pad * scale // 1
    for line, fill, is_cmd in wrapped:
        x = pad * scale
        if is_cmd:
            x = draw_text(d, x, y, "$ ", mono, cjk, CMD)
        draw_text(d, x, y, line, mono, cjk, fill)
        y += lh

    img = img.resize((width, h // scale), Image.LANCZOS)
    img.save(out)
    print(f"{out}  {img.size[0]}x{img.size[1]}  ({len(wrapped)} 行)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="文本文件路径，- 表示 stdin")
    ap.add_argument("--out", required=True)
    ap.add_argument("--title", default="bash")
    ap.add_argument("--width", type=int, default=960)
    ap.add_argument("--size", type=int, default=15)
    ap.add_argument("--prompt", default="$ ")
    a = ap.parse_args()

    text = sys.stdin.read() if a.input == "-" else open(a.input, encoding="utf-8").read()
    render(text, a.out, a.title, a.width, a.size)


if __name__ == "__main__":
    main()
