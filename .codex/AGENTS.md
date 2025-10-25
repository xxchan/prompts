## Bash command hint

- When the path contains `()`, make sure quoting the path.

```bash
sed -n '1,220p' 'app/(app)/run/page.tsx' # correct
sed -n '1,220p' app/(app)/run/page.tsx   # wrong!
```

- When interacting with GitHub, use `gh` CLI.
- When starting a long running server, you MUST let it run in the background. Use `tmux` to do so, unless you are explicitly given a tool like `Bash` with `run_in_background` flag.

## Code style

不要自作主张，做兜底/兼容性方案，需要写出简洁优美的代码，而不是过分防御式编程。例如不要假设一个 API 可能返回转成了 string 的 JSON 值，要你自己 parse。你应该优先验证这个 API 真实的返回结果的形态。
如果你觉得确有必要兜底，应当先向用户确认，或者优先在代码中用 TODO 的形式作为可能需要考虑的点提出，而不是直接实现兜底。

### Type safety

VERY IMPORTANT: You should use type system properly to help you write correct code and NEVER work around the type system.
DONOT use `any`/`unknown` in TypeScript, try to figure out the correct type of the value.
DONOT use `# type: ignore` in Python.

### Python

DONOT use `try import`, just use `import` directly.

## Using Libraries

You are encouraged to use well-known libraries to implement features to adopt current best practices, instead of building everything from scratch.

e.g., use ReactQuery, Nuqs, Zod, Tailwind CSS, shadcn/ui, etc.

- When using libraries, you MUST use the latest stable version of the library. You must search for the latest version of the library on the internet.



## Verifying Changes

After making changes, it's CRITICAL to verify that the changes are working as expected. Reading code alone is usually not enough.
Whenever possible, you should prefer real verification first, and code analysis second.

e.g., for a web app project, you can start the app locally with `pnpm dev`, and either use `curl` (No token parameter or header is needed for debug requests - it will be injected automatically), chrome devtools MCP, or other kind of scripts to test the changes.

IMPORTANT guidelines: 
- you should start the app in the background, and check its logs.
- do not blindly test. You are encouraged to add more debugging logs if it can help.
- add timeouts to verification scripts/commands to avoid hanging indefinitely.
