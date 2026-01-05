---
name: review-ci-followup
description: Address PR review feedback and follow up on CI status. Use when asked to respond to review comments, resolve threads, or interpret CI results.
---

# Review CI Followup

## Workflow
1. Evaluate each review comment from first principles; do not assume the reviewer is correct.
2. Prioritize substantive issues; treat style/polish feedback as optional.
3. If feedback is a small preference change, it's OK to accept; otherwise reply with rationale.
4. Resolve review threads; use GraphQL if gh lacks a command.
5. Check CI status and explain blockers or required approvals.
6. Update the PR with follow-up notes if needed.

## Commands
- List review threads (IDs + resolved state):
  `gh api graphql -f query='query($owner:String!,$repo:String!,$number:Int!){repository(owner:$owner,name:$repo){pullRequest(number:$number){reviewThreads(first:50){nodes{id isResolved comments(last:5){nodes{id author{login} bodyText}}}}}}}' -F owner=OWNER -F repo=REPO -F number=PR_NUMBER`
- Resolve a thread (when gh has no native command):
  `gh api graphql -f query='mutation($id:ID!){resolveReviewThread(input:{threadId:$id}){thread{id isResolved}}}' -F id=THREAD_ID`
- Check CI status rollup:
  `gh pr view PR_NUMBER --repo OWNER/REPO --json statusCheckRollup`
- Fetch line comments:
  `gh api repos/OWNER/REPO/pulls/PR_NUMBER/comments`
