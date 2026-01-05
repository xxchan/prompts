---
name: system-diagnosis
description: "Diagnose system performance issues: CPU/memory usage, disk space, and cleanup. Use when user asks: what's slowing down my computer, why is my Mac slow, what's using CPU/memory/disk, check system performance, find resource hogs, free up space, clean disk, 电脑卡, 查看系统占用, 什么进程占用资源, 磁盘清理, 清理缓存, 磁盘空间不足. Shows process trees and identifies cleanable items."
---

# System Diagnosis

Diagnose CPU/memory issues, swap usage, orphan processes, disk space, and cleanup.

## Usage

```bash
python3 {{SKILL_PATH}}/scripts/diagnose.py
python3 {{SKILL_PATH}}/scripts/diagnose.py --mem      # Sort by memory
python3 {{SKILL_PATH}}/scripts/diagnose.py --limit 15 # Show top 15
```

## IMPORTANT: First Response Guidelines

When user asks about system performance (电脑卡、什么占用资源), you MUST run BOTH commands in parallel and present results together:

```bash
# Run these two in parallel
python3 {{SKILL_PATH}}/scripts/diagnose.py --limit 10           # CPU sorted
python3 {{SKILL_PATH}}/scripts/diagnose.py --mem --limit 10     # Memory sorted
```

Then present a clear summary showing:
1. **System Overview** (CPU%, Memory%, Swap%)
2. **Top CPU consumers** - table with process name, CPU%, MEM%
3. **Top Memory consumers** - table with process name, MEM%, estimated size
4. **Actionable suggestions** if any issues found

Users want to know WHO is using resources immediately, not just overall percentages.

## Output Sections

1. **System Overview**: CPU, memory, swap, memory pressure, paging activity
2. **Swap Estimation**: Processes likely using swap (VSIZE - RSS)
3. **Orphan Processes**: Abandoned dev processes (node/npm/bun with PPID=1)
4. **Top Processes**: Resource consumers with full ancestry tree

## Orphan Process Detection (with Tree Analysis)

Detects abandoned dev processes - PPID=1 processes matching:
- `node`, `npm`, `npx`, `bun`, `deno`
- `python`, `ruby`, `perl`
- `chrome-devtools`, `webpack`, `vite`, `next-server`

**Now includes process tree analysis**: finds all descendant processes of orphans, so killing the root kills the entire tree (prevents child processes from becoming new orphans).

Output example:
```
ORPHAN PROCESSES (3 roots, 6 total with children)
  PID 12345  | 02-05:30:00 |  10.5 MB | bun run dev
  └─ PID 12350  |    8.2 MB | node /path/to/next-server

  PID 12400  |     01:30:00 |   5.5 MB | npm exec chrome-devtools-mcp...
  └─ PID 12410  |   12.0 MB | node /path/to/chrome-devtools

  To kill all (6 processes): kill 12345 12350 12400 12410 ...
```

## Process Tree Example

```
#1 [12345] CPU: 95.0%  MEM: 2.1%
   Command: node /path/to/next-server
   Process Tree (child → parent):
   ── [12345] node /path/to/next-server
     └─ [12340] node /path/to/npm run dev
       └─ [12335] /bin/zsh
         └─ [12330] /Applications/Cursor.app/.../Cursor Helper
```

Reveals `next-server` was started via `npm run dev` inside Cursor IDE.
