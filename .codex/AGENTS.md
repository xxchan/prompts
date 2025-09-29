## Bash command hint

- When the path contains `()`, make sure quoting the path.

```bash
sed -n '1,220p' 'app/(app)/run/page.tsx' # correct
sed -n '1,220p' app/(app)/run/page.tsx   # wrong!
```

## Code style

### Type safety

VERY IMPORTANT: You should use type system properly to help you write correct code and NEVER work around the type system.
DONOT use `any`/`unknown` in TypeScript, try to figure out the correct type of the value.
DONOT use `# type: ignore` in Python.

### Python

DONOT use `try import`, just use `import` directly.


## Verifying Changes

After making changes, it's CRITICAL to verify that the changes are working as expected. Reading code alone is usually not enough.
Whenever possible, you should prefer real verification first, and code analysis second.

e.g., for a web app project, you can start the app locally with `pnpm dev`, and either use `curl` (No token parameter or header is needed for debug requests - it will be injected automatically), chrome devtools MCP, or other kind of scripts to test the changes.

IMPORTANT guidelines: 
- you should start the app in the background, and check its logs.
- do not blindly test. You are encouraged to add more debugging logs if it can help.
- add timeouts to verification scripts/commands to avoid hanging indefinitely.
