#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# ///

from __future__ import annotations

import argparse
import os
import shutil
import sys
import time
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# This script manages two flows:
# 1) "dotfiles" linking: mirror repo files into a destination (usually $HOME).
# 2) Codex sync: import skills into the repo and link repo-managed skills back into ~/.codex.

# Files/directories ignored by dotfiles linking to avoid unsafe or noisy links.
DEFAULT_IGNORED_NAMES = {
    ".git",
    ".DS_Store",
    "README",
    "README.md",
    "LICENSE",
    "LICENSE.md",
    "node_modules",
    "target",
    "dist",
    "scripts",
    ".vscode",
    "promptkit",
    "skills",
}

DEFAULT_IGNORE_PREFIXES = ("README", "LICENSE")

# Codex keeps internal/system skills under .system; do not move/link them.
SKILL_IGNORE_NAMES = {".system", ".DS_Store"}
SKILL_CONTENT_IGNORE_NAMES = {".DS_Store"}


@dataclass(frozen=True)
class LinkOptions:
    mode: str
    apply: bool


@dataclass(frozen=True)
class DotfilesOptions:
    source_dir: Path
    dest_dir: Path
    scope: str
    link: bool


@dataclass(frozen=True)
class CodexOptions:
    enabled: bool
    import_skills: bool
    codex_dir: Path
    agents_file: Path
    repo_skills_dir: Path


@dataclass(frozen=True)
class ClaudeOptions:
    enabled: bool
    import_skills: bool
    link_root: bool
    claude_dir: Path
    repo_skills_dir: Path


def main() -> int:
    """Entrypoint: parse args, then run dotfile linking and agent skill sync."""
    args = parse_args()

    # --codex-sync is a shorthand that enables both import and linking.
    if args.codex_sync:
        codex_enabled = True
        import_skills = True
    else:
        codex_enabled = args.codex
        import_skills = args.codex_import

    # --claude-sync is a shorthand that enables both import and linking.
    if args.claude_sync:
        claude_enabled = True
        claude_import = True
    else:
        claude_enabled = args.claude
        claude_import = args.claude_import
    claude_link_root = args.claude_link_root

    if args.only_codex and not (codex_enabled or import_skills):
        raise ValueError("--only-codex requires --codex, --codex-import, or --codex-sync")
    if args.only_claude and not (claude_enabled or claude_import):
        raise ValueError("--only-claude requires --claude, --claude-import, or --claude-sync")

    link_options = LinkOptions(mode=args.mode, apply=args.apply)

    dotfiles = DotfilesOptions(
        source_dir=Path(args.source_dir).expanduser().resolve(),
        dest_dir=Path(args.dest).expanduser().resolve(),
        scope=args.scope,
        link=not (args.only_codex or args.only_claude),
    )

    codex = CodexOptions(
        enabled=codex_enabled,
        import_skills=import_skills,
        codex_dir=Path(args.codex_dir).expanduser().resolve(),
        agents_file=Path(args.agents_file).expanduser().resolve(),
        repo_skills_dir=Path(args.repo_skills_dir).expanduser().resolve(),
    )

    claude = ClaudeOptions(
        enabled=claude_enabled,
        import_skills=claude_import,
        link_root=claude_link_root,
        claude_dir=Path(args.claude_dir).expanduser().resolve(),
        repo_skills_dir=Path(args.repo_skills_dir).expanduser().resolve(),
    )

    # Dotfiles linking mirrors repo files to the destination directory.
    if dotfiles.link:
        link_dotfiles(dotfiles, link_options)

    # Codex sync imports existing skills into the repo and links them back.
    if codex.enabled or codex.import_skills:
        sync_codex(codex, link_options)

    # Claude sync imports existing skills into the repo and links them back.
    if claude.enabled or claude.import_skills:
        sync_claude(claude, link_options)

    if not args.apply:
        print("\nDry-run only. Re-run with --apply to make changes.")

    return 0


def parse_args() -> argparse.Namespace:
    """Define CLI flags for dotfile linking and Codex/Claude skill management."""
    default_dest = os.environ.get("DEST_DIR", str(Path.home()))

    # Keep usage readable: this script is frequently run directly by humans.
    parser = argparse.ArgumentParser(
        description="Symlink repo files into a destination and manage Codex assets.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "source_dir",
        nargs="?",
        default=str(Path.cwd()),
        help="Source directory for dotfile linking (default: cwd).",
    )
    parser.add_argument(
        "--mode",
        choices=["skip", "backup", "replace", "fail"],
        default="backup",
        help="Conflict handling: skip, backup, replace, fail.",
    )
    parser.add_argument("--apply", action="store_true", help="Apply changes.")
    parser.add_argument(
        "--dest",
        default=default_dest,
        help="Destination directory for dotfile linking (default: $HOME).",
    )
    parser.add_argument(
        "--top-level",
        dest="scope",
        action="store_const",
        const="top",
        default="files",
        help="Link only top-level items (no recursion).",
    )

    parser.add_argument(
        "--only-codex",
        action="store_true",
        help="Skip dotfile linking and only manage Codex assets.",
    )
    parser.add_argument(
        "--only-claude",
        action="store_true",
        help="Skip dotfile linking and only manage Claude assets.",
    )
    parser.add_argument(
        "--codex",
        action="store_true",
        help="Link Codex AGENTS.md and repo-managed skills.",
    )
    parser.add_argument(
        "--codex-import",
        action="store_true",
        help="Move existing Codex skills into the repo.",
    )
    parser.add_argument(
        "--codex-sync",
        action="store_true",
        help="Shortcut for --codex --codex-import.",
    )
    parser.add_argument(
        "--claude",
        action="store_true",
        help="Link Claude skills from the repo into ~/.claude/skills.",
    )
    parser.add_argument(
        "--claude-import",
        action="store_true",
        help="Move existing Claude skills into the repo.",
    )
    parser.add_argument(
        "--claude-sync",
        action="store_true",
        help="Shortcut for --claude --claude-import.",
    )
    parser.add_argument(
        "--claude-link-root",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Symlink ~/.claude/skills to the repo skills directory (default: true).",
    )
    parser.add_argument(
        "--codex-dir",
        default=str(Path.home() / ".codex"),
        help="Codex directory to manage (default: ~/.codex).",
    )
    parser.add_argument(
        "--agents-file",
        default=str(REPO_ROOT / ".codex" / "AGENTS.md"),
        help="Source AGENTS.md to link into Codex.",
    )
    parser.add_argument(
        "--repo-skills-dir",
        default=str(REPO_ROOT / "skills"),
        help="Repo skills directory to manage.",
    )
    parser.add_argument(
        "--claude-dir",
        default=str(Path.home() / ".claude"),
        help="Claude directory to manage (default: ~/.claude).",
    )

    return parser.parse_args()


def link_dotfiles(options: DotfilesOptions, link_options: LinkOptions) -> None:
    """Link repo files into a destination directory, honoring ignore rules."""
    if not options.source_dir.is_dir():
        raise ValueError(f"Source directory not found: {options.source_dir}")

    log("ROOT", f"{options.source_dir} -> {options.dest_dir}")

    if options.scope == "top":
        link_top_level(options, link_options)
    else:
        link_tree(options, link_options)


def link_top_level(options: DotfilesOptions, link_options: LinkOptions) -> None:
    """Link only top-level entries from the source directory into the destination."""
    for entry in sorted(options.source_dir.iterdir(), key=lambda path: path.name):
        name = entry.name
        if should_ignore(name):
            log("IGNORE", name)
            continue

        dest_path = options.dest_dir / name
        link_path(entry, dest_path, link_options)


def link_tree(options: DotfilesOptions, link_options: LinkOptions) -> None:
    """Recursively link files, while skipping ignored entries and destination loops."""
    dest_root = options.dest_dir.resolve()
    walk_tree(options.source_dir, options.dest_dir, dest_root, Path(""), link_options)


def walk_tree(
    current_src: Path,
    dest_root: Path,
    dest_root_resolved: Path,
    rel_prefix: Path,
    link_options: LinkOptions,
) -> None:
    """Traverse source tree and link files into destination while avoiding loops."""
    for entry in sorted(current_src.iterdir(), key=lambda path: path.name):
        name = entry.name
        if should_ignore(name):
            log("IGNORE", str(rel_prefix / name))
            continue

        rel_path = rel_prefix / name
        src_path = entry
        dest_path = dest_root / rel_path

        if src_path.is_dir() and not src_path.is_symlink():
            src_resolved = src_path.resolve()
            if is_within(dest_root_resolved, src_resolved):
                log("IGNORE", f"{rel_path} (dest)")
                continue

            # Ensure the destination directory exists before recursing.
            if ensure_dir(dest_path, link_options):
                walk_tree(src_path, dest_root, dest_root_resolved, rel_path, link_options)
        else:
            link_path(src_path, dest_path, link_options)


def sync_codex(codex: CodexOptions, link_options: LinkOptions) -> None:
    """Import Codex skills into the repo and link repo-managed skills into ~/.codex."""
    codex_dir = codex.codex_dir
    if not codex_dir.is_dir():
        raise ValueError(f"Codex directory not found: {codex_dir}")

    codex_skills_dir = codex_dir / "skills"
    ensure_dir(codex_skills_dir, link_options)
    ensure_dir(codex.repo_skills_dir, link_options)

    # Import first so linking always uses the repo as the source of truth.
    if codex.import_skills:
        import_codex_skills(codex_skills_dir, codex.repo_skills_dir, link_options)

    if codex.enabled:
        link_path(codex.agents_file, codex_dir / "AGENTS.md", link_options)
        link_repo_skills(codex.repo_skills_dir, codex_skills_dir, link_options)


def sync_claude(claude: ClaudeOptions, link_options: LinkOptions) -> None:
    """Import Claude skills into the repo and link repo-managed skills into ~/.claude/skills."""
    claude_dir = claude.claude_dir
    if not claude_dir.is_dir():
        raise ValueError(f"Claude directory not found: {claude_dir}")

    claude_skills_dir = claude_dir / "skills"
    ensure_dir(claude.repo_skills_dir, link_options)

    # Import first so linking always uses the repo as the source of truth.
    if claude.import_skills:
        ensure_dir(claude_skills_dir, link_options)
        import_claude_skills(claude_skills_dir, claude.repo_skills_dir, link_options)

    if claude.enabled:
        if claude.link_root:
            link_path(claude.repo_skills_dir, claude_skills_dir, link_options)
        else:
            ensure_dir(claude_skills_dir, link_options)
            link_claude_skills(claude.repo_skills_dir, claude_skills_dir, link_options)


def import_codex_skills(
    codex_skills_dir: Path,
    repo_skills_dir: Path,
    link_options: LinkOptions,
) -> None:
    """Move Codex skill directories into the repo for centralized management."""
    for entry in sorted(codex_skills_dir.iterdir(), key=lambda path: path.name):
        name = entry.name
        if name in SKILL_IGNORE_NAMES:
            continue

        # If already linked to the repo, leave as-is; otherwise fail fast.
        if entry.is_symlink():
            src_target = entry.resolve(strict=False)
            expected_target = (repo_skills_dir / name).resolve(strict=False)
            if src_target == expected_target:
                log("NOOP", f"{entry} already linked")
                continue
            raise ValueError(f"Skill is a symlink with unexpected target: {entry}")

        # Codex skills are directories containing SKILL.md; enforce that contract.
        if not entry.is_dir():
            raise ValueError(f"Skill entry is not a directory: {entry}")

        dest = repo_skills_dir / name
        if dest.exists():
            if dest.is_dir():
                log("NOOP", f"{dest} already exists")
                continue
            raise ValueError(f"Skill already exists in repo: {dest}")

        # Move the skill directory into the repo to establish the single source of truth.
        log("MOVE", f"{entry} -> {dest}")
        if link_options.apply:
            shutil.move(str(entry), str(dest))


def link_repo_skills(
    repo_skills_dir: Path,
    codex_skills_dir: Path,
    link_options: LinkOptions,
) -> None:
    """Install repo skills into ~/.codex/skills using non-symlink files."""
    for entry in sorted(repo_skills_dir.iterdir(), key=lambda path: path.name):
        name = entry.name
        if name in SKILL_IGNORE_NAMES or name.startswith("."):
            continue
        if not entry.is_dir():
            raise ValueError(f"Repo skill is not a directory: {entry}")

        # Materialize the skill directory so Codex's scanner can see SKILL.md,
        # then sync files inside back to the repo as the source of truth.
        dest_dir = codex_skills_dir / name
        if ensure_dir(dest_dir, link_options):
            sync_skill_contents(entry, dest_dir, link_options)


def import_claude_skills(
    claude_skills_dir: Path,
    repo_skills_dir: Path,
    link_options: LinkOptions,
) -> None:
    """Move Claude-managed skill directories into the repo (single source of truth)."""
    for entry in sorted(claude_skills_dir.iterdir(), key=lambda path: path.name):
        name = entry.name
        if name in SKILL_IGNORE_NAMES:
            continue
        # Skip packaged .skill archives; they are not editable sources.
        if name.endswith(".skill"):
            continue
        # Allow already-linked entries; otherwise fail fast on unexpected symlinks.
        if entry.is_symlink():
            src_target = entry.resolve(strict=False)
            expected_target = (repo_skills_dir / name).resolve(strict=False)
            if src_target == expected_target:
                log("NOOP", f"{entry} already linked")
                continue
            raise ValueError(f"Claude skill is a symlink with unexpected target: {entry}")
        if not entry.is_dir():
            continue

        dest = repo_skills_dir / name
        if dest.exists():
            if dest.is_dir():
                log("NOOP", f"{dest} already exists")
                continue
            raise ValueError(f"Skill already exists in repo: {dest}")

        log("MOVE", f"{entry} -> {dest}")
        if link_options.apply:
            shutil.move(str(entry), str(dest))


def link_claude_skills(
    repo_skills_dir: Path,
    claude_skills_dir: Path,
    link_options: LinkOptions,
) -> None:
    """Link repo skills into ~/.claude/skills using symlinks."""
    for entry in sorted(repo_skills_dir.iterdir(), key=lambda path: path.name):
        name = entry.name
        if name in SKILL_IGNORE_NAMES or name.startswith("."):
            continue
        if not entry.is_dir():
            raise ValueError(f"Repo skill is not a directory: {entry}")

        link_path(entry, claude_skills_dir / name, link_options)


def should_ignore(name: str) -> bool:
    """Return True when a top-level entry should be ignored by dotfile linking."""
    if name in DEFAULT_IGNORED_NAMES:
        return True
    return name.startswith(DEFAULT_IGNORE_PREFIXES)


def ensure_dir(path: Path, link_options: LinkOptions) -> bool:
    """Create directories with conflict handling for existing paths."""
    if path.is_dir() and not path.is_symlink():
        return True

    if path.exists() or path.is_symlink():
        if not handle_existing(path, link_options):
            return False

    log("MKDIR", str(path))
    if link_options.apply:
        path.mkdir(parents=True, exist_ok=True)
    return True


def link_path(src: Path, dest: Path, link_options: LinkOptions) -> None:
    """Symlink src -> dest with conflict handling and idempotent checks."""
    # If already linked to the same target, keep it.
    if dest.is_symlink():
        dest_target = dest.resolve(strict=False)
        src_target = src.resolve(strict=False)
        if dest_target == src_target:
            log("NOOP", f"{dest} -> {src}")
            return

    # Resolve conflicts before creating the link.
    if dest.exists() or dest.is_symlink():
        if not handle_existing(dest, link_options):
            return

    log("LINK", f"{dest} -> {src}")
    if link_options.apply:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.symlink_to(src)


def handle_existing(path: Path, link_options: LinkOptions) -> bool:
    """Apply conflict policy; return True if caller should continue."""
    mode = link_options.mode
    if mode == "skip":
        log("SKIP", str(path))
        return False

    if mode == "fail":
        raise ValueError(f"Path already exists: {path}")

    if mode == "backup":
        backup = backup_path(path)
        log("BACKUP", f"{path} -> {backup}")
        if link_options.apply:
            shutil.move(str(path), str(backup))
        return True

    if mode == "replace":
        log("REMOVE", str(path))
        if link_options.apply:
            remove_path(path)
        return True

    raise ValueError(f"Unknown mode: {mode}")


def backup_path(path: Path) -> Path:
    """Return a timestamped backup path in the same directory."""
    suffix = time.strftime("%Y%m%d-%H%M%S")
    return path.with_name(f"{path.name}.bak-{suffix}")


def remove_path(path: Path) -> None:
    """Remove a path whether it's a file, directory, or symlink."""
    if path.is_symlink() or path.is_file():
        path.unlink()
        return
    if path.is_dir():
        shutil.rmtree(path)
        return
    path.unlink()


def is_within(candidate: Path, root: Path) -> bool:
    """Return True when candidate path is inside root."""
    try:
        candidate.relative_to(root)
        return True
    except ValueError:
        return False


def log(action: str, detail: str) -> None:
    """Standard log formatter for script actions."""
    print(f"{action:<8} {detail}")


def sync_skill_contents(src_dir: Path, dest_dir: Path, link_options: LinkOptions) -> None:
    """Sync all files under a skill directory into an existing destination directory."""
    for entry in sorted(src_dir.iterdir(), key=lambda path: path.name):
        name = entry.name
        if name in SKILL_CONTENT_IGNORE_NAMES or name.startswith("SKILL.md.bak-"):
            continue

        dest_path = dest_dir / name

        if entry.is_symlink():
            raise ValueError(f"Skill entries must not be symlinks: {entry}")

        if entry.is_dir():
            if ensure_dir(dest_path, link_options):
                sync_skill_contents(entry, dest_path, link_options)
            continue

        sync_skill_file(entry, dest_path, link_options)


def sync_skill_file(src: Path, dest: Path, link_options: LinkOptions) -> None:
    """Copy or hardlink a skill file into the destination (no symlinks)."""
    if dest.exists() or dest.is_symlink():
        if not handle_existing(dest, link_options):
            return

    if not link_options.apply:
        log("SYNC", f"{dest} <- {src}")
        return

    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(src, dest)
        log("HARDLINK", f"{dest} -> {src}")
    except OSError:
        shutil.copy2(src, dest)
        log("COPY", f"{dest} <- {src}")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}")
        raise
