use std::collections::BTreeMap;
use std::env;
use std::fmt;
use std::fmt::Write as _;
use std::fs;
use std::io::{self, Write};
use std::path::{Path, PathBuf};

use anyhow::{Context, Result};
use clap::{Args, Parser, Subcommand};
use ignore::{DirEntry, WalkBuilder};
use tiktoken_rs::cl100k_base;

const DEFAULT_IGNORED_DIRS: [&str; 5] = [".git", "node_modules", "target", ".venv", "venv"];

#[derive(Parser, Debug)]
#[command(
    name = "prompkit",
    version,
    about = "Handy tools for working with prompts",
    propagate_version = true
)]
struct Cli {
    #[command(subcommand)]
    command: Command,
}

#[derive(Subcommand, Debug)]
enum Command {
    /// Dump repository context and file contents as a prompt.
    ///
    /// Output is written to stdout, so you can pipe it to a CLI agent.
    /// Some stats info is written to stderr.
    /// Some common ignore dirs e.g., `node_modules`, `target` will be ignored, and `.gitignore` will also be respected
    Dump(DumpArgs),
}

#[derive(Args, Debug)]
struct DumpArgs {
    /// Message describing what you want the AI to do with the context.
    task: String,
    /// Directory to dump. Defaults to the current working directory.
    #[arg(short, long, value_name = "PATH")]
    path: Option<PathBuf>,
    /// Maximum file size (in bytes) to include in the dump.
    #[arg(long, value_name = "BYTES", default_value_t = 64_000)]
    max_file_size: usize,
}

struct FileDump {
    relative_path: String,
    contents: String,
}

struct SkippedFile {
    relative_path: String,
    reason: SkipReason,
}

enum SkipReason {
    TooLarge(u64),
    NonUtf8,
    Io(String),
}

impl fmt::Display for SkipReason {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            SkipReason::TooLarge(len) => write!(f, "exceeds size limit ({} bytes)", len),
            SkipReason::NonUtf8 => write!(f, "non-UTF-8 content"),
            SkipReason::Io(err) => write!(f, "I/O error: {err}"),
        }
    }
}

fn main() -> Result<()> {
    let cli = Cli::parse();

    match cli.command {
        Command::Dump(args) => run_dump(args)?,
    }

    Ok(())
}

fn run_dump(args: DumpArgs) -> Result<()> {
    let user_message = args.task;
    let root_dir = match args.path {
        Some(path) => path,
        None => env::current_dir().context("failed to determine current directory")?,
    };

    let root_dir = root_dir
        .canonicalize()
        .with_context(|| format!("failed to resolve path {}", root_dir.display()))?;

    let (files, skipped) = collect_files(&root_dir, args.max_file_size)?;

    let mut prompt = String::new();

    writeln!(
        prompt,
        "The following is the context of a directory. After the context, I will give you a task. You need to do the task based on the context."
    )?;
    writeln!(prompt)?;
    writeln!(prompt, "# Repository Context")?;
    writeln!(prompt, "Root: {}", root_dir.display())?;
    writeln!(prompt)?;

    let file_tree = build_file_tree(&files);
    writeln!(prompt, "## File Tree")?;
    writeln!(prompt, "{}", file_tree)?;
    writeln!(prompt)?;

    writeln!(prompt, "## Files")?;
    for file in &files {
        writeln!(prompt, "### {}", &file.relative_path)?;
        prompt.push_str("```\n");
        prompt.push_str(&file.contents);
        if !file.contents.ends_with('\n') {
            prompt.push('\n');
        }
        prompt.push_str("```\n\n");
    }

    writeln!(prompt, "# Task")?;
    writeln!(
        prompt,
        "Based on the context above, please finish the following task:"
    )?;
    writeln!(prompt, "{}", user_message.trim_end())?;
    writeln!(prompt)?;

    let mut stdout = io::BufWriter::new(io::stdout().lock());
    stdout.write_all(prompt.as_bytes())?;
    stdout.flush()?;

    // Stats info (stderr)

    let tokenizer = cl100k_base().context("failed to load cl100k_base tokenizer")?;
    let token_count = tokenizer.encode_ordinary(&prompt).len();
    let included_count = files.len();
    let skipped_count = skipped.len();
    let total_bytes: usize = files.iter().map(|file| file.contents.len()).sum();

    if !skipped.is_empty() {
        for skipped_file in &skipped {
            eprintln!(
                "Skipped: path={}, reason={}",
                skipped_file.relative_path, skipped_file.reason
            );
        }
    }

    eprintln!(
        "Stats: tokens={}, files_included={}, files_skipped={}, bytes={}",
        token_count, included_count, skipped_count, total_bytes
    );
    Ok(())
}

fn collect_files(root: &Path, max_file_size: usize) -> Result<(Vec<FileDump>, Vec<SkippedFile>)> {
    let mut builder = WalkBuilder::new(root);
    builder
        .git_ignore(true)
        .git_exclude(true)
        .parents(true)
        .hidden(false)
        .follow_links(false)
        .filter_entry(|entry| should_include(entry));

    let mut files = Vec::new();
    let mut skipped = Vec::new();

    for entry in builder.build() {
        match entry {
            Ok(dir_entry) => {
                if dir_entry.depth() == 0 {
                    continue;
                }

                if dir_entry.file_type().map(|ft| ft.is_dir()).unwrap_or(false) {
                    continue;
                }

                let metadata = match dir_entry.metadata() {
                    Ok(meta) => meta,
                    Err(err) => {
                        skipped.push(SkippedFile {
                            relative_path: to_relative(root, dir_entry.path()),
                            reason: SkipReason::Io(err.to_string()),
                        });
                        continue;
                    }
                };

                if !metadata.is_file() {
                    continue;
                }

                if metadata.len() as usize > max_file_size {
                    skipped.push(SkippedFile {
                        relative_path: to_relative(root, dir_entry.path()),
                        reason: SkipReason::TooLarge(metadata.len()),
                    });
                    continue;
                }

                let data = match fs::read(dir_entry.path()) {
                    Ok(data) => data,
                    Err(err) => {
                        skipped.push(SkippedFile {
                            relative_path: to_relative(root, dir_entry.path()),
                            reason: SkipReason::Io(err.to_string()),
                        });
                        continue;
                    }
                };

                let contents = match String::from_utf8(data) {
                    Ok(text) => text,
                    Err(_) => {
                        skipped.push(SkippedFile {
                            relative_path: to_relative(root, dir_entry.path()),
                            reason: SkipReason::NonUtf8,
                        });
                        continue;
                    }
                };

                files.push(FileDump {
                    relative_path: to_relative(root, dir_entry.path()),
                    contents,
                });
            }
            Err(err) => {
                let reason_message = err
                    .io_error()
                    .map(|io_err| io_err.to_string())
                    .unwrap_or_else(|| err.to_string());
                skipped.push(SkippedFile {
                    relative_path: "<walker>".to_string(),
                    reason: SkipReason::Io(reason_message),
                });
            }
        }
    }

    files.sort_by(|a, b| a.relative_path.cmp(&b.relative_path));
    skipped.sort_by(|a, b| a.relative_path.cmp(&b.relative_path));

    Ok((files, skipped))
}

fn should_include(entry: &DirEntry) -> bool {
    if entry.depth() == 0 {
        return true;
    }

    if entry.file_type().map(|ft| ft.is_dir()).unwrap_or(false) {
        if let Some(name) = entry.file_name().to_str() {
            return !DEFAULT_IGNORED_DIRS.contains(&name);
        }
    }

    true
}

fn to_relative(root: &Path, path: &Path) -> String {
    path.strip_prefix(root)
        .map(|p| p.display().to_string())
        .unwrap_or_else(|_| path.display().to_string())
}

#[derive(Default)]
struct TreeNode {
    children: BTreeMap<String, TreeNode>,
    is_file: bool,
}

impl TreeNode {
    fn insert(&mut self, components: &[&str]) {
        if let Some((first, rest)) = components.split_first() {
            let child = self.children.entry((*first).to_string()).or_default();
            if rest.is_empty() {
                child.is_file = true;
            } else {
                child.insert(rest);
            }
        }
    }
}

fn build_file_tree(files: &[FileDump]) -> String {
    let mut root = TreeNode::default();
    for file in files {
        let path = Path::new(&file.relative_path);
        let components: Vec<String> = path
            .components()
            .map(|component| component.as_os_str().to_string_lossy().into_owned())
            .collect();
        let parts: Vec<&str> = components.iter().map(String::as_str).collect();
        if parts.is_empty() {
            continue;
        }
        root.insert(&parts);
    }

    let mut lines = Vec::new();
    lines.push(".".to_string());
    render_tree(&root, "", &mut lines);
    lines.join("\n")
}

fn render_tree(node: &TreeNode, prefix: &str, lines: &mut Vec<String>) {
    let total = node.children.len();
    for (idx, (name, child)) in node.children.iter().enumerate() {
        let is_last = idx + 1 == total;
        let connector = if is_last { "`-- " } else { "|-- " };
        let mut line = String::new();
        line.push_str(prefix);
        line.push_str(connector);
        line.push_str(name);
        if !child.children.is_empty() && !child.is_file {
            line.push('/');
        }
        lines.push(line);

        if !child.children.is_empty() {
            let mut new_prefix = String::from(prefix);
            new_prefix.push_str(if is_last { "    " } else { "|   " });
            render_tree(child, &new_prefix, lines);
        }
    }
}
