# plan-parser — Shared library for writing-plans-format md

Used by:
- `skill-0-ingest` (spec-extractor.md, Phase 0 plan-format detection) — produces `task_hints.tasks[]`
- `skill-8-batch-dispatch` (Step 4a) — references the parsed structure when constructing the plan-passthrough prompt block (the prompt itself just points the subagent at the plan file; the parser confirms the plan is well-formed before dispatch)
- `skill-9-task-status` (Step 1.5) — counts checkboxes across the whole plan file for per-plan progress
- `skill-10-smoke-test` (Step 2.5) — extracts per-task file declarations for the plan-vs-actual diff

This library does NOT do any I/O of its own; it returns parsed data structures that callers serialize.

## Input contract

A markdown file written in the format produced by `superpowers:writing-plans`. Recognizable by:
- A first-line H1 ending in "Implementation Plan"
- The agentic-workers blockquote citing `superpowers:subagent-driven-development` or `superpowers:executing-plans` (the canonical writing-plans header — see role-detector.md Signal A0)
- One or more `### Task N: <name>` headings (where N is an integer)

## Parsing rules

### Rule 1 — Task discovery

Match any line of the form `### Task N: <task-name>` (regex: `^### Task (\d+):\s*(.+)$`). The captured integer becomes `task_index`; the trailing text becomes `name` (trim trailing whitespace; preserve embedded backticks).

For each match, compute `source_plan_anchor` as the GitHub-flavored slug:
1. Lowercase the full heading text `Task N: <name>` (without the leading `### `).
2. Replace any whitespace run with a single `-`.
3. Strip every character that is not in `[a-z0-9-]` (this drops colons, parentheses, brackets, dots, apostrophes, backticks, etc.).
4. Collapse any `-{2,}` to `-`. Strip leading/trailing `-`.

Examples:
| Heading | Slug |
|---|---|
| `### Task 1: Create package skeleton` | `task-1-create-package-skeleton` |
| `### Task 3: Add CR + CRAudit dataclasses + status/source enums` | `task-3-add-cr--craudit-dataclasses--statussource-enums` |
| `### Task 7: \`POST /api/crs\` endpoint` | `task-7-post-apicrs-endpoint` |

(Note: GitHub's slugger actually preserves consecutive `-` chars rather than collapsing them in some cases. This library collapses them — both forms work as in-file deep-links; the parser's output is the canonical reference.)

### Rule 2 — Task body boundaries

A task body starts on the line AFTER its `### Task N:` heading and ends at the line BEFORE the next `### Task M:` heading, the next `## ` heading, or end-of-file (whichever comes first).

Do NOT include the next-task heading or any horizontal rule (`---`) immediately before the next task in the body.

### Rule 3 — Files sub-section per task

Within a task body, locate the literal `**Files:**` heading (case-sensitive). The block extends until the first blank line followed by `- [ ] **Step` OR `### Task` OR `## ` (whichever comes first).

Parse the block as a bullet list. Each bullet matches the regex:

```
^- (Create|Modify|Test|Delete):\s+`([^`]+)`(?:\s+at\s+lines?\s+\d+(?:-\d+)?)?(?:\s+—\s+.*)?$
```

(Case-insensitive on the verb.)

Group by the leading verb (lower-cased): `create` / `modify` / `test` / `delete`. The path is the backtick-wrapped capture. Drop any ` at line N` or ` at lines N-M` suffix and any trailing em-dash comment.

If a task has no `**Files:**` block, set `files: {create: [], modify: [], test: [], delete: []}`.

### Rule 4 — Steps per task

Match lines `- [ ] **Step N:** <description>` OR `- [x] **Step N:** <description>` (regex: `^- \[[ x]\] \*\*Step (\d+):\*\*\s*(.+)$`). The checkbox state is NOT recorded by this rule — Rule 4 only extracts step metadata. (Checkbox state is read by skill-9 for progress; it does its own counting.)

Capture:
- `step_index`: the integer N
- `description`: the text after `**Step N:**` on the same line, trimmed (multi-line descriptions are NOT supported; only the first line is captured)

For each step body (text between this step's bullet and the next `- [ ] **Step ` / `- [x] **Step `, or `### Task `, or `## ` heading — whichever comes first):
- `has_code_block`: true if any line in the body begins with ` ```` ` (three backticks, optionally followed by a language identifier)
- `has_run_command`: true if any line in the body matches `^Run:\s` (literal "Run:" prefix at start of a line)

### Rule 5 — Idempotence under re-parse

Running plan-parser twice on the same file must produce byte-identical output. No timestamps, no per-run identifiers, no hash-dependent ordering. Tasks appear in document order; steps within a task appear in document order; files within `create`/`modify`/`test`/`delete` lists appear in document order.

### Rule 6 — Refusal on malformed input

If the file does NOT match the input contract (no H1 ending in "Implementation Plan" AND no `### Task N:` heading found within the first 200 lines), refuse and return:

```yaml
result:
  error: "not-a-plan"
  warnings: []
  tasks: []
```

Callers must NOT silently emit a partial `tasks[]` from a non-plan file.

If the file has the H1 but no `### Task N:` headings, return:

```yaml
result:
  error: "plan-without-tasks"
  warnings: ["plan has no '### Task N:' headings; nothing to parse"]
  tasks: []
```

If the file is writing-plans-format but a task lacks a `**Files:**` block, that's NOT an error — the parser emits the task with empty `files` lists and adds a warning: `"task {N} '{name}' has no **Files:** block"`.

## Output structure

```yaml
tasks:
  - task_index: int
    name: str
    source_plan_path: str       # caller fills this in (parser receives bytes, not path)
    source_plan_anchor: str
    files:
      create: [str]
      modify: [str]
      test: [str]
      delete: [str]
    steps:
      - step_index: int
        description: str
        has_code_block: bool
        has_run_command: bool
```

Top-level wrapper for the caller:

```yaml
result:
  error: null | "not-a-plan" | "plan-without-tasks"
  warnings: [str]
  tasks: [...]
```

## Verification (acceptance test)

Apply this library to `skills/skill-0-ingest/tests/fixtures/plan-passthrough/admin-v2-p1-cr-data-layer.md`. The output must satisfy:

- `result.error` is `null`
- `len(result.tasks) == 14` (matches the 14 `### Task N:` headings in the fixture)
- `result.tasks[i].task_index == i+1` for all `i` (sequential integers)
- Every entry has a non-empty `source_plan_anchor` (per Rule 1)
- Every entry has at least one of `files.create`, `files.modify` non-empty (the p1 fixture declares files in every task)
- Total `sum(len(t.steps) for t in result.tasks) == 90` (matches the 90 `- [ ] **Step ` checkboxes in the fixture)

The exact expected `tasks[]` payload lives at `skills/skill-0-ingest/tests/expected/admin-v2-p1.task-hints.yaml` (after the caller has filled in `source_plan_path` = `docs/superpowers/plans/2026-05-11-admin-v2-p1-cr-data-layer.md`).

## Used by (cross-references)

- `skill-0-ingest/lib/spec-extractor.md` — Phase 0 plan-format detection: when `detected_role: plan` AND the writing-plans signature is present, delegates to this library and SKIPS the legacy steps/file_changes extraction (Steps 1-7 of spec-extractor).
- `skill-0-ingest/lib/role-detector.md` — Signal A0 (writing-plans header) — recognizes the same signature so role classification and parser delegation stay in sync.
- `skill-8-batch-dispatch/SKILL.md` — Step 4a (Plan-Passthrough block construction): the parser confirms the plan is well-formed before the subagent is dispatched. The subagent itself reads the plan via `superpowers:subagent-driven-development` / `executing-plans`, not via this parser.
- `skill-9-task-status/SKILL.md` — Step 1.5 (per-plan progress): the parser provides the task and step counts; skill-9 layers a separate `- [x]` count across the whole file for progress.
- `skill-10-smoke-test/SKILL.md` — Step 2.5 (plan-vs-actual): reads per-plan-task `files.create` and `files.modify` directly from this parser's output (or from `task-hints.yaml` if it's still in sync).
