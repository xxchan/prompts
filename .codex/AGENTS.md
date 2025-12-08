## High Level Instructions

### 1. Goal

You are coding for humans, but optimized for agents:
- Make code **easy to reason about** from static analysis + local context.
- Prefer **explicit contracts** over "smart" inference and magic.
- Never trade type safety for convenience.

### 2. Types & Contracts

1. **Single source of truth**
   - For data that crosses boundaries (API, DB, messages), define **one canonical schema**.
   - All other types must be derived from it (via language tools, codegen, or imports), not re-declared.

2. **Never weaken the type system**
   - Do **not** use dynamic escape hatches to silence errors:
     - TypeScript: `any`, `unknown`→`as Any`, non-null `!`, broad `Record<string, any>`.
     - Python: untyped function parameters/returns for public APIs, `# type: ignore` without reason.
     - Other statically typed languages: `unsafe`, raw casts, reflection-based hacks unless strictly necessary.
   - If a type mismatch happens:
     - **Fix the model/contract or call site**, do not cast it away.

3. **Contract-first for I/O**
   - For network, file, DB, message interfaces:
     - Define/adjust the schema/model **first**.
     - Then implement code to conform to that schema.
   - Treat compiler / type-checker errors as the primary feedback loop.

### 3. Code style

不要自作主张，做兜底/兼容性方案，需要写出简洁优美的代码，而不是过分防御式编程。例如不要假设一个 API 可能返回转成了 string 的 JSON 值，要你自己 parse。你应该优先验证这个 API 真实的返回结果的形态。
如果你觉得确有必要兜底，应当先在开始工作前向用户确认；在代码写了一半的时候想到这个问题则优先在代码中用 TODO 的形式作为可能需要考虑的点提出，而不是直接实现兜底。

### 4. Using Libraries

You are encouraged to use well-known libraries to implement features to adopt current best practices, instead of building everything from scratch.

e.g., use ReactQuery, Nuqs, Zod, Tailwind CSS, shadcn/ui, etc.

- When using libraries, you MUST search online to use the latest stable version of the library.

### 5. Verifying Changes

After making changes, it's CRITICAL to verify that the changes are working as expected. Reading code alone is usually not enough.
Whenever possible, you should prefer real verification first, and code analysis second.

e.g., for a web app project, you can start the app locally with `pnpm dev`, and either use `curl` (No token parameter or header is needed for debug requests - it will be injected automatically), chrome devtools MCP, or other kind of scripts to test the changes.

IMPORTANT guidelines: 
- you should start the app in the background, and check its logs.
- do not blindly test. You are encouraged to add more debugging logs if it can help.
- add timeouts to verification scripts/commands to avoid hanging indefinitely.

## Git Guidelines

### VCS workflow

IMPORTANT: Use `git-spice` for stacking workflow - when developing large features, split work in atomic changes, and should be individually mergeable.

cheatsheet:
```
# Track a normal branch - ALWAYS run this before starting work to get the current status of the branch
$ gs branch track

# Stack a new branch on top of the current branch for a large feature X
$ gs branch create feat-x-part-1

# Stack another branch on top of part 1
$ gs branch create feat-x-part-2

# Submit pull requests for part1 and part2.
$ gs stack submit

# Pull latest changes from the remote repository
# and delete merged branches.
$ gs repo sync

# Restack branches on top of the latest changes.
$ gs stack restack
```

## Language Specific Guidelines

### Bash command hint

- When the path contains `()`, make sure quoting the path.

```bash
sed -n '1,220p' 'app/(app)/run/page.tsx' # correct
sed -n '1,220p' app/(app)/run/page.tsx   # wrong!
```

- When interacting with GitHub, use `gh` CLI.
- When using git commands, avoid using editors, e.g., `GIT_EDITOR=true git rebase --continue`
- When starting a long running server, you MUST let it run in the background. Use `tmux` to do so, unless you are explicitly given a tool like `Bash` with `run_in_background` flag.

### Python

DONOT use `try import`, just use `import` directly.
Always use `uv` to run python related tools.

### JavaScript / TypeScript

- Use Temporal instead of Date

## Other guidelines
- When you are asked to write a CHANGELOG, you should find the changelog file in the current project.
  If the CHANGELOG is grouped by date, you must check the current date if you do not know.
