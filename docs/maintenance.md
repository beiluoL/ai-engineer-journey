# Maintenance — 仓库维护规则

## 七个模块的职责边界

```text
Curriculum  = 正式课程源（唯一事实源）
Labs        = 单点技术实验
Projects    = 完整可运行项目
Assessments = 能力验证（quizzes / coding / interviews / benchmarks）
Knowledge   = 知识关系与索引（不复制 Curriculum 正文）
Progress    = 学习状态追踪
Publishing  = 对外发布内容（不是知识源）
```

## 核心规则

### 单一事实源

同一个知识内容不要完整维护两份。

- Curriculum 是唯一的课程正文来源
- Knowledge 只存索引、关系、术语
- Publishing 是二次加工的输出，不是知识源

### 目录命名

统一 kebab-case：

```text
02-list-dict/
python-ai-cli/
fine-tuning/
```

### Git 提交规范

```text
feat:     新功能/新课程/新项目
fix:      修复
docs:     文档
refactor: 重构
test:     测试
chore:    杂项
```

### 安全红线

严禁提交：API Key / Token / 密码 / SSH 私钥 / `.env`。

### 迁移优先 git mv

目录迁移和重命名优先 git mv，保持 Git 历史可追踪。

### 修改前先扫描

大改动前：

```bash
grep -rl "旧路径" . --exclude-dir=.git
git diff --stat
```

### 每次完成后

```bash
python -m compileall .  # Python 语法检查
git diff --stat          # 确认改动范围合理
```
