---
name: ingest-docs
description: "Heterogeneous document ingestion — parse multiple human-authored Markdown files (gap analyses, design specs, plans, PRDs) into the same YAML artifacts as skill-1/skill-2, plus a task-hints.yaml that preserves human design decisions. Use when the user says 'ingest docs', 'read my markdown files', 'import gap analysis', or provides multiple MD files as starting point instead of a formal PRD."
---

# Skill 0: Ingest Docs

<SUBAGENT-STOP>
If you were dispatched as a subagent to execute a specific task, skip this skill.
</SUBAGENT-STOP>

Convert multiple human-authored Markdown files into the YAML artifacts that `skill-3-task-gen` and the rest of the prd2impl pipeline expect. This is **Entry B** — an alternative to running `/prd-analyze` (Entry A) when the project already has hand-written gap analyses, design specs, or plans.

## Trigger

- User runs `/ingest-docs [file1.md] [file2.md] ...`
- User provides `--tag role=path` overrides alongside file paths
- User says "ingest my docs", "read my markdown files", "import gap analysis and design spec"

## Inputs

- **Required**: One or more MD file paths
- **Optional**: `--tag <role>=<path>` overrides (force a role instead of auto-detecting)
  - Valid roles: `gap`, `design-spec`, `plan`, `prd`, `user-stories`
  - Example: `--tag spec=a.md --tag gap=b.md`

## Outputs

Three YAML files written to `{plans_dir}/{date}-*.yaml`:

| File | Produced when | Consumed by |
|------|--------------|-------------|
| `{date}-prd-structure.yaml` | Any `prd`, `plan`, or `user-stories` MD found | skill-3-task-gen |
| `{date}-gap-analysis.yaml` | Any `gap` MD found | skill-3-task-gen |
| `{date}-task-hints.yaml` | Any `design-spec` or `plan` MD found | skill-3-task-gen (optional) |

All files carry `source_type: "ingested"` to distinguish them from skill-1/skill-2 outputs.

---

## Phase 1 · Role Detection

**Read**: `lib/role-detector.md` — follow it exactly for this phase.

Steps:
1. For each input file, run the 4-signal heuristic scorer.
2. For any file scoring < 70, invoke LLM fallback (see role-detector §LLM fallback).
3. Apply any `--tag` overrides (force confidence=100 for those files).
4. Build the confirmation table using `templates/role-confirmation.md`.
5. Print the table to the user.

**[HUMAN REVIEW CHECKPOINT 1]**

Present the table and wait. Accept commands:
- `ok` → proceed to Phase 2
- `override N <role>` → update role for row N; re-display table; ask again
- `drop N` → remove file from processing list; re-display; ask again

If all remaining files are `unknown` → abort:
```
ERROR: All input files classified as 'unknown'. Re-run with --tag role=path to specify roles.
```

---

## Phase 2 · Extraction (per-role, sequential)

**Important**: Run extractors in the order: gap → spec → prd. This order ensures `gap_analysis` is populated before spec-extractor's cross-references need it.

### 2a. Gap extraction

If any files have `detected_role: gap`:
- **Read**: `lib/gap-extractor.md` — follow it exactly.
- Build `gap_analysis` dict in memory.
- Print: `  Extracted {N} gaps (P0={n0}, P1={n1}, P2={n2}) from {files}`

### 2b. Spec extraction

If any files have `detected_role: design-spec`:
- **Read**: `lib/spec-extractor.md` — follow it exactly for task-hints extraction.
- **Read**: `lib/prd-extractor.md §Extraction: role=design-spec` — follow it for modules/nfrs/constraints extraction.
- Build `task_hints` dict in memory (from spec-extractor).
- Build or extend `prd_structure` dict in memory (from prd-extractor, partial: modules/nfrs/constraints only).
- Print: `  Extracted {F} file_changes, {S} steps, {G} non_goals (spec) + {M} modules, {N} nfrs, {C} constraints (design) from {files}`

If any files have `detected_role: plan`:
- **Read**: `lib/spec-extractor.md` for steps extraction only (skip file_changes section).
- **Read**: `lib/prd-extractor.md §Extraction: role=plan` for module extraction.
- Merge step data into `task_hints`; merge module data into `prd_structure`.
- Print: `  Extracted {S} steps (plan) + {M} modules from {files}`

### 2c. PRD / user-stories extraction

If any files have `detected_role: prd` or `detected_role: user-stories`:
- **Read**: `lib/prd-extractor.md` — follow the appropriate role routing.
- Build or extend `prd_structure` dict in memory.
- Print: `  Extracted {M} modules, {U} user stories, {N} NFRs from {files}`

---

## Phase 3 · Cross-Validation

**Read**: `lib/cross-validator.md` — follow it exactly for this phase.

Steps:
1. Run Rule 4 (fatal check) first.
   - If any fatal: print conflict details; **abort — do not write any files**.
2. Run Rules 1, 2, 3, 5 (warning checks). Collect all warnings.
3. If any warnings: print warning table.

**[HUMAN REVIEW CHECKPOINT 2]** (only if warnings exist)

```
Cross-validation complete. {F} fatal errors, {W} warnings.

{warning_table}

Proceed despite warnings? (y/n):
```

- `n` → abort (no files written)
- `y` → proceed to Phase 4

If no warnings (and no fatals): skip checkpoint, proceed automatically.

---

## Phase 4 · Write + Summary

> **Path resolution**: Before constructing any output path, resolve `{plans_dir}` per `lib/plans-dir-resolver.md`. All paths below use `{plans_dir}` as the base directory.

### 4.1 Determine output paths

```
{plans_dir}/{date}-gap-analysis.yaml      (if gap_analysis populated)
{plans_dir}/{date}-prd-structure.yaml     (if prd_structure populated)
{plans_dir}/{date}-task-hints.yaml        (if task_hints populated)
```

Where `{date}` = today's date in `YYYY-MM-DD` format.

If a file already exists at the target path: print a diff-summary line (informational, non-blocking) and overwrite.

**Required diff-summary format** (enforced — tests match on this):

```
Overwriting {path} ({old_count} → {new_count} {entity}[, {old_N} → {new_N} {entity2}]...)
```

- MUST start with the literal word `Overwriting ` followed by the absolute/relative path.
- MUST contain at least one `{old_count} → {new_count} {entity}` delta inside parentheses, using the `→` arrow character (U+2192).
- Per-artifact primary entities (use these labels; add secondary deltas as relevant):
  - `gap-analysis.yaml` → `gaps` (primary), `P0` / `P1` / `P2` (secondary)
  - `prd-structure.yaml` → `modules` (primary), `user_stories` / `constraints` (secondary)
  - `task-hints.yaml` → `file_changes` (primary), `steps` / `non_goals` (secondary)
- If `old_count` is 0 (file did not exist before overwrite — shouldn't reach this branch, but defensive), skip the diff and print `Writing {path} ({new_count} {entity})` instead.

**Required downstream-invalidation hint** (print verbatim after the overwrite):

```
Note: tasks.yaml for this plans_dir already exists and may now be inconsistent. Re-run /task-gen to regenerate.
```

Only print the hint if `{plans_dir}/tasks.yaml` exists at overwrite time; otherwise skip it (no downstream to invalidate yet).

Users who want to keep both versions should run with a different `--plans-dir`.

**Worked example** — re-running ingest on an updated PRD:

```
Overwriting docs/plans/m2/2026-04-20-prd-structure.yaml (12 → 13 modules, 47 → 49 user_stories)
Overwriting docs/plans/m2/2026-04-20-gap-analysis.yaml (17 → 18 gaps, 6 → 7 P0)
Note: tasks.yaml for this plans_dir already exists and may now be inconsistent. Re-run /task-gen to regenerate.
```

### 4.2 Write files

Write each populated YAML dict to its target path. Validate that:
- `gap_analysis.yaml` begins with `gap_analysis:` key
- `prd-structure.yaml` begins with `prd_structure:` key
- `task-hints.yaml` begins with `task_hints:` key

### 4.3 Print summary

```
─────────────────────────────────────────────────────
skill-0-ingest complete
─────────────────────────────────────────────────────
Input files:  {N} processed, {D} dropped, {U} unknown/skipped

Outputs written:
  {plans_dir}/{date}-gap-analysis.yaml      {N_gaps} gaps  (P0={n0}, P1={n1}, P2={n2})
  {plans_dir}/{date}-prd-structure.yaml     {N_mods} modules, {N_us} user stories
  {plans_dir}/{date}-task-hints.yaml        {N_fc} file_changes, {N_steps} steps

Cross-validation:  {W} warnings (see above), 0 fatals

─────────────────────────────────────────────────────
```

**[HUMAN REVIEW CHECKPOINT 3]**

```
Review the output YAMLs above.

Next step: run /task-gen to generate tasks from these artifacts.
Pass the gap-analysis and prd-structure paths explicitly if needed:
  /task-gen {plans_dir}/{date}-gap-analysis.yaml {plans_dir}/{date}-prd-structure.yaml

If task-hints.yaml was produced, skill-3 will pick it up automatically from {plans_dir}/.

Ready to run /task-gen? (y/n — or adjust the YAML files first)
```

---

## Error handling reference

| Scenario | Response |
|----------|----------|
| Input file not found | `ERROR: file not found: {path}` → abort before Phase 1 |
| All files unknown after Phase 1 | `ERROR: all unknown` → abort with `--tag` suggestion |
| One file fails extraction | Skip file + warning; continue with others |
| Fatal cross-validation conflict | Abort Phase 4; print conflict pairs |
| Same-day re-run of /ingest-docs | Overwrite with diff-summary log (no suffix; use different --plans-dir for coexistence) |

## Component library

All extraction logic lives in `lib/`. Do not duplicate logic here — read the lib file and follow it.

| Phase | Read this lib file |
|-------|--------------------|
| 1 | `lib/role-detector.md` |
| 2a | `lib/gap-extractor.md` |
| 2b | `lib/spec-extractor.md` |
| 2c | `lib/prd-extractor.md` |
| 3 | `lib/cross-validator.md` |
