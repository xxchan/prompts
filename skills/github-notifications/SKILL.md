---
name: github-notifications
description: |
  查看 GitHub 通知并分析是否需要采取行动。使用场景：查看 GitHub 通知、检查未读消息、
  查看 PR/Issue 评论、分析是否需要回复或处理。触发词：GitHub 通知、gh 通知、
  查看通知、有什么消息、PR 评论、Issue 更新。
---

# GitHub Notifications

## 工作流程

### 1. 获取通知列表

```bash
# 获取所有通知（包括已读）
gh api 'notifications?all=true' --jq '.[] | "\(.updated_at) | unread:\(.unread) | \(.repository.full_name) | \(.subject.type) | \(.subject.title)"' | head -30

# 仅获取未读通知
gh api notifications --jq '.[] | "\(.updated_at) | \(.repository.full_name) | \(.subject.type) | \(.subject.title)"'
```

### 2. 查看具体详情

```bash
# 获取通知的详细 URL（用于找到 PR/Issue 编号）
gh api 'notifications?all=false' --jq '.[] | select(.unread==true) | {title: .subject.title, url: .subject.url, reason: .reason}'

# 查看 PR 详情
gh pr view <number> --repo <owner/repo>

# 查看 PR 评论
gh pr view <number> --repo <owner/repo> --comments

# 查看 PR review comments（代码行级评论）
gh api repos/<owner>/<repo>/pulls/<number>/comments --jq '.[] | "---\nauthor: \(.user.login)\npath: \(.path):\(.line // .original_line)\n\(.body)\n"'

# 查看 Issue 详情
gh issue view <number> --repo <owner/repo>
```

### 3. 分析 Action Items

根据通知内容判断是否需要采取行动：

| 情况 | 需要行动 | 行动内容 |
|------|----------|----------|
| 被 @mention 提问 | 是 | 回复问题 |
| PR 收到 review comments | 是 | 处理 comments 或解释 |
| PR 被 request changes | 是 | 修改代码 |
| PR 被 approve | 否 | 等待 merge 或自己 merge |
| 等待 CI/部署授权 | 否 | 等待 maintainer |
| 他人讨论（未直接问你） | 否 | 可选择性参与 |
| 已处理过的 comments | 否 | 检查是否已回复 |

## 输出格式

1. 先显示通知概览表格（时间、仓库、类型、标题、是否未读）
2. 对于未读通知，主动查看详情
3. 总结是否需要采取行动，给出具体建议
