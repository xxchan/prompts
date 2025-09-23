#!/usr/bin/env bash
set -euo pipefail

# Default source directory is current working directory; override via first positional arg
SRC_DIR="$(pwd)"
DEST_DIR=${DEST_DIR:-"$HOME"}

MODE="backup"   # skip | backup | replace
APPLY=false      # dry-run unless --apply
SCOPE="files"   # files (recursive per-file linking) | top (top-level only)

usage() {
  cat <<EOF
Usage: $(basename "$0") [SOURCE_DIR] [--mode skip|backup|replace] [--apply] [--dest DIR] [--top-level]

Creates symlinks into "$HOME" from SOURCE_DIR.
Defaults: SOURCE_DIR=cwd, mode=backup, scope=per-file (recursive), dry-run.

Options:
  --mode       Conflict handling: skip (do nothing), backup (rename existing to .bak-<timestamp>), replace (remove then link)
  --apply      Perform changes (otherwise dry-run)
  --dest DIR   Destination directory (default: "$HOME")
  --top-level  Link only top-level items as symlinks (no recursion)

Ignores by default: .git, .DS_Store, README*, LICENSE*, node_modules, target, dist, scripts
Explicitly allowed examples: .claude, .codex

Behavior:
  - If destination already links to the same source, it is left unchanged.
  - If destination exists and has the same file content as the source, it is left unchanged (no backup/replace).
EOF
}

timestamp() { date +%Y%m%d-%H%M%S; }

# Compare two paths and return success if their contents are identical (non-directories)
files_same() {
  local a="$1" b="$2"
  # Only compare if both exist and are not directories
  if [[ -e "$a" && -e "$b" && ! -d "$a" && ! -d "$b" ]]; then
    cmp -s -- "$a" "$b"
    return $?
  fi
  return 1
}

# Parse flags (after optional SRC_DIR positional)
if [[ $# -gt 0 && $1 != --* ]]; then
  SRC_DIR=$1
  shift
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      MODE=${2:-}
      [[ -z "$MODE" ]] && { echo "--mode requires a value" >&2; exit 2; }
      shift 2
      ;;
    --apply)
      APPLY=true
      shift
      ;;
    --dest)
      DEST_DIR=${2:-}
      [[ -z "$DEST_DIR" ]] && { echo "--dest requires a value" >&2; exit 2; }
      shift 2
      ;;
    --top-level)
      SCOPE="top"
      shift
      ;;
    -h|--help)
      usage; exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2; usage; exit 2
      ;;
  esac
done

if [[ ! -d "$SRC_DIR" ]]; then
  echo "Source directory not found: $SRC_DIR" >&2
  exit 1
fi

# Normalize to absolute, canonical path to avoid relative symlink targets
SRC_DIR="$(cd "$SRC_DIR" && pwd -P)"

mkdir -p "$DEST_DIR"
# Canonicalize destination too (after ensuring it exists)
DEST_DIR="$(cd "$DEST_DIR" && pwd -P)"

# Ignore patterns
IGNORE_PATTERNS=(
  ".git" ".DS_Store" "README" "README.md" "LICENSE" "LICENSE.md" \
  "node_modules" "target" "dist" "scripts" ".vscode" \
  "promptkit"
)

should_ignore() {
  local name="$1"
  for p in "${IGNORE_PATTERNS[@]}"; do
    if [[ "$name" == "$p" ]]; then
      return 0
    fi
  done
  # Also ignore any README* or LICENSE* generically
  if [[ "$name" == README* || "$name" == LICENSE* ]]; then
    return 0
  fi
  return 1
}

ensure_dir() {
  local dir="$1"
  if [[ -d "$dir" ]]; then
    return 0
  fi
  if [[ -e "$dir" || -L "$dir" ]]; then
    case "$MODE" in
      skip)
        echo "SKIP        $dir (exists and not dir)"
        return 1
        ;;
      backup)
        local bak="$dir.bak-$(timestamp)"
        echo "BACKUP  $dir -> $bak"
        if $APPLY; then
          mv "$dir" "$bak"
        fi
        ;;
      replace)
        echo "REMOVE  $dir"
        if $APPLY; then
          rm -rf "$dir"
        fi
        ;;
      *)
        echo "Unknown MODE: $MODE" >&2; exit 2
        ;;
    esac
  fi
  echo "MKDIR   $dir"
  if $APPLY; then
    mkdir -p "$dir"
  fi
}

link_one() {
  local src="$1"        # full path
  local rel="$2"        # relative name under SRC_DIR
  local dst="$DEST_DIR/$rel"

  # Ensure parent exists in DEST
  local parent
  parent=$(dirname "$dst")
  ensure_dir "$parent" || return 0

  # If exists and is already correct symlink, skip
  if [[ -L "$dst" ]]; then
    local target
    target=$(readlink "$dst")
    if [[ "$target" == "$src" ]]; then
      echo "NOOP (already linked)        $dst -> $src"
      return
    fi
  fi

  # If destination exists and contents are identical to source, leave as-is
  if [[ -e "$dst" || -L "$dst" ]]; then
    if files_same "$src" "$dst"; then
      echo "NOOP (same content)        $dst == $src "
      return
    fi
  fi

  if [[ -e "$dst" || -L "$dst" ]]; then
    case "$MODE" in
      skip)
        echo "SKIP        $dst (exists)"
        return
        ;;
      backup)
        local bak="$dst.bak-$(timestamp)"
        echo "BACKUP        $dst -> $bak"
        if $APPLY; then
          mv "$dst" "$bak"
        fi
        ;;
      replace)
        echo "REMOVE        $dst"
        if $APPLY; then
          rm -rf "$dst"
        fi
        ;;
      *)
        echo "Unknown MODE: $MODE" >&2; exit 2
        ;;
    esac
  fi

  echo "LINK!        $dst -> $src"
  if $APPLY; then
    ln -s "$src" "$dst"
  fi
}

link_tree() {
  local cur_src="$1"
  local rel_prefix="$2"  # may be empty or end with '/'
  local name src_path rel_path
  while IFS= read -r name; do
    [[ -z "$name" ]] && continue
    if should_ignore "$name"; then
      local shown_name="$rel_prefix$name"
      echo "IGNORE        ${shown_name%/}"
      continue
    fi
    src_path="$cur_src/$name"
    # Prevent recursing into destination directory if it resides under source
    # Resolve to canonical absolute path if possible
    if [[ -d "$src_path" ]]; then
      local cand_abs
      cand_abs=$(cd "$src_path" 2>/dev/null && pwd -P || echo "")
      # If destination lies within this source directory, skip to avoid self-recursion
      if [[ -n "$cand_abs" && ( "$DEST_DIR" == "$cand_abs" || "$DEST_DIR" == "$cand_abs"/* ) ]]; then
        local shown_name="$rel_prefix$name"
        echo "IGNORE        ${shown_name%/} (dest)"
        continue
      fi
    fi
    rel_path="${rel_prefix}$name"
    if [[ -d "$src_path" && ! -L "$src_path" ]]; then
      # Create/ensure directory in dest, then recurse
      ensure_dir "$DEST_DIR/$rel_path" || true
      link_tree "$src_path" "$rel_path/"
    else
      link_one "$src_path" "$rel_path"
    fi
  done < <(cd "$cur_src" && ls -A1)
}

cd "$SRC_DIR"

if [[ "$SCOPE" == "top" ]]; then
  while IFS= read -r name; do
    [[ -z "$name" ]] && continue
    if should_ignore "$name"; then
      echo "IGNORE        $name"
      continue
    fi
    src_path="$SRC_DIR/$name"
    rel_path="$name"
    link_one "$src_path" "$rel_path"
  done < <(ls -A1)
else
  link_tree "$SRC_DIR" ""
fi

if ! $APPLY; then
  echo
  echo "Dry-run only. Re-run with --apply to make changes."
  echo "Example: $(basename "$0") \"$SRC_DIR\" --mode backup --apply"
fi
