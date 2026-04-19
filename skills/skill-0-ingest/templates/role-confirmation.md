# Role Detection Results

Review the detected roles below. Type `ok` to accept all, or use override/drop commands.

## Commands

- `ok` — accept all and proceed to extraction
- `override N <role>` — change row N to a different role (gap | design-spec | plan | prd | user-stories)
- `drop N` — remove file N from processing (will not be ingested)
- `--tag <role>=<path>` — re-run with explicit override (restart skill)

## Detection Table

| # | File | Detected Role | Confidence | Method | Key Evidence |
|---|------|--------------|------------|--------|-------------|
{{#each detections}}
| {{@index_1}} | `{{basename path}}` | **{{detected_role}}** | {{confidence}}% | {{method}} | {{evidence_summary}} |
{{/each}}

## Legend

- **Confidence ≥ 70%** → auto-accepted (shown without ⚠)
- **Confidence 40–69%** → ⚠ needs confirmation
- **Confidence < 40%** → ✗ `unknown` — requires `override N <role>` or will be dropped

## What each role produces

| Role | YAML artifact |
|------|--------------|
| `gap` | `{date}-gap-analysis.yaml` |
| `design-spec` | `{date}-task-hints.yaml` |
| `plan` | `{date}-prd-structure.yaml` (partial) + `{date}-task-hints.yaml` (steps only) |
| `prd` | `{date}-prd-structure.yaml` (full) |
| `user-stories` | `{date}-prd-structure.yaml` (user_stories section only) |

---

> Type `ok` to proceed, or adjust with `override` / `drop` commands.
