# Development Rules — 开发规则

> 本文件是 AI Engineer Journey 的长期开发规范。写代码、提交、同步时按此执行。

## 1. Git 提交规范

```text
feat:     新功能/新课程/新项目
fix:      修复
docs:     文档
refactor: 重构
test:     测试
chore:    杂项
experiment: 实验
```

禁止使用：`update` / `test` / `aaa` / `temp` 等模糊 Commit message。

## 2. 同步双远程

```bash
git push origin main   # GitHub
git push gitee main    # Gitee
```

不要使用 `git push --force`。

确认两个远程一致：

```bash
git ls-remote origin HEAD
git ls-remote gitee HEAD
```

## 3. 安全红线

严禁提交：

```text
API Key
Token
密码
SSH 私钥
.env 文件
```

`.env` 只允许通过 `.env.example` 模板提供占位符。

## 4. 代码规范

- Python 代码用类型提示（Phase 0 后期开始引入）
- 文件用 UTF-8 编码
- 用 snake_case 命名变量和函数
- 用 PascalCase 命名类
- 每个脚本可独立运行，给出运行命令和预期输出

## 5. 目录维护

- 不要机械创建空目录
- 有实际用途的目录用 `.gitkeep`
- 主要目录用 `README.md` 说明用途
- 不要为了"看起来完整"产生大量空文件

## 6. 不提前过度工程化

现在不要：

- 创建复杂 Python 包
- 提前引入 FastAPI / LangChain / PyTorch
- 提前引入数据库
- 提前实现 RAG / Agent

让复杂度自然增长。

## 7. 仓库结构维护

每学一个新知识，先判断：

```text
属于哪个 Phase
 ↓
哪个 Lesson
 ↓
哪个 Project
 ↓
哪个 Exercise
 ↓
哪个 Knowledge Map 节点
 ↓
哪个文章素材
```

不要让项目随学习过程越来越乱。
