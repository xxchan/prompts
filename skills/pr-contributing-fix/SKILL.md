---
name: pr-contributing-fix
description: Implement a fix and open a PR while following repository contributing rules. Use when asked to make code changes and submit a PR.
---

# PR Contributing Fix

## Workflow
1. Read CONTRIBUTING.md and follow required steps (tests, formatting, changeset).
2. Implement the fix and add/update tests.
3. Create a changeset only if CONTRIBUTING.md requires it.
4. Open a PR with a clear summary and test notes.

## Commands
- Create PR with safe body input:
  `gh pr create --repo OWNER/REPO --head FORK:BRANCH --base main --title "..." --body-file - <<'EOF' ... EOF`
- If inline `--body` fails (shell parsing), prefer `--body-file -`.
