# Repository Guidelines

## Overview
Prompt is the umbrella repository for coding-agent assets (skills, prompts, and agent docs). 
Treat this repo as the single source of truth for all my agent configs.

## Project Structure & Module Organization
- `.codex/` stores Codex agent config files (e.g., `.codex/AGENTS.md`) and a `.codex/skills` link for Codex discovery.
- `skills/` stores repo-managed skills (`skills/<skill>/SKILL.md`).
- `promptkit/` contains the Rust CLI (`promptkit/src/main.rs`, `promptkit/Cargo.toml`).
- `skills/` stores repo-managed skills (`skills/<skill>/SKILL.md`).
- `scripts/` includes utility scripts (e.g., `scripts/install.py` for symlink setup).

## Build, Test, and Development Commands

Script helper:
- `scripts/install.py --help` shows usage for symlink setup (dry-run by default).
- `scripts/install.py --only-codex --codex-sync --apply` imports Codex skills and links them into `~/.codex`.
- `scripts/install.py --only-claude --claude-sync --apply` imports Claude skills and links them into `~/.claude`.
