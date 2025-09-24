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
