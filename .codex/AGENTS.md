## Bash command hint

- When the path contains `()`, make sure quoting the path.

```bash
sed -n '1,220p' 'app/(app)/run/page.tsx' # correct
sed -n '1,220p' app/(app)/run/page.tsx   # wrong!
```

## Code style

VERY IMPORTANT: You should use type system properly to help you write correct code and NEVER work around the type system.
DONOT use `any` in TypeScript,
DONOT use `# type: ignore` in Python.
