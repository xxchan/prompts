#!/usr/bin/env python3
"""
Disk space analysis and cleanup tool for macOS.
Scans for cleanable items and provides interactive cleanup.
"""

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class MountPoint:
    filesystem: str
    size: str
    used: str
    avail: str
    use_percent: int
    mount: str


@dataclass
class CleanableItem:
    name: str
    path: Path
    size_bytes: int
    risk: str  # safe / moderate / caution
    description: str
    clean_func: str = "rm_rf"  # rm_rf / rm_old_files / custom
    selected: bool = False

    @property
    def size_human(self) -> str:
        return format_size(self.size_bytes)


@dataclass
class LargeItem:
    path: Path
    size_bytes: int
    item_type: str  # file / directory

    @property
    def size_human(self) -> str:
        return format_size(self.size_bytes)


# Cleanable targets configuration
CLEANABLE_TARGETS: list[dict] = [
    # SAFE - caches that auto-regenerate
    {
        "name": "Homebrew Cache",
        "path": "~/Library/Caches/Homebrew",
        "risk": "safe",
        "description": "Downloaded packages, reinstalls automatically",
    },
    {
        "name": "npm Cache",
        "path": "~/.npm/_cacache",
        "risk": "safe",
        "description": "npm package cache, rebuilds on install",
    },
    {
        "name": "Yarn Cache",
        "path": "~/Library/Caches/Yarn",
        "risk": "safe",
        "description": "Yarn package cache",
    },
    {
        "name": "pnpm Store",
        "path": "~/Library/pnpm/store",
        "risk": "safe",
        "description": "pnpm content-addressable store",
    },
    {
        "name": "pip Cache",
        "path": "~/Library/Caches/pip",
        "risk": "safe",
        "description": "Python package cache",
    },
    {
        "name": "uv Cache",
        "path": "~/.cache/uv",
        "risk": "safe",
        "description": "uv package manager cache",
    },
    {
        "name": "Go Module Cache",
        "path": "~/go/pkg/mod/cache",
        "risk": "safe",
        "description": "Go module download cache",
    },
    {
        "name": "Cargo Registry Cache",
        "path": "~/.cargo/registry/cache",
        "risk": "safe",
        "description": "Rust crate download cache",
    },
    {
        "name": "Composer Cache",
        "path": "~/.composer/cache",
        "risk": "safe",
        "description": "PHP Composer package cache",
    },
    {
        "name": "CocoaPods Cache",
        "path": "~/Library/Caches/CocoaPods",
        "risk": "safe",
        "description": "iOS dependency cache",
    },
    # MODERATE - requires rebuild/redownload
    {
        "name": "Xcode DerivedData",
        "path": "~/Library/Developer/Xcode/DerivedData",
        "risk": "moderate",
        "description": "Build artifacts, requires rebuild",
    },
    {
        "name": "Gradle Cache",
        "path": "~/.gradle/caches",
        "risk": "moderate",
        "description": "Gradle build cache, requires rebuild",
    },
    {
        "name": "Maven Repository",
        "path": "~/.m2/repository",
        "risk": "moderate",
        "description": "Maven artifacts, redownloads on build",
    },
    {
        "name": "Xcode Archives",
        "path": "~/Library/Developer/Xcode/Archives",
        "risk": "moderate",
        "description": "Old app archives for App Store submission",
    },
    {
        "name": "iOS DeviceSupport",
        "path": "~/Library/Developer/Xcode/iOS DeviceSupport",
        "risk": "moderate",
        "description": "Debug symbols for iOS devices",
    },
    {
        "name": "Android SDK Cache",
        "path": "~/.android/cache",
        "risk": "moderate",
        "description": "Android SDK download cache",
    },
    # CAUTION - may contain user data
    {
        "name": "Trash",
        "path": "~/.Trash",
        "risk": "caution",
        "description": "Deleted files, PERMANENT deletion",
        "clean_func": "empty_trash",
    },
    {
        "name": "Log Files",
        "path": "~/Library/Logs",
        "risk": "caution",
        "description": "Application logs, may be useful for debugging",
    },
]


def format_size(size_bytes: int) -> str:
    """Format bytes to human readable string."""
    if size_bytes < 0:
        return "0 B"
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"


def get_dir_size(path: Path) -> int:
    """Get total size of directory in bytes."""
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size

    total = 0
    try:
        for entry in path.rglob("*"):
            try:
                if entry.is_file() and not entry.is_symlink():
                    total += entry.stat().st_size
            except (PermissionError, OSError):
                continue
    except (PermissionError, OSError):
        pass
    return total


def get_disk_overview() -> list[MountPoint]:
    """Get disk usage overview using df."""
    result = subprocess.run(
        ["df", "-H"],  # -H for human readable (base 10)
        capture_output=True,
        text=True,
    )

    mounts = []
    for line in result.stdout.strip().split("\n")[1:]:
        parts = line.split()
        if len(parts) >= 6:
            # Skip small/system filesystems
            filesystem = parts[0]
            mount = parts[-1]

            # Only show main disk partitions
            if not mount.startswith("/Volumes") and mount != "/":
                if "devfs" in filesystem or "map " in filesystem:
                    continue

            try:
                use_pct = int(parts[4].rstrip("%"))
            except ValueError:
                use_pct = 0

            mounts.append(
                MountPoint(
                    filesystem=filesystem,
                    size=parts[1],
                    used=parts[2],
                    avail=parts[3],
                    use_percent=use_pct,
                    mount=mount,
                )
            )

    # Sort by mount point, / first
    mounts.sort(key=lambda m: (0 if m.mount == "/" else 1, m.mount))
    return mounts


def scan_cleanable_items() -> list[CleanableItem]:
    """Scan for cleanable items and calculate their sizes."""
    items = []

    for target in CLEANABLE_TARGETS:
        path = Path(target["path"]).expanduser()
        if not path.exists():
            continue

        size = get_dir_size(path)
        if size < 1024 * 1024:  # Skip if < 1MB
            continue

        items.append(
            CleanableItem(
                name=target["name"],
                path=path,
                size_bytes=size,
                risk=target["risk"],
                description=target["description"],
                clean_func=target.get("clean_func", "rm_rf"),
            )
        )

    # Sort by size descending
    items.sort(key=lambda x: x.size_bytes, reverse=True)
    return items


def scan_large_items(
    root: Path, min_size_mb: int = 100, max_depth: int = 3
) -> list[LargeItem]:
    """Scan for large files and directories."""
    min_size = min_size_mb * 1024 * 1024
    large_items = []

    def scan_dir(path: Path, depth: int):
        if depth > max_depth:
            return

        try:
            entries = list(path.iterdir())
        except (PermissionError, OSError):
            return

        for entry in entries:
            try:
                if entry.is_symlink():
                    continue

                if entry.is_file():
                    size = entry.stat().st_size
                    if size >= min_size:
                        large_items.append(
                            LargeItem(path=entry, size_bytes=size, item_type="file")
                        )
                elif entry.is_dir():
                    # Skip system directories
                    if entry.name.startswith(".") and entry.name in [
                        ".Trash",
                        ".Spotlight-V100",
                        ".fseventsd",
                    ]:
                        continue

                    dir_size = get_dir_size(entry)
                    if dir_size >= min_size:
                        large_items.append(
                            LargeItem(
                                path=entry, size_bytes=dir_size, item_type="directory"
                            )
                        )
                    # Recurse into directory
                    scan_dir(entry, depth + 1)
            except (PermissionError, OSError):
                continue

    scan_dir(root, 0)

    # Sort by size descending and dedupe (parent dirs contain children)
    large_items.sort(key=lambda x: x.size_bytes, reverse=True)
    return large_items[:20]  # Top 20


def clean_item(item: CleanableItem, dry_run: bool = False) -> bool:
    """Clean a single item. Returns True if successful."""
    if not item.path.exists():
        return True

    if dry_run:
        print(f"  [DRY-RUN] Would delete: {item.path}")
        return True

    try:
        if item.clean_func == "empty_trash":
            # Use Finder to empty trash safely
            subprocess.run(
                [
                    "osascript",
                    "-e",
                    'tell application "Finder" to empty trash',
                ],
                capture_output=True,
                check=True,
            )
        else:
            # rm -rf
            if item.path.is_dir():
                shutil.rmtree(item.path)
            else:
                item.path.unlink()
        return True
    except (PermissionError, OSError, subprocess.CalledProcessError) as e:
        print(f"  Error cleaning {item.name}: {e}")
        return False


def print_overview(mounts: list[MountPoint]):
    """Print disk overview."""
    print("=" * 70)
    print("DISK OVERVIEW")
    print("=" * 70)
    print(f"{'Filesystem':<20} {'Size':>8} {'Used':>8} {'Avail':>8} {'Use%':>6}  Mount")
    print("-" * 70)

    for m in mounts:
        # Warning indicators
        if m.use_percent >= 95:
            indicator = " 🔴 CRITICAL"
        elif m.use_percent >= 90:
            indicator = " 🟠 HIGH"
        elif m.use_percent >= 80:
            indicator = " 🟡"
        else:
            indicator = ""

        fs_display = m.filesystem[:20] if len(m.filesystem) > 20 else m.filesystem
        print(
            f"{fs_display:<20} {m.size:>8} {m.used:>8} {m.avail:>8} {m.use_percent:>5}%  {m.mount}{indicator}"
        )


def print_cleanable_items(items: list[CleanableItem]):
    """Print cleanable items grouped by risk level."""
    if not items:
        print("\nNo significant cleanable items found.")
        return

    total_size = sum(i.size_bytes for i in items)
    print()
    print("=" * 70)
    print(f"CLEANABLE ITEMS ({len(items)} items, {format_size(total_size)} total)")
    print("=" * 70)

    # Group by risk
    risk_order = ["safe", "moderate", "caution"]
    risk_labels = {
        "safe": "[SAFE] Auto-regenerates, safe to delete:",
        "moderate": "[MODERATE] Requires rebuild/redownload:",
        "caution": "[CAUTION] Review before deleting:",
    }

    idx = 1
    for risk in risk_order:
        risk_items = [i for i in items if i.risk == risk]
        if not risk_items:
            continue

        print(f"\n{risk_labels[risk]}")
        for item in risk_items:
            checkbox = "[x]" if item.selected else "[ ]"
            print(f"  {idx:2}. {checkbox} {item.name:<24} {item.size_human:>10}")
            idx += 1


def interactive_cleanup(items: list[CleanableItem]):
    """Interactive cleanup mode."""
    if not items:
        return

    # Pre-select safe items
    for item in items:
        if item.risk == "safe":
            item.selected = True

    while True:
        # Clear screen and reprint
        print("\033[2J\033[H", end="")  # Clear screen

        mounts = get_disk_overview()
        print_overview(mounts)
        print_cleanable_items(items)

        selected = [i for i in items if i.selected]
        selected_size = sum(i.size_bytes for i in selected)

        print()
        print("-" * 70)
        print(f"Selected: {len(selected)} items, {format_size(selected_size)}")
        print()
        print("Commands: [1-9] toggle | [a]ll-safe | [m]oderate | [c]aution | [n]one")
        print("          [Enter] execute cleanup | [d]ry-run | [q]uit")
        print()

        try:
            choice = input("Your choice: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nAborted.")
            return

        if choice == "q":
            print("Aborted.")
            return

        elif choice == "a":
            # Select all safe
            for item in items:
                if item.risk == "safe":
                    item.selected = True

        elif choice == "m":
            # Toggle all moderate
            moderate_items = [i for i in items if i.risk == "moderate"]
            all_selected = all(i.selected for i in moderate_items)
            for item in moderate_items:
                item.selected = not all_selected

        elif choice == "c":
            # Toggle all caution
            caution_items = [i for i in items if i.risk == "caution"]
            all_selected = all(i.selected for i in caution_items)
            for item in caution_items:
                item.selected = not all_selected

        elif choice == "n":
            # Deselect all
            for item in items:
                item.selected = False

        elif choice == "d":
            # Dry run
            selected = [i for i in items if i.selected]
            if not selected:
                print("No items selected.")
                input("Press Enter to continue...")
                continue

            print("\n[DRY-RUN] Would execute:")
            for item in selected:
                print(f"  rm -rf {item.path}")
            print()
            input("Press Enter to continue...")

        elif choice == "" or choice == "y":
            # Execute cleanup
            selected = [i for i in items if i.selected]
            if not selected:
                print("No items selected.")
                input("Press Enter to continue...")
                continue

            print(f"\nAbout to delete {len(selected)} items ({format_size(selected_size)}):")
            for item in selected:
                risk_icon = {"safe": "✓", "moderate": "⚠", "caution": "⚠️"}
                print(f"  {risk_icon.get(item.risk, '?')} {item.name}: {item.path}")

            print()
            confirm = input("Type 'yes' to confirm: ").strip().lower()
            if confirm != "yes":
                print("Aborted.")
                input("Press Enter to continue...")
                continue

            print("\nCleaning...")
            freed = 0
            for item in selected:
                print(f"  Deleting {item.name}...", end=" ", flush=True)
                if clean_item(item):
                    print(f"✓ freed {item.size_human}")
                    freed += item.size_bytes
                    item.selected = False
                else:
                    print("✗ failed")

            print(f"\nTotal freed: {format_size(freed)}")
            input("Press Enter to continue...")

            # Rescan items
            items[:] = scan_cleanable_items()
            if not items:
                print("\nAll clean! No more items to clean.")
                return

        elif choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(items):
                items[idx].selected = not items[idx].selected


def print_large_items(items: list[LargeItem], root: Path):
    """Print large files and directories."""
    print()
    print("=" * 70)
    print(f"LARGE ITEMS in {root} (>{100}MB)")
    print("=" * 70)

    if not items:
        print("No large items found.")
        return

    for i, item in enumerate(items[:15], 1):
        icon = "📁" if item.item_type == "directory" else "📄"
        rel_path = item.path
        try:
            rel_path = item.path.relative_to(root)
        except ValueError:
            pass
        print(f"  {i:2}. {icon} {item.size_human:>10}  {rel_path}")


def main():
    args = sys.argv[1:]

    # Parse arguments
    show_overview = "--overview" in args or not args
    show_clean = "--clean" in args or "--scan" in args or not args
    show_large = "--large" in args
    dry_run = "--dry-run" in args
    interactive = not ("--scan" in args or dry_run)

    # Get path for large scan
    large_path = Path.home()
    if "--large" in args:
        idx = args.index("--large")
        if idx + 1 < len(args) and not args[idx + 1].startswith("-"):
            large_path = Path(args[idx + 1]).expanduser()

    # Show overview
    if show_overview:
        mounts = get_disk_overview()
        print_overview(mounts)

    # Scan and show large items
    if show_large:
        print("\nScanning for large items... (this may take a moment)")
        large_items = scan_large_items(large_path)
        print_large_items(large_items, large_path)

    # Scan cleanable items
    if show_clean:
        print("\nScanning for cleanable items...")
        items = scan_cleanable_items()

        if interactive and items:
            interactive_cleanup(items)
        else:
            print_cleanable_items(items)

            if dry_run and items:
                print("\n[DRY-RUN] Cleanup commands:")
                for item in items:
                    print(f"  rm -rf '{item.path}'")


if __name__ == "__main__":
    main()
