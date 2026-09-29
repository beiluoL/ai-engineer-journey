# P07 Colab 使用说明（Open Source LLM）

本目录的 `p07_colab.ipynb` 是 Project 07 的全部 9 个 Milestone 的**真实可跑** notebook。
目标：在云端 GPU 上亲手加载 / 推理 / 量化 / 服务一个开源模型（Qwen2.5-0.5B-Instruct），本机零磁盘与内存占用。

## 一、在 Colab 打开并运行

1. 上传 `p07_colab.ipynb` 到 Google Colab（或点 `File → Open` 选本地文件）。
2. 顶部菜单：`Runtime → Change runtime type → Hardware accelerator = GPU`（选 T4 免费即可）。
3. `Runtime → Run all`（或逐节 `Shift+Enter`）。
4. 全程会自动 `pip -U transformers bitsandbytes`（如需要）并从 Hugging Face 下载 Qwen2.5-0.5B（约 1GB，Colab 带宽很快）。

## 二、回收真实输出（用于生成文档截图）

notebook 每节都会 `print` 真实数字（参数量、显存、延迟、生成文本等）。请把这些输出按 milestone 落到本仓库，
我再用 `scripts/render_terminal.py` 渲染成截图并撰写 `milestones/01-09`。

**方式 A（推荐，最省力）**：跑完后把每个 milestone 节（M01–M09）对应 cell 的输出文本，
分别存成文件：

```
projects/07-open-source-llm/demos/out/colab_M01.txt
projects/07-open-source-llm/demos/out/colab_M02.txt
...
projects/07-open-source-llm/demos/out/colab_M09.txt
```

> 每个文件只放该节代码的真实 stdout（从 `=== ... ===` 到该节结束），不要夹杂其他。

**方式 B（更省事）**：直接把 Colab 全部输出（或截图）贴回对话，我负责拆分与渲染。

## 三、M08 量化的两条路线（说明）

- **Colab（CUDA T4）**：notebook 里用 `load_in_4bit=True`（bitsandbytes）真跑，看 4-bit 权重大小与生成。
- **Mac 本地（无 CUDA）**：对应走 GGUF（q4_0 / q4_k_m）+ llama.cpp，不依赖 bitsandbytes。
  Mac 本地若想实操，可后续单独补一个 `llama.cpp` 的 demo（不在本 notebook 内）。

## 四、FAQ

- **Q：Colab 报 `bitsandbytes` 找不到？** A：notebook 顶部已含 `!pip install -q -U bitsandbytes`；若仍失败，换 `Runtime → GPU` 重连一次。
- **Q：模型下载慢/失败？** A：Colab 直连 HF 通常很快；如遇限流，可重跑「M03 Model Loading」那节。
- **Q：一定要 Colab 吗？** A：不是。本机若愿意装 torch（M1 MPS 已验证可用），把 `device_map` 改为 `"mps"` 也能跑；但本项目当前阶段按「云端真跑」推进。
