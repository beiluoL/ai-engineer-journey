# Finetune Series — 大模型微调与企业级部署系列（草稿库）

> **状态：草稿（未人工校对）**。本目录是从对话/笔记导入的原始学习材料，内容尚未逐篇核实，
> 不属于 `projects/` 单一事实源，也不是正式 tutorial。校对通过后择优改写进
> [tutorials/](../tutorials/)（参考：Day1 已改写为 [教程 03](../tutorials/03-llm-finetune-day1-colab-llamafactory-qwen.md)）。

## 内容分级约定

| 标记 | 含义 |
|------|------|
| 📝 草稿 | AI 生成 / 笔记原始态，未校对，可能有事实错误 |
| ✅ 已校对 | 人工核实过事实与代码 |
| 🎓 已学习 | 亲手操作过并能复述（计入 PROGRESS 学习进度） |

当前：**全部 35 篇均为 📝 草稿**。

## 索引

### 基础认知
| 篇 | 文件 |
|----|------|
| Day0.5 | [大模型名词与硬件资源完全解释](Day0.5-大模型名词与硬件资源完全解释.md) |
| Day0.6 | [自己采购硬件](Day0.6-自己采购硬件.md) |
| Day0.7 | [企业级硬件采购视角](Day0.7-企业级硬件采购视角.md) |

> Day1–Day10 已修复：文件名与文首 H1 均已改为可区分的主题标题。

### 第一次微调实战（Day1-10）
| 篇 | 文件 |
|----|------|
| Day1 | [第一次微调实战](Day1-Colab跑通Qwen-LLaMA-Factory.md)（已改写为教程 03） |
| Day2 | [01](Day2-01-数据集注册-dataset-info.md) · [02](Day2-02-QLoRA训练配置-train-yaml.md) · [03](Day2-03-启动QLoRA训练.md) |
| Day3-10 | [Day3](Day3-LoRA接入Ollama-SpringBoot.md) · [Day4](Day4-RAG结合LoRA构建Agent.md) · [Day5](Day5-SpringBoot-Milvus-RAG.md) · [Day6](Day6-RAG-LoRA-ToolCalling-Agent.md) · [Day7](Day7-Agent生产级工程化.md) · [Day8](Day8-包装成求职项目.md) · [Day9](Day9-模拟AI工程师面试.md) · [Day10](Day10-面试100问与项目答辩.md) |

### 企业级部署与平台（Day11-30）
| 篇 | 文件 |
|----|------|
| Day11 | [01 部署完整路线](Day11-01-企业级大模型部署完整路线.md) · [02 实战](Day11-02-实战.md) |
| Day12-16 | [Day12 部署升级](Day12-企业级部署升级.md) · [Day13 LoRA微调部署](Day13-企业级LoRA微调部署实战.md) · [Day14 平台架构](Day14-企业级大模型平台架构.md) · [Day15 RAG优化](Day15-企业级RAG深度优化.md) · [Day16 安全稳定](Day16-企业级大模型安全与稳定性.md) |
| Day17-20 | [Day17 MLOps](Day17-MLOps实战.md) · [Day18 设计答辩](Day18-企业级AI系统完整设计答辩.md) · [Day19 AI产品工程师](Day19-从AI工程师到AI产品工程师.md) · [Day20 AI SaaS MVP](Day20-打造你的第一个AI-SaaS-MVP.md) |
| Day21-25 | [Day21 平台落地](Day21-企业AI平台落地实战.md) · [Day22 AI Agent平台](Day22-打造企业级AI-Agent平台.md) · [Day23 自动化平台](Day23-企业AI自动化平台实战.md) · [Day24 Agent工程化](Day24-AI-Agent工程化进阶.md) · [Day25 Agent开发](Day25-企业级AI-Agent开发实战.md) |
| Day26 | 缺（编号跳过） |
| Day27-30 | [Day27 训练微调实战](Day27-大模型训练与微调完整实战.md) · [Day28 训练环境](Day28-大模型训练环境实战.md) · [Day29 评测上线](Day29-模型评测与生产上线.md) · [Day30 能力闭环](Day30-Java-AI-Engineer完整能力闭环.md) |

## 维护规则

- 校对一篇就把状态表里的 📝 改成 ✅，并在文首加一行 `> 状态：已校对（YYYY-MM-DD）`
- 事实性内容（价格 / 版本号 / API）校对时必须联网核实
- 与 `projects/` 或已有 tutorial 重复的内容，保留 tutorials / projects 版本为准，此处仅存档
