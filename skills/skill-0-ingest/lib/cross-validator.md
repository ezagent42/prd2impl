# cross-validator — Phase 3 of skill-0-ingest

Validate the in-memory `gap_analysis`, `task_hints`, and `prd_structure` objects against
five cross-cutting rules before any files are written to disk.

Fatal violations abort Phase 4 (no files written).
Non-fatal warnings are reported and require user confirmation to proceed.

## Input

- `gap_analysis` dict (from gap-extractor; may be empty if no gap MDs provided)
- `task_hints` dict (from spec-extractor; may be empty/null if no spec MDs provided)
- `prd_structure` dict (from prd-extractor; may be empty if no prd/plan/user-stories MDs provided)
- Source MD file contents (for anchor verification)

## Five validation rules

---

### Rule 1 — Every file_change must relate to a gap

**Check**: For each `task_hints.file_changes` entry where `related_gap_refs == []`:
1. Look at the `source_anchor` heading in the original spec MD.
2. In the text under that heading, search for any string matching:
   - `GAP-\d+` pattern
   - Any known `source_id` value from `gap_analysis.gaps` (e.g. `A-①`, `B-⑦`)
3. If match found → backfill `related_gap_refs` with the canonical GAP-NNN.
4. If no match found → emit **Warning**: `"orphan spec change: {path} has no related gap"`

**Severity**: Warning (non-fatal)
**Handling**: Backfill if possible; flag if not. User can proceed.

---

### Rule 2 — Every P0 gap must be covered by at least one spec file_change

**Check**: For each gap where `priority == P0`:
1. Search `task_hints.file_changes[*].related_gap_refs` for this gap's `id`.
2. If not found → emit **Warning**: `"P0 gap with no implementation plan: {gap.id} ({gap.description})"`

**Severity**: Warning (non-fatal)
**Handling**: User may proceed; warning serves as reminder to add spec coverage.

---

### Rule 3 — implementation_steps.touches_files ⊆ file_changes.path

**Check**: For each `task_hints.implementation_steps` entry:
1. For each `path` in `touches_files`:
2. Check if `path` appears in `task_hints.file_changes[*].path` (exact string match).
3. If not found → emit **Warning**: `"step {N} references undeclared file: {path}"`

**Severity**: Warning (non-fatal)
**Handling**: The referenced file is not in the spec's file-change list. May be an oversight or may be intentional (touching a file without formally declaring it). User proceeds.

---

### Rule 4 — non_goals must not contradict file_changes (FATAL)

**Check**: For each `task_hints.non_goals` string:
1. Tokenize the non_goal into keywords (split on spaces; strip punctuation; drop stop words).
2. For each `task_hints.file_changes` entry:
   - If `file_changes.path` contains any keyword from the non_goal → **Fatal conflict**.
   - Example: non_goal = "tokens.css unchanged"; keyword = "tokens.css"; file_change path = `src/tokens.css` → conflict.
3. If conflict found → emit **Fatal**: `"non_goal conflicts with file_change: '{non_goal}' vs '{path}'"`

**Severity**: Fatal
**Handling**: Abort Phase 4. Print all conflicting pairs. User must fix the spec MD and re-run `/ingest-docs`.

---

### Rule 5 — All source_anchor values must resolve to real headings

**Check**: For each `source_anchor` value in gap_analysis.gaps, task_hints.file_changes, task_hints.implementation_steps:
1. Re-read the corresponding source MD file.
2. Compute GitHub-style heading slugs for all headings in the file.
3. Check if the `source_anchor` matches any slug.
4. If not found → emit **Warning**: `"dead anchor: '{source_anchor}' in {source_file} (heading may have been renamed)"`

**Severity**: Warning (non-fatal)
**Handling**: Usually means the source MD was edited after ingest. Traceability is broken but data is still usable. User proceeds.

**GitHub slug algorithm**: lowercase, replace spaces with `-`, remove characters that are not alphanumeric or `-`.

---

## Execution order

1. Run Rule 4 first (fatal check). If any fatal → abort immediately; no files written.
2. Run Rules 1, 2, 3, 5 (warning checks). Collect all warnings.
3. If any warnings → print warning table; ask user `y/n` to proceed.
4. If user says `n` → abort (no files written).
5. If user says `y` (or no warnings) → proceed to Phase 4 (write).

## Output format

```
Cross-validation results:
────────────────────────
FATAL (1):
  [FATAL] Rule 4: non_goal conflicts with file_change
    non_goal : "tokens.css unchanged"
    file_change: src/tokens.css (modify)
    → Fix the spec MD and re-run /ingest-docs

Warnings (3):
  [WARN]  Rule 1: orphan spec change: src/App.tsx has no related gap
  [WARN]  Rule 2: P0 gap with no implementation plan: GAP-003 (一键发布 API 未实现)
  [WARN]  Rule 5: dead anchor: 'a--p0-a-missing-register-step' in clear-gap.md

Proceed with warnings? (y/n):
```

## Fixtures (one per rule)

Five fixture sets live in `tests/fixtures/cross-validation/`:

| Fixture dir | Trips rule | Expected outcome |
|---|---|---|
| `rule1-orphan-spec-change/` | Rule 1 | 1 warning: orphan file_change |
| `rule2-p0-uncovered/` | Rule 2 | 1 warning: P0 gap with no spec coverage |
| `rule3-undeclared-file/` | Rule 3 | 1 warning: step references undeclared file |
| `rule4-nongoal-conflict/` | Rule 4 | 1 fatal: non_goal contradicts file_change |
| `rule5-dead-anchor/` | Rule 5 | 1 warning: dead anchor |

Each fixture dir contains minimal in-memory YAML snapshots (not full MDs) named:
- `gap_analysis.yaml`
- `task_hints.yaml`
- `prd_structure.yaml`
- `expected-output.txt`

Cross-validator reads these YAMLs directly (bypassing extraction phases) for unit-level testing.

## Design-spec warnings (v0.2.1+)

When Phase 2b processes a file with `detected_role: design-spec`, emit these warnings
if the corresponding sections were not found:

| Condition | Warning message (info level) |
|---|---|
| §Design section missing | `design-spec <file>: no §Design/§Architecture section, modules[] empty` |
| §Requirements section missing | `design-spec <file>: no §Behavioral Requirements section, nfrs[] empty` |
| §Known Limitations section missing | `design-spec <file>: no §Known Limitations section, constraints[] empty` |
| §Design present but no `###` sub-headings | `design-spec <file>: §Design has no sub-headings, treated as single coarse module (MOD-01.coarse=true)` |
| `prd_structure` fully empty after extraction | `design-spec <file>: produced no prd-structure content, prd-structure.yaml skipped for this file` |
| Both `prd_structure` and `task_hints` empty | `design-spec <file>: produced no output — file content had no recognized sections. Check file categorization (role-detector may have misclassified).` |

These warnings are **info-level, non-blocking**. They appear in the Phase 3 human review
table so the user can decide whether the extraction was good enough or the source doc
needs editing before re-running /ingest-docs.
