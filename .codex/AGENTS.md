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

2. Annotate **explicit type hints** judiciously at boundaries where types are not locally obvious.

  Always annotate:
  - External API/SDK return values: `const value: SdkType[] = await sdk.fetch()`
  - Exported function signatures (params + return): `export function parse(raw: string): Config`
  - Cross-module boundaries where tracing requires file jumps

  Why this matters:
  1. Enables static type lookup via CLI tools (`npx expand-my-type file.ts TypeName`)
  2. Removes need for runtime defensive checks (`typeof x === 'number'`)
  3. Makes code locally readable without IDE hover

3. **Never weaken the type system**
   - Find the type definition first if you are not sure.
     - If you are given concrete IDE/LSP tools, use that.
     - TypeScript: prefer `npx expand-my-type <file.ts> <TypeName>` to search in `node_modules`.
     - If you failed to get the type quickly, use a subagent to find the type definition in `node_modules`, `site-packages` etc.
   - NEVER use dynamic escape hatches to silence errors:
     - TypeScript: `any`, `unknown`→`as Any`, non-null `!`, broad `Record<string, any>`.
     - Python: untyped function parameters/returns for public APIs, `# type: ignore` without reason.
     - Other statically typed languages: `unsafe`, raw casts, reflection-based hacks unless strictly necessary.
   - If a type mismatch happens:
     - **Fix the model/contract or call site**, do not cast it away.

4. **Contract-first for I/O**
   - For network, file, DB, message interfaces:
     - Define/adjust the schema/model **first**.
     - Then implement code to conform to that schema.
   - Treat compiler / type-checker errors as the primary feedback loop.

### 3. Code style

- VERY IMPORTANT: 避免过度防御式编程。防御式编程本质上是懒惰、对问题本质理解不清楚的表现。正确的做法是搞清楚 Single source of truth，依赖正确而合理的假设。依赖类型系统。
  不要自作主张，做兜底/兼容性方案，需要写出简洁优美的代码。

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
# Check current git spice stack status
$ gs ls

# Track a normal branch
$ gs branch track

# Stack a new branch on top of the current branch for a large feature X (and commit staged changes)
$ gs branch create feat-x-part-1 -m "commit message"

# Stack another branch on top of part 1 without commit
$ gs branch create feat-x-part-2 --no-commit

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
