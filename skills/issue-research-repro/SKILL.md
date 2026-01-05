---
name: issue-research-repro
description: Research existing issues and background discussions, then produce a minimal reproducible example (MRE) for a bug report. Use when asked to search prior issues, gather context, or write a minimal repro.
---

# Issue Research Repro

## Workflow
1. Search existing issues, discussions, and docs for prior context.
2. Summarize the relevant background with links and short notes.
3. Build a minimal reproducible example (smallest input and steps).
4. State expected vs actual behavior in a short block.

## Commands
- Search issues: `gh search issues --repo OWNER/REPO "query" --limit 20`
- View issue context: `gh issue view <id> --repo OWNER/REPO --comments`
- Create issue safely (avoid shell parsing errors):
  `gh issue create --repo OWNER/REPO --title "..." --body-file - <<'EOF' ... EOF`
- If `--body "..."` fails due to shell parsing, use `--body-file -` with heredoc.
