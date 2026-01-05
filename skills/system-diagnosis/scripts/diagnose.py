#!/usr/bin/env python3
"""
System diagnosis script: CPU, memory usage, and process ancestry tracking.
"""

import subprocess
import sys
from dataclasses import dataclass


@dataclass
class ProcessInfo:
    pid: int
    ppid: int
    cpu: float
    mem: float
    command: str
    vsize_mb: float = 0.0  # Virtual memory size
    rss_mb: float = 0.0    # Resident set size (physical memory)


def get_top_processes(sort_by: str = "cpu", limit: int = 10) -> list[ProcessInfo]:
    """Get top processes sorted by CPU or memory usage."""
    # ps output: PID, PPID, %CPU, %MEM, COMMAND (full)
    result = subprocess.run(
        ["ps", "-eo", "pid,ppid,pcpu,pmem,command", "-r"],
        capture_output=True,
        text=True,
    )

    processes = []
    for line in result.stdout.strip().split("\n")[1:]:  # Skip header
        parts = line.split(None, 4)
        if len(parts) < 5:
            continue
        try:
            processes.append(
                ProcessInfo(
                    pid=int(parts[0]),
                    ppid=int(parts[1]),
                    cpu=float(parts[2]),
                    mem=float(parts[3]),
                    command=parts[4],
                )
            )
        except (ValueError, IndexError):
            continue

    if sort_by == "mem":
        processes.sort(key=lambda p: p.mem, reverse=True)
    # Already sorted by CPU from ps -r

    return processes[:limit]


def get_processes_with_memory() -> list[ProcessInfo]:
    """Get all processes with memory details (VSIZE and RSS)."""
    # ps output: PID, PPID, %CPU, %MEM, VSZ (KB), RSS (KB), COMMAND
    result = subprocess.run(
        ["ps", "-eo", "pid,ppid,pcpu,pmem,vsz,rss,command"],
        capture_output=True,
        text=True,
    )

    processes = []
    for line in result.stdout.strip().split("\n")[1:]:  # Skip header
        parts = line.split(None, 6)
        if len(parts) < 7:
            continue
        try:
            processes.append(
                ProcessInfo(
                    pid=int(parts[0]),
                    ppid=int(parts[1]),
                    cpu=float(parts[2]),
                    mem=float(parts[3]),
                    command=parts[6],
                    vsize_mb=int(parts[4]) / 1024,  # KB to MB
                    rss_mb=int(parts[5]) / 1024,    # KB to MB
                )
            )
        except (ValueError, IndexError):
            continue

    return processes


def get_swap_heavy_processes(processes: list[ProcessInfo], limit: int = 10) -> list[tuple[ProcessInfo, float]]:
    """
    Estimate which processes are using swap by comparing VSIZE - RSS.
    This is an approximation since VSIZE includes shared libs and mapped files.
    """
    # Calculate estimated "swapped" memory (VSIZE - RSS)
    # Filter out kernel/system processes with huge VSIZE but low actual usage
    swap_estimates = []
    for proc in processes:
        # Skip processes with very high VSIZE (likely shared mappings, not actual swap)
        if proc.vsize_mb > 100000:  # > 100GB virtual = likely kernel/shared
            continue
        # Estimated swap = VSIZE - RSS (rough approximation)
        estimated_swap = max(0, proc.vsize_mb - proc.rss_mb)
        if estimated_swap > 100:  # Only show if > 100MB estimated
            swap_estimates.append((proc, estimated_swap))

    # Sort by estimated swap usage
    swap_estimates.sort(key=lambda x: x[1], reverse=True)
    return swap_estimates[:limit]


@dataclass
class OrphanProcess:
    pid: int
    etime: str  # Elapsed time
    rss_mb: float
    command: str


@dataclass
class OrphanTree:
    """An orphan process with its descendant tree."""
    root: OrphanProcess
    descendants: list["OrphanTree"]  # Child processes

    def all_pids(self) -> list[int]:
        """Get all PIDs in this tree (root + all descendants)."""
        pids = [self.root.pid]
        for child in self.descendants:
            pids.extend(child.all_pids())
        return pids

    def total_memory(self) -> float:
        """Get total memory of root + all descendants."""
        total = self.root.rss_mb
        for child in self.descendants:
            total += child.total_memory()
        return total


def parse_etime(etime: str) -> int:
    """Convert elapsed time string to seconds for sorting."""
    # Format: [[DD-]HH:]MM:SS or MM:SS
    total = 0
    if "-" in etime:
        days, rest = etime.split("-", 1)
        total += int(days) * 86400
        etime = rest
    parts = etime.split(":")
    if len(parts) == 3:
        total += int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    elif len(parts) == 2:
        total += int(parts[0]) * 60 + int(parts[1])
    return total


def get_orphan_processes() -> list[OrphanTree]:
    """
    Detect orphan processes - processes with PPID=1 that are likely
    abandoned dev/script processes rather than legitimate daemons.
    Now includes process tree analysis to find all descendants.
    """
    # Patterns that indicate a script/dev process (likely orphan if PPID=1)
    orphan_patterns = [
        "node ", "npm ", "npx ", "bun ", "deno ",
        "python ", "python3 ", "ruby ", "perl ",
        "chrome-devtools", "webpack", "vite", "next-server",
        "ts-node", "tsx ", "esbuild", "turbo ",
    ]

    # Patterns that indicate legitimate daemon/service (not orphan)
    legitimate_patterns = [
        "/System/", "/usr/libexec/", "/usr/sbin/", "/sbin/",
        "/Library/Apple/", "/Library/PrivilegedHelperTools/",
        ".app/Contents/MacOS/",  # App main executables
    ]

    result = subprocess.run(
        ["ps", "-eo", "pid,ppid,etime,rss,command"],
        capture_output=True,
        text=True,
    )

    # Build process info map and parent->children map
    all_procs: dict[int, OrphanProcess] = {}
    children_map: dict[int, list[int]] = {}  # ppid -> [child pids]

    for line in result.stdout.strip().split("\n")[1:]:
        parts = line.split(None, 4)
        if len(parts) < 5:
            continue
        try:
            pid = int(parts[0])
            ppid = int(parts[1])
            etime = parts[2]
            rss_kb = int(parts[3])
            command = parts[4]
        except (ValueError, IndexError):
            continue

        all_procs[pid] = OrphanProcess(
            pid=pid,
            etime=etime,
            rss_mb=rss_kb / 1024,
            command=command,
        )

        if ppid not in children_map:
            children_map[ppid] = []
        children_map[ppid].append(pid)

    def build_tree(pid: int) -> OrphanTree:
        """Recursively build process tree from a root PID."""
        proc = all_procs[pid]
        child_pids = children_map.get(pid, [])
        descendants = [build_tree(cpid) for cpid in child_pids if cpid in all_procs]
        return OrphanTree(root=proc, descendants=descendants)

    def is_orphan_candidate(pid: int) -> bool:
        """Check if a PPID=1 process is an orphan candidate."""
        if pid not in all_procs:
            return False
        command = all_procs[pid].command

        # Skip legitimate system processes
        if any(pat in command for pat in legitimate_patterns):
            return False

        # Check if it matches orphan patterns
        if any(pat in command.lower() for pat in orphan_patterns):
            return True

        # Also check if it's a user process (starts with /Users/)
        if command.startswith("/Users/") and ".app/" not in command:
            return True

        return False

    # Find root orphans (PPID=1 and matches patterns)
    root_orphan_pids = [
        pid for pid in children_map.get(1, [])
        if is_orphan_candidate(pid)
    ]

    # Build trees for each root orphan
    orphan_trees = [build_tree(pid) for pid in root_orphan_pids]

    # Sort by elapsed time (longer running first)
    orphan_trees.sort(key=lambda t: parse_etime(t.root.etime), reverse=True)

    return orphan_trees


def get_process_ancestry(pid: int, all_procs: dict[int, ProcessInfo]) -> list[str]:
    """Trace process ancestry from pid to init (PID 1)."""
    ancestry = []
    current_pid = pid
    visited = set()

    while current_pid > 0 and current_pid not in visited:
        visited.add(current_pid)
        if current_pid in all_procs:
            proc = all_procs[current_pid]
            # Truncate long commands for readability
            cmd = proc.command
            if len(cmd) > 80:
                cmd = cmd[:77] + "..."
            ancestry.append(f"[{proc.pid}] {cmd}")
            current_pid = proc.ppid
        else:
            # Process might have exited, try to get info directly
            try:
                result = subprocess.run(
                    ["ps", "-o", "ppid=,command=", "-p", str(current_pid)],
                    capture_output=True,
                    text=True,
                )
                if result.stdout.strip():
                    parts = result.stdout.strip().split(None, 1)
                    ppid = int(parts[0])
                    cmd = parts[1] if len(parts) > 1 else "?"
                    if len(cmd) > 80:
                        cmd = cmd[:77] + "..."
                    ancestry.append(f"[{current_pid}] {cmd}")
                    current_pid = ppid
                else:
                    break
            except (subprocess.SubprocessError, ValueError):
                break

    return ancestry


def get_system_stats() -> dict:
    """Get overall system CPU and memory stats."""
    # Memory stats via vm_stat
    vm_result = subprocess.run(["vm_stat"], capture_output=True, text=True)
    page_size = 16384  # Default, will try to get actual

    # Try to get page size
    try:
        ps_result = subprocess.run(["pagesize"], capture_output=True, text=True)
        page_size = int(ps_result.stdout.strip())
    except (subprocess.SubprocessError, ValueError):
        pass

    stats = {}
    for line in vm_result.stdout.split("\n"):
        if ":" in line:
            key, val = line.split(":", 1)
            try:
                stats[key.strip()] = int(val.strip().rstrip("."))
            except ValueError:
                pass

    # Calculate memory usage
    pages_free = stats.get("Pages free", 0)
    pages_active = stats.get("Pages active", 0)
    pages_inactive = stats.get("Pages inactive", 0)
    pages_speculative = stats.get("Pages speculative", 0)
    pages_wired = stats.get("Pages wired down", 0)
    pages_compressed = stats.get("Pages occupied by compressor", 0)
    pages_purgeable = stats.get("Pages purgeable", 0)
    pageins = stats.get("Pageins", 0)
    pageouts = stats.get("Pageouts", 0)
    swapins = stats.get("Swapins", 0)
    swapouts = stats.get("Swapouts", 0)

    total_pages = (
        pages_free
        + pages_active
        + pages_inactive
        + pages_speculative
        + pages_wired
        + pages_compressed
    )
    used_pages = pages_active + pages_wired + pages_compressed

    mem_total_gb = (total_pages * page_size) / (1024**3)
    mem_used_gb = (used_pages * page_size) / (1024**3)
    mem_percent = (used_pages / total_pages * 100) if total_pages > 0 else 0
    mem_compressed_gb = (pages_compressed * page_size) / (1024**3)
    mem_cached_gb = (pages_inactive * page_size) / (1024**3)

    # Swap usage via sysctl
    swap_total_gb = swap_used_gb = swap_percent = 0.0
    try:
        swap_result = subprocess.run(
            ["sysctl", "-n", "vm.swapusage"],
            capture_output=True,
            text=True,
        )
        # Output: "total = 2048.00M  used = 1024.00M  free = 1024.00M  (encrypted)"
        for part in swap_result.stdout.split():
            if part.endswith("M"):
                val = float(part[:-1])
            elif part.endswith("G"):
                val = float(part[:-1]) * 1024
            else:
                continue
            # Assign based on preceding keyword
            if "total" in swap_result.stdout.split()[swap_result.stdout.split().index(part) - 2]:
                swap_total_gb = val / 1024
            elif "used" in swap_result.stdout.split()[swap_result.stdout.split().index(part) - 2]:
                swap_used_gb = val / 1024
        if swap_total_gb > 0:
            swap_percent = (swap_used_gb / swap_total_gb) * 100
    except (subprocess.SubprocessError, ValueError, IndexError):
        # Fallback: parse more carefully
        try:
            swap_result = subprocess.run(
                ["sysctl", "-n", "vm.swapusage"],
                capture_output=True,
                text=True,
            )
            parts = swap_result.stdout.replace("=", " ").split()
            for i, p in enumerate(parts):
                if p == "total" and i + 1 < len(parts):
                    val = parts[i + 1]
                    swap_total_gb = float(val.rstrip("MG")) / (1 if val.endswith("G") else 1024)
                elif p == "used" and i + 1 < len(parts):
                    val = parts[i + 1]
                    swap_used_gb = float(val.rstrip("MG")) / (1 if val.endswith("G") else 1024)
            if swap_total_gb > 0:
                swap_percent = (swap_used_gb / swap_total_gb) * 100
        except Exception:
            pass

    # Memory pressure
    mem_pressure = "unknown"
    try:
        pressure_result = subprocess.run(
            ["memory_pressure"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        # Look for "System-wide memory free percentage: XX%"
        for line in pressure_result.stdout.split("\n"):
            if "free percentage" in line.lower():
                mem_pressure = line.strip()
                break
            elif "pressure level" in line.lower():
                mem_pressure = line.strip()
                break
    except (subprocess.SubprocessError, subprocess.TimeoutExpired):
        pass

    # CPU usage via top (single sample)
    top_result = subprocess.run(
        ["top", "-l", "1", "-n", "0", "-s", "0"],
        capture_output=True,
        text=True,
    )
    cpu_user = cpu_sys = cpu_idle = 0.0
    for line in top_result.stdout.split("\n"):
        if line.startswith("CPU usage:"):
            # CPU usage: 5.26% user, 10.52% sys, 84.21% idle
            parts = line.split(",")
            for part in parts:
                if "user" in part:
                    cpu_user = float(part.split("%")[0].split()[-1])
                elif "sys" in part:
                    cpu_sys = float(part.split("%")[0].split()[-1])
                elif "idle" in part:
                    cpu_idle = float(part.split("%")[0].split()[-1])
            break

    return {
        "cpu_user": cpu_user,
        "cpu_sys": cpu_sys,
        "cpu_idle": cpu_idle,
        "cpu_used": cpu_user + cpu_sys,
        "mem_total_gb": mem_total_gb,
        "mem_used_gb": mem_used_gb,
        "mem_percent": mem_percent,
        "mem_compressed_gb": mem_compressed_gb,
        "mem_cached_gb": mem_cached_gb,
        "swap_total_gb": swap_total_gb,
        "swap_used_gb": swap_used_gb,
        "swap_percent": swap_percent,
        "mem_pressure": mem_pressure,
        "pageins": pageins,
        "pageouts": pageouts,
        "swapins": swapins,
        "swapouts": swapouts,
    }


def main():
    sort_by = "cpu"
    limit = 10

    # Parse args
    args = sys.argv[1:]
    if "--mem" in args:
        sort_by = "mem"
    if "--limit" in args:
        try:
            idx = args.index("--limit")
            limit = int(args[idx + 1])
        except (IndexError, ValueError):
            pass

    # Get system stats
    print("=" * 70)
    print("SYSTEM OVERVIEW")
    print("=" * 70)

    stats = get_system_stats()
    print(f"CPU Usage: {stats['cpu_used']:.1f}% (user: {stats['cpu_user']:.1f}%, sys: {stats['cpu_sys']:.1f}%, idle: {stats['cpu_idle']:.1f}%)")
    print(f"Memory:    {stats['mem_used_gb']:.1f} GB / {stats['mem_total_gb']:.1f} GB ({stats['mem_percent']:.1f}% used)")
    print(f"           Compressed: {stats['mem_compressed_gb']:.1f} GB, Cached: {stats['mem_cached_gb']:.1f} GB")
    if stats['swap_total_gb'] > 0:
        print(f"Swap:      {stats['swap_used_gb']:.2f} GB / {stats['swap_total_gb']:.2f} GB ({stats['swap_percent']:.1f}% used)")
    else:
        print("Swap:      Not configured or unavailable")
    if stats['mem_pressure'] != "unknown":
        print(f"Pressure:  {stats['mem_pressure']}")
    # Show paging activity as indicator of memory stress
    if stats['pageouts'] > 0 or stats['swapouts'] > 0:
        print(f"⚠️  Paging:  pageins={stats['pageins']}, pageouts={stats['pageouts']}, swapins={stats['swapins']}, swapouts={stats['swapouts']}")
        if stats['pageouts'] > 10000 or stats['swapouts'] > 1000:
            print("           ↑ High pageouts/swapouts indicate memory pressure!")

    # Get processes with memory details for swap analysis
    all_procs_with_mem = get_processes_with_memory()

    # Show swap-heavy processes if swap is being used
    if stats['swap_used_gb'] > 0.1:  # More than 100MB swap used
        print()
        print("=" * 70)
        print("ESTIMATED SWAP USAGE BY PROCESS (VSIZE - RSS approximation)")
        print("=" * 70)
        print("Note: This is an estimate. VSIZE includes shared libs & mapped files.")
        print()

        swap_procs = get_swap_heavy_processes(all_procs_with_mem, limit=10)
        if swap_procs:
            for i, (proc, est_swap) in enumerate(swap_procs, 1):
                cmd_display = proc.command
                if len(cmd_display) > 50:
                    cmd_display = cmd_display[:47] + "..."
                est_swap_gb = est_swap / 1024
                print(f"#{i} [{proc.pid}] ~{est_swap_gb:.1f} GB swapped (VSIZE: {proc.vsize_mb/1024:.1f}GB, RSS: {proc.rss_mb/1024:.1f}GB)")
                print(f"   {cmd_display}")
        else:
            print("No processes with significant estimated swap usage found.")

    # Detect orphan processes
    orphan_trees = get_orphan_processes()
    if orphan_trees:
        # Count total processes including descendants
        all_pids: list[int] = []
        total_mem = 0.0
        for tree in orphan_trees:
            all_pids.extend(tree.all_pids())
            total_mem += tree.total_memory()

        root_count = len(orphan_trees)
        total_count = len(all_pids)

        print()
        print("=" * 70)
        if total_count > root_count:
            print(f"ORPHAN PROCESSES ({root_count} roots, {total_count} total with children)")
        else:
            print(f"ORPHAN PROCESSES ({total_count} found)")
        print("=" * 70)
        print("These are likely abandoned dev processes (PPID=1, script/node/bun).")
        print("Process trees show root orphans and their descendants.")
        print()

        def print_tree(tree: OrphanTree, depth: int = 0, is_last: bool = True, prefix: str = ""):
            """Recursively print process tree."""
            cmd_display = tree.root.command
            if len(cmd_display) > 45:
                cmd_display = cmd_display[:42] + "..."

            if depth == 0:
                # Root level - no tree prefix
                print(f"  PID {tree.root.pid:<6} | {tree.root.etime:>12} | {tree.root.rss_mb:>6.1f} MB | {cmd_display}")
            else:
                # Child level - show tree structure
                connector = "└─" if is_last else "├─"
                print(f"  {prefix}{connector} PID {tree.root.pid:<6} | {tree.root.rss_mb:>6.1f} MB | {cmd_display}")

            # Build prefix for children
            if depth == 0:
                child_prefix = ""
            else:
                child_prefix = prefix + ("   " if is_last else "│  ")

            for i, child in enumerate(tree.descendants):
                print_tree(child, depth + 1, i == len(tree.descendants) - 1, child_prefix)

        for tree in orphan_trees:
            print_tree(tree)
            print()  # Line between trees

        print()
        print(f"  Total orphan memory: {total_mem:.1f} MB")
        print(f"  To kill all ({total_count} processes): kill {' '.join(str(pid) for pid in all_pids)}")

    # Get all processes for ancestry lookup
    all_result = subprocess.run(
        ["ps", "-eo", "pid,ppid,pcpu,pmem,command"],
        capture_output=True,
        text=True,
    )
    all_procs: dict[int, ProcessInfo] = {}
    for line in all_result.stdout.strip().split("\n")[1:]:
        parts = line.split(None, 4)
        if len(parts) >= 5:
            try:
                pid = int(parts[0])
                all_procs[pid] = ProcessInfo(
                    pid=pid,
                    ppid=int(parts[1]),
                    cpu=float(parts[2]),
                    mem=float(parts[3]),
                    command=parts[4],
                )
            except (ValueError, IndexError):
                continue

    # Get top processes
    top_procs = get_top_processes(sort_by=sort_by, limit=limit)

    print()
    print("=" * 70)
    print(f"TOP {limit} PROCESSES (sorted by {sort_by.upper()})")
    print("=" * 70)

    for i, proc in enumerate(top_procs, 1):
        cmd_display = proc.command
        if len(cmd_display) > 60:
            cmd_display = cmd_display[:57] + "..."

        print(f"\n#{i} [{proc.pid}] CPU: {proc.cpu:.1f}%  MEM: {proc.mem:.1f}%")
        print(f"   Command: {cmd_display}")
        print("   Process Tree (child → parent):")

        ancestry = get_process_ancestry(proc.pid, all_procs)
        for j, ancestor in enumerate(ancestry):
            indent = "   " + "  " * j + ("└─ " if j > 0 else "── ")
            print(f"{indent}{ancestor}")


if __name__ == "__main__":
    main()
