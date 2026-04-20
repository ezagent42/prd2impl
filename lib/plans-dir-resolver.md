# plans-dir-resolver

Shared path resolution logic for prd2impl skills. All skills that read/write
artifacts under `docs/plans/` must call this resolution before constructing
paths.

## Resolution Order

```
resolve_plans_dir():
  1. if CLI flag --plans-dir <path> was passed:         return <path>
  2. elif project.yaml has `plans_dir` field (non-empty): return project.yaml.plans_dir
  3. else:                                               return "docs/plans"
```

After resolution, if the resolved directory does not exist, `mkdir -p` it
silently (no error, no prompt).

## Legality Checks

Normalize runs on every resolved value (including the default) before paths
are constructed, so downstream path concatenation `{plans_dir}/{name}` never
produces a double slash. Then run the following checks in order; reject with
error message if any fails:

1. **Normalize**: strip trailing `/`, resolve `./`, convert `\` → `/` (Windows)
2. **Absolute path check**: if starts with `/` or matches `[A-Za-z]:` →
   error: `"plans_dir must be a repository-relative path. Got: '<input>'"`
3. **`..` segment check**: after split by `/`, if any segment is `..` →
   error: `"plans_dir must not contain '..' segments. Got: '<input>'"`
4. **Empty string**: treat as default `docs/plans` (no error)

## Usage in SKILL.md files

When a skill constructs an output path, use `{plans_dir}` as the placeholder:

- Before: `docs/plans/{date}-tasks.yaml`
- After:  `{plans_dir}/{date}-tasks.yaml`

Where `{plans_dir}` is the return of `resolve_plans_dir()` at skill invocation
time.

## Examples

| Input | Resolved |
|-------|----------|
| CLI `--plans-dir docs/plans/m2`, no project.yaml | `docs/plans/m2` |
| No CLI, `project.yaml.plans_dir: docs/plans/m2` | `docs/plans/m2` |
| No CLI, no project.yaml.plans_dir | `docs/plans` |
| CLI `--plans-dir /tmp/plans` | ERROR (absolute path) |
| CLI `--plans-dir ../plans` | ERROR (`..` segment) |
| CLI `--plans-dir "docs/plans/m2/"` | `docs/plans/m2` (trailing slash stripped) |
