# Plan-Passthrough × TDD-Step Propagation × Plan-Grounded Smoke-Test Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make prd2impl natively consume writing-plans-format markdown plans without YAML round-trip loss (#1 plan-passthrough), propagate per-step TDD discipline verbatim into batch-dispatch subagent prompts (#2 TDD-step 真传), and verify milestone deliverables against the plan-declared File Structure (#3 plan-grounded smoke-test).

**Architecture:** Introduce one shared library `skills/skill-0-ingest/lib/plan-parser.md` that extracts the `{Task → Steps → Files}` hierarchy from a writing-plans-format md. Extend `task-hints.yaml` schema with a `tasks[]` array carrying `source_plan_path` + `source_plan_anchor` per plan-task (the rich data lives in task-hints.yaml). Skill-3 collapses by `source_plan_path` — one prd2impl task per plan FILE (Option B coarse-grained mapping), aggregating files-touched across all plan-tasks in that file. Skill-5 delegates the WHOLE plan to `superpowers:executing-plans` (no slicing — executing-plans is a no-arg loader; the slicing is at the plan-file boundary). Skill-8's subagent prompt for plan-passthrough tasks instructs the agent to invoke executing-plans/subagent-driven-development on the source plan rather than improvising. Skill-9 counts checked boxes across the whole plan file. Skill-10 reads the rich per-plan-task data from task-hints.yaml for granular plan-vs-actual file diffs in the gate report. All changes are backward-compatible — tasks without `source_plan_path` continue through existing paths.

**Granularity decision (Option B, coarse-grained):** After self-review found that `superpowers:executing-plans` v5.1.0 takes no args (it loads one plan and runs all tasks), the cleanest mapping is one prd2impl task per plan FILE — not one per plan-task. The 8 admin-v2 plans (p1, p2, p3, p4a, p4b, p5, p6a, p6b) become 8 prd2impl tasks (T1, T2, T3, T4A, T4B, T5, T6A, T6B). batch-dispatch parallelizes across plan files; intra-plan ordering is handled by executing-plans' built-in sequential discipline. A finer-grained Option A (1 plan-task → 1 prd2impl task, with plan-slicing) is explicitly out of scope for this plan — revisit if needed after dogfooding.

**Design Rationale (folded from spec):**
- The 8 admin-v2 plan files at `AutoService/docs/superpowers/plans/2026-05-11-admin-v2-*.md` are already in writing-plans format with `### Task N: <name>` headings, `**Files:**` sub-sections, and `- [ ] **Step M:**` checkboxes. The current skill-0 spec-extractor flattens this into `implementation_steps[]` keyed by step number alone, losing the Task↔Steps↔Files hierarchy. Reconstructing it on the consumer side is fragile.
- The fix is to model the hierarchy in the schema, retain the source path/anchor, and have downstream skills (start-task, batch-dispatch, smoke-test) read the original md when richer detail is needed. This converts the YAML from "lossy compression" to "index + pointer."
- This is purely additive: when ingested docs are not plans (gap analyses, design specs, PRDs), the new fields stay absent and every skill falls back to its 0.4.0 behavior.

**Tech Stack:**
- Markdown-based skill specs (no compiled code in prd2impl — skills are read by Claude Code)
- YAML schemas (JSON-Schema flavored)
- Test fixtures: input md + expected yaml, manually verified by reading skill behavior
- Reuses existing libs: [skills/skill-0-ingest/lib/spec-extractor.md](../../skills/skill-0-ingest/lib/spec-extractor.md), [skills/skill-0-ingest/lib/role-detector.md](../../skills/skill-0-ingest/lib/role-detector.md), [skills/skill-0-ingest/lib/cross-validator.md](../../skills/skill-0-ingest/lib/cross-validator.md)

**File Structure:**

```
# New
skills/skill-0-ingest/lib/plan-parser.md
skills/skill-0-ingest/tests/fixtures/plan-passthrough/
  admin-v2-p1-cr-data-layer.md         ← copy of an actual admin-v2 plan (canonical fixture)
skills/skill-0-ingest/tests/expected/
  admin-v2-p1.task-hints.yaml          ← expected ingestion output
  admin-v2-p1.tasks.yaml.fragment      ← expected task-gen fragment for one task

# Modified
skills/skill-0-ingest/schemas/task-hints.schema.yaml
skills/skill-0-ingest/schemas/task-hints.example.yaml
skills/skill-0-ingest/lib/spec-extractor.md
skills/skill-0-ingest/lib/role-detector.md         ← raise role=plan confidence on writing-plans header line
skills/skill-0-ingest/SKILL.md
skills/skill-3-task-gen/SKILL.md
skills/skill-5-start-task/SKILL.md
skills/skill-8-batch-dispatch/SKILL.md
skills/skill-9-task-status/SKILL.md
skills/skill-10-smoke-test/SKILL.md
CHANGELOG.md
```

**Discipline:** Because prd2impl skill files are markdown specs (not compiled code), the conventional red-green-refactor TDD rhythm becomes "fixture-first, expected-output-second, spec-update-third, manual-verify-fourth, commit-fifth." Every spec change must show the exact before/after text. Every behavior change must be backed by a fixture entry in `tests/fixtures/plan-passthrough/` + a matching `tests/expected/` file. Commits are per-task.

---

## Phase A — Shared parser foundation

### Task 1: Add the canonical test fixture (the admin-v2 p1 plan)

**Files:**
- Create: `skills/skill-0-ingest/tests/fixtures/plan-passthrough/admin-v2-p1-cr-data-layer.md`

- [ ] **Step 1: Copy the AutoService admin-v2 p1 plan as the canonical fixture**

The fixture lives in a different repo. Capture its current shape verbatim so future spec changes stay grounded in a real plan.

```bash
mkdir -p skills/skill-0-ingest/tests/fixtures/plan-passthrough
cp "D:/Work/h2os.cloud/AutoService-dev-a/docs/superpowers/plans/2026-05-11-admin-v2-p1-cr-data-layer.md" \
   skills/skill-0-ingest/tests/fixtures/plan-passthrough/admin-v2-p1-cr-data-layer.md
```

Expected: file exists, ~1000 lines, contains `### Task 1:`, `**Files:**`, `- [ ] **Step 1:`.

- [ ] **Step 2: Sanity-check the fixture structure**

```bash
grep -c "^### Task " skills/skill-0-ingest/tests/fixtures/plan-passthrough/admin-v2-p1-cr-data-layer.md
grep -c "^\*\*Files:\*\*" skills/skill-0-ingest/tests/fixtures/plan-passthrough/admin-v2-p1-cr-data-layer.md
grep -c "^- \[ \] \*\*Step " skills/skill-0-ingest/tests/fixtures/plan-passthrough/admin-v2-p1-cr-data-layer.md
```

Expected: Task count ≥ 8, Files count ≥ 8, Step count ≥ 30. Record the exact counts; they're used as assertions in Task 6.

- [ ] **Step 3: Commit**

```bash
git add skills/skill-0-ingest/tests/fixtures/plan-passthrough/admin-v2-p1-cr-data-layer.md
git commit -m "test(skill-0): add canonical plan-passthrough fixture (admin-v2 p1)"
```

---

### Task 2: Extend `task-hints.schema.yaml` with `tasks[]` array

**Files:**
- Modify: `skills/skill-0-ingest/schemas/task-hints.schema.yaml`

- [ ] **Step 1: Open the schema and locate the `properties:` block of `task_hints`**

Read current lines 17-120 of `skills/skill-0-ingest/schemas/task-hints.schema.yaml`. We are adding one new top-level property `tasks` alongside the existing `source_files`, `file_changes`, `implementation_steps`, `test_strategy`, `non_goals`, `risks`.

- [ ] **Step 2: Append the new `tasks` property to the schema**

Insert this block immediately after the `risks` property definition, but still inside the `task_hints.properties` map. The block:

```yaml
      tasks:
        type: array
        description: >
          Plan-task hierarchy preserved verbatim from a role=plan source MD.
          Each entry corresponds to one '### Task N: <name>' heading in the
          source plan. Present only when source role is 'plan'; absent for
          spec/prd/gap/user-stories roles.

          Downstream skill-3 (Option B coarse-grained) groups entries by
          source_plan_path and emits ONE prd2impl task per unique plan file,
          aggregating files-touched across all plan-tasks in the file.
          The rich per-plan-task data stays in task-hints.yaml — skill-9 and
          skill-10 read it directly for per-plan-task progress and file diffs.
        items:
          type: object
          required: [task_index, name, source_plan_path, source_plan_anchor]
          properties:
            task_index:
              type: integer
              description: "1-based ordinal as it appears in the plan."
            name:
              type: string
              description: "Task title from the '### Task N: <name>' heading."
            source_plan_path:
              type: string
              description: "Repo-relative path to the source plan md."
            source_plan_anchor:
              type: string
              description: >
                Heading slug for the task's '### Task N:' line in the source md
                (GitHub-flavored slug: lowercased, spaces → '-', punctuation
                stripped). Used by downstream skills to deep-link.
            files:
              type: object
              description: "Files declared under the task's **Files:** sub-section."
              properties:
                create: {type: array, items: {type: string}}
                modify: {type: array, items: {type: string}}
                test:   {type: array, items: {type: string}}
                delete: {type: array, items: {type: string}}
            steps:
              type: array
              description: >
                Ordered checkbox steps under this task. Verbatim copy of each
                '- [ ] **Step M:** ...' line; downstream skill-8 embeds these
                into subagent prompts.
              items:
                type: object
                required: [step_index, description]
                properties:
                  step_index: {type: integer}
                  description:
                    type: string
                    description: "Step heading text (after 'Step M:')."
                  has_code_block:
                    type: boolean
                    description: "True if the step body contains a fenced code block."
                  has_run_command:
                    type: boolean
                    description: "True if the step body contains a 'Run: ...' line."
```

Use the Edit tool to insert this block. Make sure indentation is exactly 6 spaces (matching the sibling `risks:` property). Do NOT touch any other property.

- [ ] **Step 3: Validate the YAML parses**

```bash
python3 -c "import yaml; yaml.safe_load(open('skills/skill-0-ingest/schemas/task-hints.schema.yaml'))" && echo OK
```

Expected: prints `OK`. If it errors, fix indentation.

- [ ] **Step 4: Commit**

```bash
git add skills/skill-0-ingest/schemas/task-hints.schema.yaml
git commit -m "feat(skill-0): add tasks[] field to task-hints schema for plan-passthrough"
```

---

### Task 3: Refresh `task-hints.example.yaml` with a `tasks[]` example

**Files:**
- Modify: `skills/skill-0-ingest/schemas/task-hints.example.yaml`

- [ ] **Step 1: Append a `tasks:` section after the existing `risks:` block**

Use Edit to append (do NOT replace existing content — example file shows multiple roles). Add at end of file:

```yaml

  # tasks[]: present only when source role is 'plan' (see schema).
  # The example below is derived from AutoService/docs/superpowers/plans/2026-05-11-admin-v2-p1-cr-data-layer.md
  tasks:
    - task_index: 1
      name: "Create change_request package skeleton + audit.db schema"
      source_plan_path: "docs/superpowers/plans/2026-05-11-admin-v2-p1-cr-data-layer.md"
      source_plan_anchor: "task-1-create-change_request-package-skeleton--auditdb-schema"
      files:
        create:
          - "autoservice/change_request/__init__.py"
          - "autoservice/change_request/schema.py"
          - "tests/change_request/__init__.py"
          - "tests/change_request/conftest.py"
          - "tests/change_request/test_schema.py"
        modify: []
        test:
          - "tests/change_request/test_schema.py"
      steps:
        - step_index: 1
          description: "Create the conftest.py fixture (used by all later tasks)"
          has_code_block: true
          has_run_command: false
        - step_index: 2
          description: "Write the failing test for schema creation"
          has_code_block: true
          has_run_command: false
        - step_index: 3
          description: "Run test to verify it fails"
          has_code_block: false
          has_run_command: true

    - task_index: 2
      name: "Create CR + CRAudit dataclasses + status/source enums"
      source_plan_path: "docs/superpowers/plans/2026-05-11-admin-v2-p1-cr-data-layer.md"
      source_plan_anchor: "task-2-create-cr--craudit-dataclasses--statussource-enums"
      files:
        create:
          - "autoservice/change_request/models.py"
          - "tests/change_request/test_models.py"
        modify: []
        test:
          - "tests/change_request/test_models.py"
      steps:
        - step_index: 1
          description: "Write failing test for CR dataclass"
          has_code_block: true
          has_run_command: false
```

- [ ] **Step 2: Validate the YAML parses**

```bash
python3 -c "import yaml; yaml.safe_load(open('skills/skill-0-ingest/schemas/task-hints.example.yaml'))" && echo OK
```

Expected: `OK`.

- [ ] **Step 3: Commit**

```bash
git add skills/skill-0-ingest/schemas/task-hints.example.yaml
git commit -m "docs(skill-0): add tasks[] example to task-hints.example.yaml"
```

---

### Task 4: Create the shared `lib/plan-parser.md` library

**Files:**
- Create: `skills/skill-0-ingest/lib/plan-parser.md`

- [ ] **Step 1: Write the full lib spec**

Create `skills/skill-0-ingest/lib/plan-parser.md` with this content:

````markdown
# plan-parser — Shared library for writing-plans-format md

Used by:
- `skill-0-ingest` (spec-extractor.md, Phase 2b plan branch) — produces `task_hints.tasks[]`
- `skill-8-batch-dispatch` (Step 4 prompt construction) — extracts per-step text for TDD propagation
- `skill-10-smoke-test` (Step 2.5 plan-vs-actual) — extracts per-task file declarations

This library does NOT do any I/O of its own; it returns parsed data structures that callers serialize.

## Input contract

A markdown file written in the format produced by `superpowers:writing-plans`. Recognizable by:
- A first-line H1 ending in "Implementation Plan"
- The agentic-workers blockquote citing `superpowers:subagent-driven-development` or `superpowers:executing-plans`
- One or more `### Task N: <name>` headings (where N is an integer)

## Parsing rules

### Rule 1 — Task discovery

Match any line of the form `### Task N: <task-name>` (regex: `^### Task (\d+):\s*(.+)$`). The captured integer becomes `task_index`; the trailing text becomes `name` (trim trailing whitespace).

For each match, compute `source_plan_anchor` as the GitHub-flavored slug:
1. Lowercase the full heading text `Task N: <name>` (without the leading `### `).
2. Replace any whitespace run with a single `-`.
3. Strip every character that is not in `[a-z0-9-]` (this drops colons, parentheses, brackets, dots, apostrophes, etc.).
4. Collapse any `-{2,}` to `-`. Strip leading/trailing `-`.

Examples:
| Heading | Slug |
|---|---|
| `### Task 1: Create package skeleton` | `task-1-create-package-skeleton` |
| `### Task 3: Add CR + CRAudit dataclasses + status/source enums` | `task-3-add-cr--craudit-dataclasses--statussource-enums` |
| `### Task 7: \`POST /api/crs\` endpoint` | `task-7-post-apicrs-endpoint` |

### Rule 2 — Task body boundaries

A task body starts on the line AFTER its `### Task N:` heading and ends at the line BEFORE the next `### Task M:` heading or `## ` heading (whichever comes first), or end-of-file.

Do NOT include the next-task heading or any horizontal rule (`---`) immediately before the next task.

### Rule 3 — Files sub-section per task

Within a task body, locate `**Files:**` (literal, case-sensitive). The block extends until the next blank line followed by `- [ ] **Step`, or `### Task`, or `## `.

Parse the block as a bullet list. Each bullet matches:

```
- (Create|Modify|Test|Delete): `<path>`(?: at lines? \d+(?:-\d+)?)?(?: — .*)?
```

Group by the leading verb (case-insensitive: `create` / `modify` / `test` / `delete`). The path is the backtick-wrapped string. Drop any `:line` or `:lines N-M` suffix and any trailing em-dash comment.

If a task has no `**Files:**` block, set `files: {create: [], modify: [], test: [], delete: []}`.

### Rule 4 — Steps per task

Match lines `- [ ] **Step N:** <description>` (the description ends at the line break — multi-line descriptions are NOT supported; only the first line is captured). Capture:
- `step_index`: the integer N
- `description`: the text after `**Step N:**`, trimmed

For each step body (text between this step's bullet and the next `- [ ] **Step`, or `### Task`, or `## `):
- `has_code_block`: true if any line begins with ` ```` ` (three backticks, optionally followed by a language identifier)
- `has_run_command`: true if any line matches `^Run:\s` (literal "Run:" prefix)

### Rule 5 — Idempotence under re-parse

Running plan-parser twice on the same file must produce byte-identical output. No timestamps, no per-run identifiers, no hash-dependent ordering. Tasks appear in document order; steps within a task appear in document order; files within `create`/`modify`/`test`/`delete` appear in document order.

### Rule 6 — Refusal on malformed input

If the file does NOT match the input contract (no H1 ending in "Implementation Plan" AND no `### Task N:` heading found within the first 200 lines), refuse and return `{error: "not-a-plan", tasks: []}`. Callers must NOT silently emit a partial `tasks[]`.

If the file has the H1 but no `### Task N:` headings, return `{error: "plan-without-tasks", tasks: []}` plus a warning string the caller can surface to the user.

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

## Verification

Apply this library to `skills/skill-0-ingest/tests/fixtures/plan-passthrough/admin-v2-p1-cr-data-layer.md`. The output must match `skills/skill-0-ingest/tests/expected/admin-v2-p1.task-hints.yaml` byte-for-byte under the `tasks:` key (after the caller has filled in `source_plan_path`).

## Used by (cross-references)

- `skill-0-ingest/lib/spec-extractor.md` — Phase 2b, when `detected_role: plan`, replaces the legacy implementation_steps extraction.
- `skill-8-batch-dispatch/SKILL.md` — Step 4, reads the source md fresh on dispatch (NOT the cached YAML) and uses Rule 4 to extract verbatim step text for prompt embedding.
- `skill-10-smoke-test/SKILL.md` — Step 2.5, uses Rule 3 to extract per-task files for plan-vs-actual diff.
````

- [ ] **Step 2: Verify the file was written**

```bash
wc -l skills/skill-0-ingest/lib/plan-parser.md
grep -c "^### Rule" skills/skill-0-ingest/lib/plan-parser.md
```

Expected: line count > 100, Rule count == 6.

- [ ] **Step 3: Commit**

```bash
git add skills/skill-0-ingest/lib/plan-parser.md
git commit -m "feat(skill-0): add plan-parser.md shared library for writing-plans-format md"
```

---

### Task 5: Add the expected-output fixture (target for plan-parser)

**Files:**
- Create: `skills/skill-0-ingest/tests/expected/admin-v2-p1.task-hints.yaml`

- [ ] **Step 1: Draft the expected output by reading the fixture md**

Read `skills/skill-0-ingest/tests/fixtures/plan-passthrough/admin-v2-p1-cr-data-layer.md`. For each `### Task N:` heading, capture:
1. `task_index` (the N)
2. `name` (the heading text after the colon)
3. `source_plan_anchor` (computed per plan-parser Rule 1)
4. `files` from the `**Files:**` block per Rule 3
5. `steps` from each `- [ ] **Step M:**` per Rule 4

Write the result to `skills/skill-0-ingest/tests/expected/admin-v2-p1.task-hints.yaml`:

```yaml
# Expected output of plan-parser applied to
# tests/fixtures/plan-passthrough/admin-v2-p1-cr-data-layer.md
# Used as the canonical assertion when skill-0 ingests a plan file.

task_hints:
  source_files:
    - "docs/superpowers/plans/2026-05-11-admin-v2-p1-cr-data-layer.md"
  source_type: "ingested"

  tasks:
    - task_index: 1
      name: "Create `change_request` package skeleton + `audit.db` schema"
      source_plan_path: "docs/superpowers/plans/2026-05-11-admin-v2-p1-cr-data-layer.md"
      source_plan_anchor: "task-1-create-change_request-package-skeleton--auditdb-schema"
      files:
        create:
          - "autoservice/change_request/__init__.py"
          - "autoservice/change_request/schema.py"
          - "tests/change_request/__init__.py"
          - "tests/change_request/conftest.py"
          - "tests/change_request/test_schema.py"
        modify: []
        test: []
        delete: []
      steps:
        # (Fill in every step from the fixture in document order.
        # If the fixture has 5 steps under Task 1, list all 5 here.)
        - step_index: 1
          description: "Create the conftest.py fixture (used by all later tasks)"
          has_code_block: true
          has_run_command: false
        # ... continue for every step ...

    # Continue for every Task N in the fixture.
```

The exact full expected file must enumerate every task and every step. Use the fixture as authoritative.

- [ ] **Step 2: Validate the YAML parses**

```bash
python3 -c "import yaml; yaml.safe_load(open('skills/skill-0-ingest/tests/expected/admin-v2-p1.task-hints.yaml'))" && echo OK
```

- [ ] **Step 3: Sanity-check counts match the fixture**

```bash
python3 - <<'PY'
import yaml
data = yaml.safe_load(open('skills/skill-0-ingest/tests/expected/admin-v2-p1.task-hints.yaml'))
tasks = data['task_hints']['tasks']
print(f"tasks: {len(tasks)}")
print(f"total steps: {sum(len(t.get('steps', [])) for t in tasks)}")
print(f"total create files: {sum(len(t.get('files', {}).get('create', [])) for t in tasks)}")
PY
```

Cross-reference with the fixture counts recorded in Task 1 Step 2. Tasks must match; total steps must match; total create files must match.

- [ ] **Step 4: Commit**

```bash
git add skills/skill-0-ingest/tests/expected/admin-v2-p1.task-hints.yaml
git commit -m "test(skill-0): add expected task-hints.yaml for plan-passthrough fixture"
```

---

## Phase B — Ingestion wiring (skill-0)

### Task 6: Update `role-detector.md` to confidently classify writing-plans-format md as `role=plan`

**Files:**
- Modify: `skills/skill-0-ingest/lib/role-detector.md`

- [ ] **Step 1: Read the current role-detector spec**

```bash
wc -l skills/skill-0-ingest/lib/role-detector.md
grep -n "^##" skills/skill-0-ingest/lib/role-detector.md
```

Locate the section that defines the heuristic for `role=plan`. We want to ADD a high-confidence signal: presence of the writing-plans agentic-workers blockquote.

- [ ] **Step 2: Add a high-confidence signal for writing-plans format**

Use Edit to add a new bullet under the `role=plan` heuristic table or signal list. The exact insertion depends on the file's current structure — read the file first, then insert this bullet at the top of the `plan` signal list (highest priority, since it's the most reliable):

```markdown
- **Signal A0 (highest confidence — +60 score)**: file contains the exact substring `REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development` or `REQUIRED SUB-SKILL: Use superpowers:executing-plans` within the first 30 lines. This is the canonical writing-plans header. Files matching this signal MUST be classified as `role=plan` regardless of other signals; downstream uses plan-parser (see `lib/plan-parser.md`) instead of the legacy heuristic extractor.
```

If the file uses a different signal-scoring scheme (numeric weights, regex table, etc.), adapt the wording but keep the spirit: writing-plans-format = high confidence plan.

- [ ] **Step 3: Verify the file still parses as valid markdown**

```bash
head -5 skills/skill-0-ingest/lib/role-detector.md
grep -c "writing-plans" skills/skill-0-ingest/lib/role-detector.md
```

Expected: grep returns >= 1.

- [ ] **Step 4: Commit**

```bash
git add skills/skill-0-ingest/lib/role-detector.md
git commit -m "feat(skill-0): role-detector recognizes writing-plans-format md with high confidence"
```

---

### Task 7: Wire `spec-extractor.md` to delegate to plan-parser when role=plan

**Files:**
- Modify: `skills/skill-0-ingest/lib/spec-extractor.md`

- [ ] **Step 1: Locate the section in spec-extractor that handles `role: plan`**

Currently `spec-extractor.md` extracts `implementation_steps` from a generic spec format. Per `skill-0-ingest/SKILL.md` Phase 2b (lines 89-93), when `detected_role: plan`, the SKILL.md says "Read `lib/spec-extractor.md` for steps extraction only". We need to add an upstream branch: if the file is writing-plans-format, use plan-parser INSTEAD of the legacy implementation_steps logic.

Read the current spec-extractor.md to locate the right section.

- [ ] **Step 2: Add a "Phase 0 — Plan-format detection" section at the top of the extraction flow**

Use Edit to insert this section as the very first content under the top-level extraction heading (right after the input-contract description, before "Step 1 — Locate section anchors"):

```markdown
## Phase 0 — Plan-format detection (role=plan only)

**Triggers when**: the calling skill (skill-0-ingest Phase 2b plan branch) passes in a file with `detected_role: plan`.

**Step 0.1**: Check whether the file is writing-plans-format. Scan the first 30 lines for the literal substring `REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development` OR `REQUIRED SUB-SKILL: Use superpowers:executing-plans`.

**Step 0.2** (match): Delegate to `lib/plan-parser.md`. Pass the file bytes; receive the parsed `tasks[]` list. Set `task_hints.tasks` = the parsed list, populate `source_plan_path` on each entry (the parser leaves it null — caller fills it in), and SKIP the rest of this file's extraction logic (Steps 1-7 below). Also populate `task_hints.source_type = "ingested"`.

**Step 0.3** (no match): Continue with the legacy flow (Steps 1-7 below) — this preserves backward compatibility with hand-written plan-shaped markdown that does NOT follow writing-plans format.
```

- [ ] **Step 3: Add a cross-reference at the bottom of spec-extractor.md**

Append (use Edit at end-of-file):

```markdown

## Plan-format passthrough

When the caller's `detected_role` is `plan` and Phase 0 above matches, ALL `tasks[]` extraction happens in `lib/plan-parser.md` — this file is a no-op for steps/file_changes. Legacy plans (no writing-plans header) still flow through Steps 1-7.
```

- [ ] **Step 4: Verify the file is well-formed**

```bash
head -30 skills/skill-0-ingest/lib/spec-extractor.md
grep -c "Phase 0 — Plan-format detection" skills/skill-0-ingest/lib/spec-extractor.md
```

Expected: grep returns 1.

- [ ] **Step 5: Commit**

```bash
git add skills/skill-0-ingest/lib/spec-extractor.md
git commit -m "feat(skill-0): spec-extractor delegates to plan-parser for writing-plans-format md"
```

---

### Task 8: Update `skill-0-ingest/SKILL.md` Phase 2b to mention the plan-passthrough branch

**Files:**
- Modify: `skills/skill-0-ingest/SKILL.md`

- [ ] **Step 1: Locate the existing Phase 2b text (lines 89-93)**

Current text (verbatim from SKILL.md lines 89-93):

```markdown
If any files have `detected_role: plan`:
- **Read**: `lib/spec-extractor.md` for steps extraction only (skip file_changes section).
- **Read**: `lib/prd-extractor.md §Extraction: role=plan` for module extraction.
- Merge step data into `task_hints`; merge module data into `prd_structure`.
- Print: `  Extracted {S} steps (plan) + {M} modules from {files}`
```

- [ ] **Step 2: Replace it with the plan-passthrough-aware version**

Use Edit to replace the entire 5-line block above with:

```markdown
If any files have `detected_role: plan`:
- **Read**: `lib/spec-extractor.md` — Phase 0 detects writing-plans format and delegates to `lib/plan-parser.md`. For writing-plans-format md, the output is `task_hints.tasks[]` (Task/Step/Files hierarchy preserved). For legacy plans (no writing-plans header), the legacy step-extraction flow runs.
- **Read**: `lib/prd-extractor.md §Extraction: role=plan` for module extraction.
- For each entry in `task_hints.tasks[]` (when present), populate `source_plan_path` with the input file's repo-relative path.
- Merge step data into `task_hints`; merge module data into `prd_structure`.
- Print, depending on path:
  - writing-plans format: `  Extracted {T} tasks ({S} total steps) (plan-passthrough) + {M} modules from {files}`
  - legacy format: `  Extracted {S} steps (plan-legacy) + {M} modules from {files}`
```

- [ ] **Step 3: Update the Phase 4.1b paragraph about source_type**

The schema validation in Phase 4.2 currently says `task-hints.yaml` begins with `task_hints:`. No change needed there. But ensure the Phase 4.1b extraction-metadata block does NOT incorrectly add an `extraction:` key for `role=plan` — it should only fire for `design-spec`. The existing text (lines 199-201) already says "For source_role in {prd, plan, user-stories}: do NOT add the extraction key". Verify and leave unchanged.

- [ ] **Step 4: Update the diff-summary entity hint in Phase 4.1**

Currently line 158 says:
```
- `task-hints.yaml` → `file_changes` (primary), `steps` / `non_goals` (secondary)
```

Replace with:
```
- `task-hints.yaml` → `file_changes` or `tasks` (primary, whichever is non-empty), `steps` / `non_goals` (secondary). When source role is `plan` and writing-plans format, `tasks` count is primary.
```

- [ ] **Step 5: Verify the SKILL.md still parses and Phase 2b mentions the new flow**

```bash
grep -c "plan-passthrough" skills/skill-0-ingest/SKILL.md
grep -c "lib/plan-parser.md" skills/skill-0-ingest/SKILL.md
```

Expected: each >= 1.

- [ ] **Step 6: Commit**

```bash
git add skills/skill-0-ingest/SKILL.md
git commit -m "docs(skill-0): SKILL.md Phase 2b documents plan-passthrough branch"
```

---

## Phase C — Task generation (skill-3) + execution delegation (skill-5)

### Task 9: Update `skill-3-task-gen/SKILL.md` to emit one task per `tasks[]` entry (1:1 plan-passthrough mapping)

**Files:**
- Modify: `skills/skill-3-task-gen/SKILL.md`

- [ ] **Step 1: Read skill-3-task-gen/SKILL.md to find where it consumes task-hints.yaml**

```bash
wc -l skills/skill-3-task-gen/SKILL.md
grep -n "task-hints" skills/skill-3-task-gen/SKILL.md
grep -n "^##\|^###" skills/skill-3-task-gen/SKILL.md
```

Identify the section that reads `file_changes` and `implementation_steps`. We're adding a sibling code path: when `task_hints.tasks` is present and non-empty, emit one prd2impl task per entry and SKIP the legacy file_changes/steps aggregation.

- [ ] **Step 2: Add a new section "Plan-passthrough mapping" near the start of the task-derivation logic**

Use Edit to insert immediately before the section that currently derives tasks from `file_changes`. Insert this content:

```markdown
## Plan-passthrough mapping (0.4.1+, Option B coarse-grained)

When `task_hints.tasks[]` is present and non-empty, use the plan-file mapping below INSTEAD of the legacy `file_changes` + `implementation_steps` aggregation. The legacy path remains the default for design-spec / hand-written plan ingest.

### When to use

`task_hints.source_type == "ingested"` AND `len(task_hints.tasks) > 0` AND every entry in `task_hints.tasks[]` carries a `source_plan_path`.

### Emission rule — one task per plan FILE

Group `task_hints.tasks[]` by `source_plan_path`. For each unique plan-file group, emit exactly one prd2impl task to `tasks.yaml`:

```yaml
- id: "{auto-assigned, see ID rule below}"
  name: "{plan filename: derive a human name from the title H1, stripping 'Implementation Plan'; fall back to filename stem}"
  type: green                            # default; see type-inference rule
  phase: "{auto from plan filename, see phase rule}"
  module: ""                             # plan itself is the module
  source_plan_path: "{unique plan path for this group}"
  source_plan_task_count: {count of entries in this group}
  source_plan_step_count: {sum of len(steps) across the group}
  deliverables:
    # aggregated across all plan-tasks in the group, de-duplicated by path:
    - path: "{path}"
      change_type: "create | modify"
  verification:
    - "All checkbox steps in {source_plan_path} are checked (executing-plans tick state)"
    - "git diff vs base branch matches the plan's aggregated File Structure (see skill-10-smoke-test Step 2.5)"
  depends_on: []                          # see dependency-inference rule below
```

Note: the prd2impl task does NOT carry `source_plan_anchor` (no anchor — the whole plan is the unit). The per-plan-task richness (each plan-task's anchor, files, steps) stays in `task-hints.yaml` and is read directly by skill-10 / skill-9 when they need it.

### Aggregation rule for deliverables

For each unique `source_plan_path`:
- Union `files.create` across all `tasks[]` entries with that path → become `deliverables[].change_type = create`.
- Union `files.modify` similarly → `change_type = modify`.
- Union `files.test` and merge into the create set if the test path is a new file under `tests/`, else into modify.
- De-duplicate by `path` (if a file appears in both create and modify across different plan-tasks, prefer `create`).

### ID rule

Match the plan filename pattern `\d{4}-\d{2}-\d{2}-(?:[a-z0-9-]+-)?p(\d+)([a-z]?)-.+\.md` to extract the plan-letter:
- `*-p1-*.md` → `T1`
- `*-p2-*.md` → `T2`
- `*-p4a-*.md` → `T4A`
- `*-p4b-*.md` → `T4B`
- `*-p6a-*.md` → `T6A`

If the filename does NOT match the `p\d+[a-z]?` pattern, fall back to `TP{1-based ordinal of plan in input list}` (e.g. `TP3` for the 3rd plan).

### Phase rule

If `project.yaml` defines `phases[]`, match the plan-letter to a phase (e.g. `p1` → phase `P1`). If no match, set `phase: "ingested"`.

### Type-inference rule

Default: `type: green`. The granularity is now plan-level — most plans bundle a mix of green/yellow/red work. Default to green and let the user re-classify in `tasks.yaml` if needed. Exception: if the plan filename or H1 mentions `design`, `policy`, `decision`, `architecture` (e.g. `*-decision.md`, `*-policy.md`), default to `red` — these plans typically front-load design decisions.

### Dependency-inference rule

For each emitted task at plan-letter index `i` (ordered by the digit + letter: p1 < p2 < p3 < p4a < p4b < p5 < p6a < p6b), set `depends_on: ["T{prev-plan-letter}"]` if a prev plan was ingested in the same call. Sequential chaining is the safe default; the user edits `tasks.yaml` afterward for non-linear deps.

Print a hint at end of generation:

```
Cross-plan dependencies inferred sequentially (T2 depends on T1, T3 on T2, ...). Review tasks.yaml depends_on if your plans have non-linear deps.
```

### What is NOT done in plan-passthrough mode

- No `gap-analysis.yaml` cross-referencing (writing-plans format does not carry GAP-NNN refs)
- No NFR mapping (plans encode "how", not "what" — NFRs come from prd-structure)
- No intra-plan parallelism (executing-plans runs plan-tasks sequentially within one plan; cross-plan parallelism still works via batch-dispatch)
- No batch packing (skill-4-plan-schedule does that)
```

- [ ] **Step 3: Update the existing flow to branch on `tasks[]` presence**

Find the line in skill-3-task-gen/SKILL.md that says something like "Read task-hints.yaml" or "Process file_changes". Use Edit to add a branch check at that point:

```markdown
> **Branch**: if the loaded `task-hints.yaml` has `tasks[]` populated, jump to the "Plan-passthrough mapping" section above and skip the rest of this section. Otherwise, continue with the legacy file_changes/steps flow.
```

- [ ] **Step 4: Verify**

```bash
grep -c "Plan-passthrough mapping" skills/skill-3-task-gen/SKILL.md
grep -c "source_plan_path" skills/skill-3-task-gen/SKILL.md
```

Each must be >= 1.

- [ ] **Step 5: Commit**

```bash
git add skills/skill-3-task-gen/SKILL.md
git commit -m "feat(skill-3): plan-passthrough plan-file mapping (Option B) from task_hints.tasks[] to tasks.yaml"
```

---

### Task 10: Update `skill-5-start-task/SKILL.md` to delegate to executing-plans when task has `source_plan_path`

**Files:**
- Modify: `skills/skill-5-start-task/SKILL.md`

- [ ] **Step 1: Read current Step 1 (Load Task Definition) on lines 33-37**

Verbatim current text:

```markdown
### Step 1: Load Task Definition

1. Find the task by ID in `tasks.yaml` or fallback to markdown files
2. Extract: name, type, phase, dependencies, deliverables, verification criteria
3. If task not found, list similar task IDs and ask user to clarify
```

- [ ] **Step 2: Augment Step 1 with a new sub-step (4) that detects plan-passthrough**

Use Edit to replace the entire Step 1 block with:

```markdown
### Step 1: Load Task Definition

1. Find the task by ID in `tasks.yaml` or fallback to markdown files
2. Extract: name, type, phase, dependencies, deliverables, verification criteria
3. If task not found, list similar task IDs and ask user to clarify
4. **Plan-passthrough detection**: if the task entry in `tasks.yaml` has `source_plan_path` (no anchor — Option B operates at plan-file granularity), mark this task as "plan-passthrough mode" and SKIP the legacy Step 5 type-specific workflow. Plan-passthrough mode runs Step 5' (new) below.
```

- [ ] **Step 3: Insert a new Step 5' "Plan-Passthrough Execution" before the existing Step 5**

Use Edit to insert immediately before `### Step 5: Enter Type-Specific Workflow`:

```markdown
### Step 5' — Plan-Passthrough Execution (when source_plan_path present)

When Step 1.4 marked the task as plan-passthrough mode, the execution model is "load the whole plan and run it" — delegate to `superpowers:executing-plans` (or `superpowers:subagent-driven-development` if subagents are available, which is the recommended path).

This skill operates at plan-FILE granularity (Option B): one prd2impl task = one plan file. Intra-plan sequencing (the `### Task 1`, `### Task 2`, ... headings within the source md) is handled by executing-plans itself; prd2impl does not slice the plan.

#### Step 5'.1 — Verify the source plan still exists

```bash
test -f {source_plan_path} && echo OK || echo "MISSING source plan"
```

If MISSING, halt and ask the user to either restore the file or remove `source_plan_path` from the task entry (which degrades the task to legacy Step 5).

#### Step 5'.2 — Verify the plan is still parseable

Apply `skill-0-ingest/lib/plan-parser.md` to `{source_plan_path}`. If the parser returns `error: "not-a-plan"` or `error: "plan-without-tasks"`, halt and surface the parser's error to the user. The plan may have been hand-edited into an unparseable state.

#### Step 5'.3 — Delegate execution to superpowers

**Preferred path — `superpowers:subagent-driven-development` is installed**:

Invoke it. The skill expects no CLI args; it operates on the plan that the caller has just loaded into context. From this skill, the invocation is conceptually:

```
1. Announce: "Delegating task {task_id} to superpowers:subagent-driven-development on plan {source_plan_path}."
2. Read the plan into context.
3. Invoke the subagent-driven-development skill, passing the plan path as its starting context.
```

The subagent-driven-development skill will iterate the plan's `### Task N:` headings, dispatch a fresh subagent per task, run two-stage review between tasks, and tick each `- [ ]` checkbox in the source plan md as steps complete.

**Fallback — only `superpowers:executing-plans` is installed**:

Invoke it. Same shape — no CLI args; the skill operates on the plan currently in context. It runs all tasks sequentially in this session, with TodoWrite-based tracking and checkpoint pauses.

**Final fallback — neither superpowers skill installed**:

Log a warning: "plan-passthrough cannot execute step-by-step without `superpowers:executing-plans` or `superpowers:subagent-driven-development`. Falling back to legacy Step 5 type-specific workflow." Then jump to the existing Step 5 below. The user can install superpowers and retry.

#### Step 5'.4 — Task completion

When the delegated skill reports completion (all `### Task N:` blocks in the source plan have all their `- [ ]` boxes ticked), mark the prd2impl task `completed` in `tasks.yaml` AND in `task-status.md`. Commit message format:

```
task: {task_id} → completed (plan-passthrough; {N}/{N} plan-tasks done, {S}/{S} steps)
```

Where N = source_plan_task_count from tasks.yaml, S = source_plan_step_count.

#### Step 5'.5 — Autopilot interaction

If `--autopilot={level}` was passed to /start-task, persist it (per existing Autopilot Mode section) AND prefix the announcement with a note for the delegated skill: "Autopilot level: {level} — apply your own auto-proceed rules within this plan." The two superpowers skills have their own interpretation of autopilot semantics; prd2impl just forwards the level.

```

- [ ] **Step 4: Update the "Status Transitions" section to mention the new path**

Find the Status Transitions section (around line 210). Add one bullet after it:

```markdown
> Plan-passthrough tasks (with `source_plan_path`) transition via Step 5'. Per-step progress is recorded as `- [x]` ticks in the source plan md, not in task-status.md.
```

- [ ] **Step 5: Verify**

```bash
grep -c "Step 5'" skills/skill-5-start-task/SKILL.md
grep -c "source_plan_path" skills/skill-5-start-task/SKILL.md
grep -c "subagent-driven-development\|executing-plans" skills/skill-5-start-task/SKILL.md
```

Each must be >= 2.

- [ ] **Step 6: Commit**

```bash
git add skills/skill-5-start-task/SKILL.md
git commit -m "feat(skill-5): plan-passthrough delegates whole plan to superpowers (Option B)"
```

---

## Phase D — Progress reporting (skill-9)

### Task 11: Update `skill-9-task-status/SKILL.md` to compute per-step progress from source plan checkboxes

**Files:**
- Modify: `skills/skill-9-task-status/SKILL.md`

- [ ] **Step 1: Read current Step 1 (Load Data) on lines 30-55**

Identify where the skill loads tasks.yaml and reads task statuses.

- [ ] **Step 2: Insert a new "Step 1.5 — Plan-passthrough progress" after Step 1**

Use Edit to insert immediately before `### Step 2: Compute Statistics`:

```markdown
### Step 1.5: Plan-passthrough progress (0.4.1+, Option B coarse-grained)

For each task with `source_plan_path` (and status `in_progress`):

1. Open `{source_plan_path}` (a markdown file at the repo-relative path).
2. Count `- [ ]` (unchecked) and `- [x]` (checked) bullets across the WHOLE file (the prd2impl task = the whole plan file under Option B).
3. Also count `### Task N:` headings to get plan-task count.
4. Compute `step_progress: {checked}/{total}` AND `plan_task_progress: {fully-checked-plan-tasks}/{total-plan-tasks}` where a plan-task is "fully-checked" when its body contains zero `- [ ]` and at least one `- [x]`. Attach both to the task's in-memory record.
5. Use this in Step 4's Active Tasks table: render the Duration column as `2h (12/30 steps, 3/8 plan-tasks)` instead of just `2h`.

If `{source_plan_path}` is missing, fall back to no step progress (no error — just absent). The task-level status still reflects the tasks.yaml entry.

**Why this matters**: a plan-passthrough task can encompass dozens of checkbox steps across many plan-tasks. The operator wants to know "is T1 halfway done or just starting?" The plan md is authoritative — its checkboxes are mechanically ticked by `superpowers:subagent-driven-development` / `executing-plans` as work progresses (Task 10 Step 5'.3 above).
```

- [ ] **Step 3: Update the Active Tasks table example**

Find the "Active Tasks" example output around line 127-129. Add a note after it:

```markdown
> When a task has `source_plan_path`, the Duration column is augmented with `{checked}/{total} steps, {done}/{total} plan-tasks`. This lets the operator see whether a long-running plan-passthrough task is progressing through its plan or stuck.
```

- [ ] **Step 4: Verify**

```bash
grep -c "step_progress\|source_plan_path" skills/skill-9-task-status/SKILL.md
```

Expected: >= 2.

- [ ] **Step 5: Commit**

```bash
git add skills/skill-9-task-status/SKILL.md
git commit -m "feat(skill-9): per-step progress from source plan checkboxes"
```

---

## Phase E — TDD-step propagation (skill-8)

### Task 12: Update `skill-8-batch-dispatch/SKILL.md` Step 4 to delegate plan-passthrough tasks to superpowers

**Files:**
- Modify: `skills/skill-8-batch-dispatch/SKILL.md`

- [ ] **Step 1: Read current Step 4 (Construct Agent Prompts) on lines 176-222**

The current prompt template is a Python f-string. We will not rewrite it from scratch — we add a "Plan-passthrough block" that gets appended to the prompt when the task has `source_plan_path`.

- [ ] **Step 2: Add a new sub-section "Step 4a — Plan-passthrough block (when source_plan_path present)"**

Use Edit to insert immediately before the closing `"""` of the prompt_template (right after the "Yellow review expectations" block, around line 222):

```markdown
### Step 4a: Plan-passthrough block (when source_plan_path present)

When the task being dispatched has `source_plan_path` in its `tasks.yaml` entry, REPLACE the "Type-Specific Workflow" portion of the agent prompt with the block below. The subagent delegates execution to `superpowers:subagent-driven-development` (or `executing-plans` as fallback), which handles per-step TDD discipline internally — skill-8 does NOT inject step-level instructions itself.

**Step 4a.1**: Construct this block and use it INSTEAD of the green/yellow workflow lines in the prompt_template:

````
## Plan-Passthrough Execution

Your task is plan-passthrough mode. The source plan lives at `{source_plan_path}`. It is a writing-plans-format implementation plan with `### Task N:` headings and `- [ ] **Step M:**` checkboxes. Your job is to execute the WHOLE plan end-to-end inside your isolated worktree.

### Required workflow

1. Read the source plan in full: `{source_plan_path}`.
2. Invoke `superpowers:subagent-driven-development` on it. If subagent-driven-development is not available, invoke `superpowers:executing-plans` instead. If neither is available, STOP and report — do NOT improvise step execution.
3. The chosen superpowers skill enforces:
   - One step at a time (the plan's `- [ ]` checkbox rhythm)
   - TDD discipline (write failing test → run, verify FAIL → write minimal impl → run, verify PASS → commit)
   - Verbatim execution of `Run: <cmd>` lines with actual output reporting
   - Commit cadence as the plan declares
4. Tick `- [x]` boxes in the source plan md AS YOU GO (the superpowers skill does this; do not skip it — the prd2impl progress dashboard reads these ticks).

### Hard rules (apply ON TOP of the superpowers skill's discipline)

- **Worktree scope**: only modify files this prd2impl task's `deliverables[]` declares, OR files the source plan declares under `**Files:**`. Anything else is out-of-scope and must STOP-and-report.
- **No plan editing**: if you find a step is wrong (referenced symbol missing, command syntax broken, etc.), STOP and report. Do NOT "fix the plan as you go" — the user owns plan revisions.
- **No early exit**: do NOT mark the prd2impl task completed until ALL `### Task N:` headings in the source plan have all their checkboxes ticked.

### Completion criteria

Before marking the prd2impl task `completed`:
- Every `- [ ]` in `{source_plan_path}` is now `- [x]`.
- All tests declared in the plan pass under their declared command.
- `git diff {base_branch}...HEAD --name-status` matches the plan's aggregated File Structure (skill-10-smoke-test will cross-check this at milestone time; you should self-check it now).
- Commit message format: `task: {task_id} — plan-passthrough complete ({source_plan_step_count} steps across {source_plan_task_count} plan-tasks)`.
````

**Step 4a.2**: When constructing the prompt, REMOVE the "Type-Specific Workflow" instructions (the `Enter dev-loop: skill-5-feature-eval...` and `Draft deliverables → produce review checklist...` lines) — they don't apply in plan-passthrough mode. The superpowers skill called inside the subagent's worktree handles all workflow decisions.

**Step 4a.3**: Why this is cleaner than inlining the plan steps verbatim into the prompt (the original Option A approach): the writing-plans format is purpose-built for `superpowers:executing-plans` and `superpowers:subagent-driven-development` to consume. Re-encoding the steps into a prd2impl prompt would duplicate that contract and drift out of sync as superpowers evolves. The subagent just opens the plan file like any developer would and follows it.

```

- [ ] **Step 3: Update the "Step 4" preamble to flag the new branch**

Find the line that says `### Step 4: Construct Agent Prompts`. Use Edit to add a note immediately after it:

```markdown
> **Branching**: when a task has `source_plan_path`, also run Step 4a below (after the legacy template construction). Step 4a appends a Plan-Passthrough Execution block that overrides the Type-Specific Workflow instructions.
```

- [ ] **Step 4: Verify**

```bash
grep -c "Plan-Passthrough Execution" skills/skill-8-batch-dispatch/SKILL.md
grep -c "subagent-driven-development" skills/skill-8-batch-dispatch/SKILL.md
grep -c "source_plan_path" skills/skill-8-batch-dispatch/SKILL.md
```

Each must be >= 1.

- [ ] **Step 5: Commit**

```bash
git add skills/skill-8-batch-dispatch/SKILL.md
git commit -m "feat(skill-8): plan-passthrough subagents delegate to superpowers (Option B)"
```

---

## Phase F — Plan-grounded smoke-test (skill-10)

### Task 13: Update `skill-10-smoke-test/SKILL.md` to cross-check declared vs actual file changes

**Files:**
- Modify: `skills/skill-10-smoke-test/SKILL.md`

- [ ] **Step 1: Locate where to insert (between Step 2 Task Completion Check and Step 3 Automated Test Verification)**

Read lines 70-89 of `skill-10-smoke-test/SKILL.md`. The new section sits between Step 2 (line 89, end) and Step 3 (line 91, "Automated Test Verification").

- [ ] **Step 2: Insert "Step 2.5 — Plan-vs-Actual File Structure Check"**

Use Edit to insert immediately before `### Step 3: Automated Test Verification`:

```markdown
### Step 2.5: Plan-vs-Actual File Structure Check (0.4.1+, Option B coarse-grained)

**Triggers when**: at least one task in the milestone has `source_plan_path` in its `tasks.yaml` entry.

For each such task, read the matching `task-hints.yaml` entries (rich per-plan-task data) to extract per-plan-task `files.create` + `files.modify` lists. If `task-hints.yaml` is missing or out of sync, re-parse the plan with `skill-0-ingest/lib/plan-parser.md` (Rule 3) as a fallback. Cross-check against actual git history.

The report breaks down to per-PLAN-TASK rows (e.g. `T1 / plan-task-1`, `T1 / plan-task-2`) for granularity, even though the prd2impl task is plan-FILE level. This is the "richness preserved" half of the plan-passthrough deal — task_hints.yaml is the source of truth for that richness.

#### Step 2.5.1 — Build the declared set per plan-task

For each prd2impl task `T` with `source_plan_path = P`:
- Lookup the `task_hints.tasks[]` entries whose `source_plan_path == P` (these are the plan-tasks within this prd2impl task).
- For each such entry `pt` (1-based index `i`), record:
  - `declared_create[T/pt_i] = pt.files.create`
  - `declared_modify[T/pt_i] = pt.files.modify`

If `task-hints.yaml` cannot be located (e.g. ingest-docs was never run or task-hints was deleted), parse `P` directly with plan-parser and use the parsed `tasks[]`. Surface a WARN: "task-hints.yaml not found; re-parsed plan at smoke-test time (slower; please regenerate)."

#### Step 2.5.2 — Build the actual set (one-shot, scoped to base branch)

```bash
git diff --name-status {base_branch}...HEAD | awk '$1 == "A" { print $2 }'    # actually created
git diff --name-status {base_branch}...HEAD | awk '$1 == "M" { print $2 }'    # actually modified
```

Define:
- `actual_create` = the "A" set
- `actual_modify` = the "M" set
- (also note: "D" = deleted, "R..." = renamed — handle as their own row class)

The actual set is computed once for the whole milestone (not per-plan-task) — it's the cumulative diff vs the milestone's base branch.

#### Step 2.5.3 — Compute the four delta sets per plan-task

For each `T/pt_i` row built in Step 2.5.1:

| Delta | Definition | Severity |
|---|---|---|
| `missing_create` | `declared_create[T/pt_i] ∩ NOT(actual_create)` | NO-GO (declared file does not exist) |
| `unexpected_create` | `actual_create - ⋃(declared_create across all T/pt_i)` | WARN (file created outside any plan; reported ONCE at milestone level, not per-plan-task) |
| `declared_modify_not_modified` | `declared_modify[T/pt_i] ∩ NOT(actual_modify ∪ actual_create)` | NO-GO (plan said to modify but no diff) |
| `unexpected_modify` | `actual_modify - ⋃(declared_modify across all T/pt_i)` | WARN (modification outside any plan; reported ONCE at milestone level) |

`declared_modify_not_modified` subtracts `actual_create` because a file declared as "modify" but actually created from scratch in this milestone is a NAMING mismatch, not a missing change — surface it as a WARN with hint "plan said modify; actual was create — was this file new this milestone?"

#### Step 2.5.4 — Build the report block

Add a new section to the gate report (Step 6):

```markdown
## Plan vs Actual File Structure

Each prd2impl task with `source_plan_path` is broken down to its plan-tasks
(read from task-hints.yaml). The "Plan-Task" column shows `{prd2impl-task} /
plan-task-{N}` where N is the 1-based ordinal within the plan.

| Plan-Task | Status | Declared (C/M) | Actual (C/M) | Delta |
|-----------|--------|----------------|--------------|-------|
| T1 / plan-task-1 | ✅ | 5/0 | 5/0 | none |
| T1 / plan-task-2 | ❌ | 2/3 | 2/1 | declared_modify_not_modified: api_routes.py, auth.py |
| T1 / plan-task-4 | ⚠️ | 1/2 | 3/2 | unexpected_create: helpers/utils.py, helpers/__init__.py |

### Blocking deltas (NO-GO contributors)
- T1 / plan-task-2: declared but missing modify on `autoservice/api_routes.py`
- T1 / plan-task-2: declared but missing modify on `autoservice/auth.py`

### Warning deltas (CONDITIONAL GO contributors)
- T1 / plan-task-4: unexpected create `helpers/utils.py` — scope creep or incidental?
```

#### Step 2.5.5 — Gate-decision contribution

- Any `missing_create` row → contributes a NO-GO to the milestone gate.
- Any `declared_modify_not_modified` row → contributes a NO-GO.
- `unexpected_create` and `unexpected_modify` rows are WARNINGs only — they contribute a CONDITIONAL GO if no NO-GO is otherwise present.

#### Step 2.5.6 — Graceful degradation

If NO tasks in the milestone have `source_plan_path`, skip this step entirely (silent — no warning). The milestone may simply not be a plan-passthrough milestone.

If a task has `source_plan_path` but the file is missing, surface a CONDITIONAL GO with the diagnostic "plan file missing — cannot verify file structure" and proceed with Step 3.

```

- [ ] **Step 3: Update Step 6 ("Generate Gate Report") to include the new section**

Find Step 6 in skill-10-smoke-test/SKILL.md. Add to the summary table:

```markdown
| Plan vs Actual files | ✅ / ❌ / ⚠️ PASS/FAIL/WARN | {N} missing_create, {M} declared_not_modified, {U} unexpected |
```

- [ ] **Step 4: Verify**

```bash
grep -c "Plan vs Actual" skills/skill-10-smoke-test/SKILL.md
grep -c "missing_create\|declared_modify_not_modified" skills/skill-10-smoke-test/SKILL.md
```

Each must be >= 2.

- [ ] **Step 5: Commit**

```bash
git add skills/skill-10-smoke-test/SKILL.md
git commit -m "feat(skill-10): plan-vs-actual file structure check (Step 2.5)"
```

---

## Phase G — Documentation + end-to-end smoke

### Task 14: Add a CHANGELOG entry

**Files:**
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Read the current CHANGELOG head**

```bash
head -40 CHANGELOG.md
```

Find the most recent version heading. The next entry probably goes under an `## [Unreleased]` or `## 0.4.1` section.

- [ ] **Step 2: Add the entry**

Insert under the most recent unreleased section (or create one above 0.4.0):

```markdown
## [Unreleased] — 0.4.1

### Added — Plan-passthrough (Option B coarse-grained) × Plan-grounded smoke (2026-05-12)
- **skill-0-ingest**: detects writing-plans-format md (header sub-skill block) and routes to new `lib/plan-parser.md`. Output: `task_hints.tasks[]` array with `source_plan_path` + `source_plan_anchor` per plan-task (rich data lives in task-hints.yaml). Backward-compatible: legacy plans without the writing-plans header fall through to the existing implementation_steps flow.
- **schema**: `task-hints.schema.yaml` gains a `tasks[]` property (optional, per-plan-task hierarchy).
- **skill-3-task-gen**: when `task_hints.tasks[]` is non-empty, emits **one prd2impl task per unique `source_plan_path`** (plan-file granularity — Option B). Files declared across all plan-tasks in the file are aggregated into one `deliverables[]` list. The 8 admin-v2 plans become 8 prd2impl tasks (T1, T2, T3, T4A, T4B, T5, T6A, T6B).
- **skill-5-start-task**: Step 5' delegates the WHOLE plan to `superpowers:subagent-driven-development` (preferred) or `superpowers:executing-plans` (fallback) when the prd2impl task carries `source_plan_path`. No CLI flags needed — the superpowers skill consumes the plan as-is. Per-step progress is recorded by the superpowers skill ticking `- [ ]` boxes in the source plan md.
- **skill-8-batch-dispatch**: Step 4a constructs a "Plan-Passthrough Execution" prompt block that REPLACES the legacy Type-Specific Workflow instructions. The subagent's job is to invoke `superpowers:subagent-driven-development` on the source plan inside its worktree — prd2impl does NOT inline verbatim plan steps into the prompt (that would duplicate the superpowers contract).
- **skill-9-task-status**: Active Tasks table shows per-plan progress (`12/30 steps`) for tasks with `source_plan_path`, by counting checked vs unchecked boxes across the whole plan file.
- **skill-10-smoke-test**: Step 2.5 cross-checks plan-declared files vs `git diff`, using the rich per-plan-task data still living in task-hints.yaml. `missing_create` and `declared_modify_not_modified` contribute NO-GO; `unexpected_create` / `unexpected_modify` contribute CONDITIONAL GO.

### Granularity choice — Option B (coarse-grained)
This release implements **1 prd2impl task = 1 plan file**. A finer-grained mapping (1 plan-task = 1 prd2impl task, with plan-slicing at execution time) was considered and deferred. The 0.4.0 → 0.4.1 transition can be revisited if intra-plan parallel dispatch becomes a real need.

### Designed for
The 8 admin-v2 plans at `AutoService/docs/superpowers/plans/2026-05-11-admin-v2-*.md` (and any other writing-plans-format md) are now first-class prd2impl input. Run `/ingest-docs <plans>` → `/task-gen` → `/start-task` (or `/batch-dispatch`) → `/smoke-test` end-to-end without information loss between stages.

### Backward compatibility
All changes are additive. Tasks without `source_plan_path` behave exactly as 0.4.0. Plans that don't use the writing-plans header are still parsed by the legacy step-extraction flow.
```

- [ ] **Step 3: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs: CHANGELOG entry for 0.4.1 plan-passthrough × TDD × plan-grounded smoke"
```

---

### Task 15: End-to-end manual smoke test

**Files:** None — this is verification only.

- [ ] **Step 1: Set up a sandbox workspace**

Use a throwaway directory (NOT the AutoService repo, to avoid polluting it):

```bash
mkdir -p /tmp/prd2impl-passthrough-smoke
cd /tmp/prd2impl-passthrough-smoke
mkdir -p docs/superpowers/plans docs/plans
cp "D:/Work/h2os.cloud/AutoService-dev-a/docs/superpowers/plans/2026-05-11-admin-v2-p1-cr-data-layer.md" \
   docs/superpowers/plans/
cat > docs/plans/project.yaml <<'YAML'
project:
  name: passthrough-smoke
  plans_dir: docs/plans
  branches:
    integration: dev
  team: [{name: smoke, branch: dev}]
YAML
```

- [ ] **Step 2: Run /ingest-docs on the p1 plan**

In Claude Code from this sandbox:

```
/ingest-docs docs/superpowers/plans/2026-05-11-admin-v2-p1-cr-data-layer.md
```

**Expected**:
- Role detection table shows `role: plan, confidence: 100` (because the writing-plans header is present)
- After confirmation, Phase 2b prints `Extracted N tasks (S total steps) (plan-passthrough)`
- Phase 4 writes `docs/plans/2026-05-12-task-hints.yaml`
- `cat docs/plans/2026-05-12-task-hints.yaml | yq '.task_hints.tasks | length'` returns the same task count as Task 1 Step 2 recorded for the fixture.

- [ ] **Step 3: Run /task-gen**

```
/task-gen
```

**Expected**:
- Branch message: "task_hints.tasks[] detected — using Plan-passthrough mapping (Option B: plan-file granularity)"
- `docs/plans/tasks.yaml` is created
- Exactly ONE task entry (since only one plan file was ingested)
- That entry has `source_plan_path` set (NO `source_plan_anchor` — Option B operates at file granularity)
- Task ID follows the `T{plan-letter}` pattern: `T1` (from filename `*-p1-*`)
- `deliverables[]` aggregates all create+modify paths from across the plan's plan-tasks, de-duplicated

```bash
yq '.tasks | length' docs/plans/tasks.yaml                  # expect: 1
yq '.tasks[0].id' docs/plans/tasks.yaml                     # expect: T1
yq '.tasks[0].source_plan_path' docs/plans/tasks.yaml       # expect: docs/superpowers/plans/2026-05-11-admin-v2-p1-cr-data-layer.md
yq '.tasks[0].source_plan_task_count' docs/plans/tasks.yaml # expect: matches Task 1 Step 2 record
yq '.tasks[0].deliverables | length' docs/plans/tasks.yaml  # expect: > 10 (aggregate of plan-task file lists)
```

- [ ] **Step 4: Dry-run /start-task on T1**

```
/start-task T1
```

**Expected**:
- Step 1.4 logs "plan-passthrough mode detected (source_plan_path: ...)"
- Step 5'.1 confirms the source plan exists
- Step 5'.2 confirms plan-parser returns no error (valid writing-plans format)
- Step 5'.3:
  - If `superpowers:subagent-driven-development` is installed: logs "Delegating to subagent-driven-development on plan {path}"
  - Else if `superpowers:executing-plans` is installed: logs "Delegating to executing-plans on plan {path}"
  - Else: logs "Neither superpowers skill installed; falling back to legacy Step 5"

Do NOT actually execute the task in the sandbox — verify the routing log only. Ctrl-C / "stop" if it tries to proceed.

- [ ] **Step 5: Dry-run /batch-dispatch with two plans**

For this step we ingest a second plan so we have two prd2impl tasks (T1 and a second one). If you only have p1 ingested, skip this step and just run /batch-dispatch T1 to verify single-task dispatch.

```bash
# (optional) ingest p4a as a second plan
cp "D:/Work/h2os.cloud/AutoService-dev-a/docs/superpowers/plans/2026-05-11-admin-v2-p4a-ingest-layer.md" \
   docs/superpowers/plans/
```

Then in Claude Code:

```
/ingest-docs docs/superpowers/plans/2026-05-11-admin-v2-p4a-ingest-layer.md
/task-gen
/batch-dispatch T1,T4A
```

**Expected**:
- Step 4 prints the legacy prompt template
- Step 4a REPLACES the Type-Specific Workflow lines with the "Plan-Passthrough Execution" block that:
  - Tells the subagent to read `{source_plan_path}` and invoke `superpowers:subagent-driven-development`
  - Lists hard rules (worktree scope, no plan editing, no early exit)
  - Defines completion criteria (all checkboxes ticked, tests pass, git diff matches File Structure)
- The block does NOT contain verbatim plan steps inline (those are read from the file by the subagent)
- The agent is NOT actually dispatched (cancel before launch)

Verify by inspecting the prompt that batch-dispatch would have sent.

- [ ] **Step 6: Synthetic smoke-test pass**

Manually create a synthetic git history that satisfies T1's declared files (the aggregated set, since T1 = whole p1 plan) but adds one extra:

```bash
cd /tmp/prd2impl-passthrough-smoke
git init && git checkout -b dev && git commit --allow-empty -m "base"
git checkout -b feature
# Create the aggregated p1 file set — pick any reasonable subset for the smoke
mkdir -p autoservice/change_request tests/change_request
touch autoservice/change_request/__init__.py
touch autoservice/change_request/schema.py
touch autoservice/change_request/models.py
touch tests/change_request/__init__.py
touch tests/change_request/conftest.py
touch tests/change_request/test_schema.py
touch helpers/utils.py     # NOT in p1's aggregated declared files
git add -A && git commit -m "T1 deliverables + 1 unexpected"
```

Mark T1 completed in tasks.yaml (manual edit). Define an M1 milestone in execution-plan.yaml containing T1 (manual edit; the smoke is for skill-10 not skill-4). Then run:

```
/smoke-test M1
```

**Expected**:
- Step 2.5 "Plan vs Actual File Structure" report appears
- The report breaks T1 down into its constituent plan-tasks (since task-hints.yaml still has the rich per-plan-task data)
- At least one row shows: `declared X/Y, actual X+1/Y, delta: unexpected_create: helpers/utils.py`
- Other rows show `declared_modify_not_modified` for any p1 plan-task whose Modify list wasn't touched in the synthetic commit
- Gate verdict: NO-GO if there were missing modifies, otherwise CONDITIONAL GO (unexpected_create is WARN-only)

- [ ] **Step 7: Document any deviations**

If any of Steps 2-6 produce unexpected output, capture the diff in a new file `docs/superpowers/plans/2026-05-12-plan-passthrough-smoke-notes.md` and open a follow-up task. If everything matches, commit nothing (the smoke test is documentation in this plan, not artifact).

- [ ] **Step 8: Close-out commit (only if smoke notes were written)**

```bash
git add docs/superpowers/plans/2026-05-12-plan-passthrough-smoke-notes.md
git commit -m "docs: smoke-test notes for 0.4.1 plan-passthrough"
```

---

## Open questions for the executor

1. **plan-letter inference fallback**: if a plan filename does NOT match `*-p\d+[a-z]?-*.md` (e.g., a one-off plan named `2026-05-12-some-feature.md`), should /task-gen use `TP{N}` or refuse to ingest? Current plan: use `TP{N}` (silent fallback). Reconsider after end-to-end smoke.

2. **Cross-plan dependency wiring**: when multiple plans are ingested in one `/ingest-docs` call, the dependency-inference rule chains them sequentially (`T2 depends_on T1`, `T3 depends_on T2`, …). This is wrong when plans are independent. Defer to user manual edit, or add a `--no-cross-plan-deps` flag? Current plan: chain sequentially + print hint; let user edit `tasks.yaml`.

3. **What if writing-plans format changes**: the writing-plans skill itself can evolve (new header format, new step syntax). plan-parser is pinned to the `REQUIRED SUB-SKILL: Use superpowers:executing-plans` or `superpowers:subagent-driven-development` substring. If superpowers renames either skill, the detector breaks. Mitigation: add a `--force-plan-format` ingest flag for the transition window. Track superpowers version compatibility in CHANGELOG.

4. ~~**executing-plans contract**~~ **(RESOLVED 2026-05-12)**: `superpowers:executing-plans` v5.1.0 takes no CLI args — it loads the plan in context and runs all tasks sequentially. This forced the Option B granularity decision: prd2impl tasks operate at plan-file granularity, not plan-task granularity. Step 5'.3 delegates the WHOLE plan and lets the superpowers skill handle intra-plan sequencing.

5. **Option A (fine-grained) follow-up**: if end-to-end smoke reveals that 8 admin-v2 plans → 8 prd2impl tasks is too coarse (e.g., one plan blocks others for hours when its sub-tasks could parallelize), revisit Option A by adding a plan-slicer at start-task time. The plan-parser library this release lands ALREADY contains the per-plan-task hierarchy needed; the slicer would only need to write a temporary `_slice.md` containing one plan-task and hand it to executing-plans. Plumbing only — no schema changes required.

---

## Acceptance criteria for this whole plan

- [ ] All 15 tasks above have their checkboxes ticked.
- [ ] `git log --oneline 0.4.0..HEAD` on the prd2impl repo shows ~15 commits, all under conventional-commit prefixes `feat(...)`, `test(...)`, `docs(...)`, `chore(...)`.
- [ ] `/ingest-docs` on any AutoService admin-v2 plan produces a `task-hints.yaml` with non-empty `tasks[]` (rich per-plan-task data preserved).
- [ ] `/task-gen` emits **one prd2impl task per unique source_plan_path** (Option B coarse-grained), each carrying `source_plan_path` and aggregated `deliverables[]`. ID matches plan-letter (T1, T4A, etc.).
- [ ] `/start-task T1` on a plan-passthrough task with `superpowers:subagent-driven-development` installed delegates the whole plan cleanly (logs visible; no `--task-anchor` arg invented).
- [ ] `/batch-dispatch T1,T4A` produces agent prompts containing the "Plan-Passthrough Execution" block that tells the subagent to invoke superpowers on its source plan. The prompt does NOT contain verbatim plan-step contents inline.
- [ ] `/smoke-test` produces a Plan vs Actual section when at least one milestone task has `source_plan_path`. The section breaks down to per-plan-task rows by reading task-hints.yaml's rich data.
- [ ] All changes are backward-compatible: a task WITHOUT `source_plan_path` behaves byte-for-byte identical to 0.4.0.
- [ ] CHANGELOG.md `[Unreleased]` section documents every change AND explicitly notes Option B granularity choice.

---

## Out of scope for this plan (deferred to a follow-up)

- **#4 next-task parallel siblings** (medium ROI, separate plan)
- **#5 plan-layer preflight** (cross-task symbol resolution)
- **#6 contract-check cross-plan reference graph**
- **#7 retro-driven plan template improvement**
- **#8 ingest-time brainstorming ambiguity check**

These build on the foundation this plan lays (`source_plan_path` + plan-parser library) but each is a 2-3 day project of its own.
