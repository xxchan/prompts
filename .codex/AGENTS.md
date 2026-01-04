## High Level Instructions

### Goal

You are coding for humans, but optimized for agents:
- Make code **easy to reason about** from static analysis + local context.
- Prefer **explicit contracts** over "smart" inference and magic.

### Types & Contracts

Never trade type safety for convenience.

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
   - Find the type definition first if you are not sure. AVOID defensive programming.
     - If you are given concrete IDE/LSP tools, use that.
     - TypeScript: use `npx expand-my-type <file.ts> <TypeName>` aggressively.
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

### Code style

- VERY IMPORTANT: 避免过度防御式编程。防御式编程本质上是懒惰、对问题本质理解不清楚的表现。正确的做法是搞清楚 Single source of truth，依赖正确而合理的假设。依赖类型系统。
  不要自作主张，做兜底/兼容性方案，需要写出简洁优美的代码。

### Using Libraries

You are encouraged to use well-known libraries to implement features to adopt current best practices, instead of building everything from scratch.

e.g., use ReactQuery, Nuqs, Zod, Tailwind CSS, shadcn/ui, etc.

- When using libraries, you MUST search online to use the latest stable version of the library.

### Verifying Changes

After making changes, it's CRITICAL to verify that the changes are working as expected. Reading code alone is usually not enough.
Whenever possible, you should prefer real verification first, and code analysis second.

e.g., for a web app project, you can start the app locally with `pnpm dev`, and either use `curl` (No token parameter or header is needed for debug requests - it will be injected automatically), chrome devtools MCP, or other kind of scripts to test the changes.

IMPORTANT guidelines: 
- you should start the app in the background, and check its logs.
- do not blindly test. You are encouraged to add more debugging logs if it can help.
- add timeouts to verification scripts/commands to avoid hanging indefinitely.

### Build skills to improve yourself

When assigned a task, you should always think whether it needs a skill - 
specialized knowledge, workflows, and tools.
If you do not have the needed one, use `skill-creator` skill to build it first.
Sometimes the user may assign a task with very specific instructions or workflow. 
In this case, you can also create a corresponding skill so the user do not need to
instruct in the future.

Remember that skills are imperfect and can always be iteratively improved.
After finishing tasks, if you find bugs or inefficiencis, you can update 
workflows, and tools, or jot down the lesson to improve the skill.


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


## Other guidelines
- When you are asked to write a CHANGELOG, you should find the changelog file in the current project.
  If the CHANGELOG is grouped by date, you must check the current date if you do not know.
- When you are clearly not in a project (e.g., `/tmp`), there's no need to explore directories.
- After the user explictity asked you to do a commit, you should also do a commit for all code changes later.