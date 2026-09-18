---
name: git-push
description: 将当前项目的改动提交（commit）并推送（push）到 GitHub。当用户说"提交到 github"、"推送到 github"、"commit"、"push"、"上传代码/笔记"等时使用。
---

# 提交并推送到 GitHub

把当前项目的改动提交并推送到远程 GitHub 仓库（`origin/main`）。

## 项目信息

- 远程仓库：`git@github.com:guangyang-wang/agent-learning.git`
- 默认分支：`main`，远程名：`origin`
- 提交信息约定：**中文**，简洁描述本次改动（参考现有风格，如「新增元组、字典、集合笔记与练习代码」）
- 认证：SSH 密钥已配置，无需重复处理

## 步骤

1. 查看改动：
   - `git status` 看有哪些文件被修改/新增
   - `git diff` 看具体改动内容，确认没有敏感信息（密钥、token 等）

2. 暂存文件：
   - 用 `git add <具体文件名>` 逐个添加，**不要用 `git add -A`**，避免误提交
   - `GitHub上传步骤.md` 已被 `.gitignore` 排除，正常不会出现在 status 里

3. 提交：
   - 写一条中文提交信息，格式：`新增/修改 <内容简述>`
   - 命令：`git commit -m "..."`

4. 推送：
   - `git push origin main`

5. 完成后向用户报告：提交信息 + 是否成功推送 + 远程提交范围（如 `3efd4d6..fbb14e9`）

## 注意

- 如果 `git push` 被拒绝（rejected），先 `git pull --rebase origin main` 再重试；若是首次关联历史，加 `--allow-unrelated-histories`
- 只提交当前项目的学习代码与笔记，不要提交用户未要求的内容
