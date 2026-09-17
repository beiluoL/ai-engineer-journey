# Maintenance — 长期维护规则

## Single Source of Truth【单一事实源】

```text
Curriculum  = 核心学习内容
Labs        = 实验验证
Projects    = 完整可运行项目
Assessments = 能力验证
Knowledge   = 知识关系与索引（不是第二套课程）
Progress    = 学习状态追踪
Publishing  = 对外发布内容（不是知识源）
```

禁止同一知识完整复制 2~3 份。

## 维护清单

每次提交前检查：

- [ ] 没有把课程正文复制到 Publishing 或 Knowledge
- [ ] 项目代码没有复制到 Curriculum
- [ ] 没有提前生成未来所有课程正文
- [ ] 没有留下失效的 Markdown 链接
- [ ] 没有修改远程地址
- [ ] 没有 Push Token / API Key / 私钥
- [ ] Demo 代码在当前环境可运行
- [ ] Commit message 符合规范

## 迁移优先 git mv

目录迁移和重命名优先：

```bash
git mv old new
```

保持 Git 历史可追踪。

## 修改前先扫描

大改动前必做：

```bash
# 扫描旧路径引用
grep -rl "旧路径" . --exclude-dir=.git

# 查看文件统计
find . -type f | sort

# 查看 git 状态
git status
```

## 每次完成后运行

```bash
git diff --stat        # 确认改动范围合理
python -m compileall . # 确认 Python 文件无语法错误（如有）
```
