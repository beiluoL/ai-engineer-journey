# Contributing — 仓库维护规范

> 本仓库是个人学习系统 + 开源项目。所有改动（包括 AI 协助生成）都遵守本规范。

## 1. 单一事实源

- **知识只维护在 `projects/*/milestones/`**。`publishing/` 只是派生输出，禁止在两处平行维护同一知识。
- 禁止出现平行知识体系：`curriculum/`、`labs/`、`knowledge/`、`assessments/`。

## 2. 文件命名

| 内容 | 规则 | 示例 |
|------|------|------|
| milestone | `NN-english-slug.md`（两位序号 + 英文短横线） | `04-dataclass.md` |
| tutorial | `NN-english-slug.md/.html` | `04-enterprise-llm-deploy-gpu-vllm-springboot.md` |
| 错误记录 | `YYYY-MM-DD-slug.md` | `2026-09-15-package-init-export-miss.md` |
| 配图 | `site-*` / `term-*` / `colab-*` / `diagram-*` 前缀 | `colab-nvidia-smi-t4.png` |

中文标题写在文档 H1 / 副标题里，不进文件名。

## 3. 内容分级（防「假装学会」）

| 标记 | 含义 |
|------|------|
| 📝 草稿 | AI 生成或笔记原始态，未核实 |
| ✅ 已校对 | 人工核实事实与代码（价格/版本/API 必须联网核实） |
| 🎓 已学习 | 亲手跑通 + 能复述，计入 PROGRESS 学习进度轨 |

只有 🎓 才能写进 PROGRESS 的学习轨；publishing/finetune-series 等草稿库的头部 README 负责维护分级。

## 4. 代码规范

- 类型注解齐全；模块 docstring 说明「对应哪个 milestone」且**引用路径必须真实存在**
- 异常不允许静默吞掉；对外行为（HTTP 状态、退出码）有明确映射
- 每个项目的核心逻辑有单元测试（unittest 起步，Project 02 起切 pytest）
- v0.1 项目允许零依赖标准库实现；引入第三方库时同步给 `requirements.txt`（版本用 `==` 锚定）+ `.env.example`

## 5. 文档同步规矩（防漂移）

- **结构性重构（移动/删除目录）的 commit，必须同步修复所有引用旧路径的文件**，commit message 附「受影响引用清单」
- README / PROGRESS / ROADMAP 与仓库现实不一致，视为 bug
- 提交前跑一遍：`grep -rnE "已删除目录名" --include="*.py" --include="*.md" projects/ README.md`

## 6. Git 约定

- Commit message 用约定式前缀：`feat:` / `fix:` / `docs:` / `refactor:` / `test:` / `chore:` / `experiment:`
- 双远程：origin（GitHub）+ gitee（Gitee）。**是否推送、推送到哪，由维护者当场决定**；未明确授权时不推送
- 每个完整学习/开发任务一个 commit；里程碑打 tag

## 7. 安全

- API Key / Token / 密码只走环境变量或本地 `.env`（已 gitignore），仓库只有 `.env.example`
- 严禁在任何文件、日志、截图里出现真实凭证
