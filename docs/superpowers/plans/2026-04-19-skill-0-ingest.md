# skill-0-ingest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `skill-0-ingest` to prd2impl so users can feed multiple heterogeneous Markdown documents (gap analyses, design specs, plans) into the pipeline and have `skill-3-task-gen` consume them unchanged.

**Architecture:** New skill at `skills/skill-0-ingest/` with a 4-phase flow (role-detect → extract → cross-validate → write). Produces three YAMLs compatible with existing skill outputs plus one new `task-hints.yaml`. Minor additive changes to `skill-3-task-gen` (optional task-hints input), `using-prd2impl` (router registration), and `README.md`.

**Tech Stack:** Markdown skill authoring. Skills are prompts; tests are fixture MDs + expected YAMLs diffed via `diff`. No runtime code beyond what Claude Code itself executes when running the skill.

**Repo:** `D:/Work/h2os.cloud/prd2impl/`

**Spec:** [docs/superpowers/specs/2026-04-19-skill-0-ingest-design.md](../specs/2026-04-19-skill-0-ingest-design.md)

---

## File Structure

```
prd2impl/
├── skills/skill-0-ingest/                                    # NEW
│   ├── SKILL.md                                              # orchestrator
│   ├── lib/
│   │   ├── role-detector.md                                  # Phase 1
│   │   ├── gap-extractor.md                                  # Phase 2a
│   │   ├── spec-extractor.md                                 # Phase 2b
│   │   ├── prd-extractor.md                                  # Phase 2c
│   │   └── cross-validator.md                                # Phase 3
│   ├── schemas/
│   │   ├── task-hints.schema.yaml                            # new schema
│   │   ├── task-hints.example.yaml
│   │   └── gap-analysis.example.yaml                         # extended example
│   ├── templates/
│   │   └── role-confirmation.md
│   └── tests/
│       ├── fixtures/                                         # MD inputs
│       │   ├── clear-gap.md
│       │   ├── clear-spec.md
│       │   ├── clear-plan.md
│       │   ├── clear-prd.md
│       │   ├── clear-stories.md
│       │   ├── ambiguous.md
│       │   ├── cross-val-orphan.md
│       │   ├── cross-val-p0-uncovered.md
│       │   ├── cross-val-dangling-step.md
│       │   ├── cross-val-nongoal-conflict.md
│       │   └── cross-val-dead-anchor.md
│       ├── expected/                                         # expected YAMLs
│       │   ├── clear-gap.gap-analysis.yaml
│       │   ├── clear-spec.task-hints.yaml
│       │   ├── clear-plan.prd-structure.yaml
│       │   ├── clear-prd.prd-structure.yaml
│       │   ├── clear-stories.prd-structure.yaml
│       │   ├── role-detection-table.txt
│       │   └── cross-val-warnings.txt
│       └── run-fixture.md                                    # manual run instructions
├── skills/skill-3-task-gen/SKILL.md                          # MODIFIED
├── skills/using-prd2impl/SKILL.md                            # MODIFIED
└── README.md                                                 # MODIFIED
```

Each file has one responsibility. Fixtures and expected outputs live together to make acceptance diffs a one-command check.

---

## Task 1: Create skill-0-ingest directory skeleton

**Files:**
- Create: `skills/skill-0-ingest/SKILL.md`
- Create: `skills/skill-0-ingest/lib/` (empty dir)
- Create: `skills/skill-0-ingest/schemas/` (empty dir)
- Create: `skills/skill-0-ingest/templates/` (empty dir)
- Create: `skills/skill-0-ingest/tests/fixtures/` (empty dir)
- Create: `skills/skill-0-ingest/tests/expected/` (empty dir)

- [ ] **Step 1: Create directory structure**

Run:
```bash
cd D:/Work/h2os.cloud/prd2impl
mkdir -p skills/skill-0-ingest/lib
mkdir -p skills/skill-0-ingest/schemas
mkdir -p skills/skill-0-ingest/templates
mkdir -p skills/skill-0-ingest/tests/fixtures
mkdir -p skills/skill-0-ingest/tests/expected
```

Expected: five directories exist under `skills/skill-0-ingest/`.

- [ ] **Step 2: Create SKILL.md stub with frontmatter only**

Write `skills/skill-0-ingest/SKILL.md`:

```markdown
---
name: ingest-docs
description: "Ingest multiple existing Markdown documents (gap analyses, design specs, plans) and produce the YAML artifacts the rest of the prd2impl pipeline expects. Use when user already has hand-written intermediate docs and wants to skip straight to /task-gen, or says 'ingest docs', 'import these files', '/ingest-docs'."
---

# Skill 0: Ingest Docs

<SUBAGENT-STOP>
If you were dispatched as a subagent to execute a specific task, skip this skill.
</SUBAGENT-STOP>

_Full orchestration body written in Task 8. This file is a stub during development._
```

- [ ] **Step 3: Verify structure**

Run:
```bash
find skills/skill-0-ingest -type d | sort
cat skills/skill-0-ingest/SKILL.md
```

Expected output:
```
skills/skill-0-ingest
skills/skill-0-ingest/lib
skills/skill-0-ingest/schemas
skills/skill-0-ingest/templates
skills/skill-0-ingest/tests
skills/skill-0-ingest/tests/expected
skills/skill-0-ingest/tests/fixtures
```
Plus the SKILL.md contents.

- [ ] **Step 4: Commit**

```bash
git add skills/skill-0-ingest/
git commit -m "feat(skill-0): scaffold skill-0-ingest directory structure"
```

---

## Task 2: Define task-hints.yaml schema + examples

**Files:**
- Create: `skills/skill-0-ingest/schemas/task-hints.schema.yaml`
- Create: `skills/skill-0-ingest/schemas/task-hints.example.yaml`
- Create: `skills/skill-0-ingest/schemas/gap-analysis.example.yaml`

- [ ] **Step 1: Write task-hints schema**

Write `skills/skill-0-ingest/schemas/task-hints.schema.yaml`:

```yaml
# JSON-Schema-flavored YAML spec for task-hints.yaml
# Not a formal validator input; used as documentation + reference.

$schema: "http://json-schema.org/draft-07/schema#"
title: task_hints
type: object
required: [task_hints]
properties:
  task_hints:
    type: object
    required: [source_files, file_changes, implementation_steps]
    properties:
      source_files:
        type: array
        items: {type: string}
        description: "Absolute or repo-relative paths to source MD files."

      file_changes:
        type: array
        items:
          type: object
          required: [path, change_type, purpose, source_anchor]
          properties:
            path: {type: string}
            change_type:
              type: string
              enum: [create, modify, delete, no-change]
            purpose: {type: string}
            source_anchor:
              type: string
              description: "Heading slug in the source MD to anchor back to context."
            related_gap_refs:
              type: array
              items: {type: string, pattern: "^GAP-[0-9]+$"}
              description: "Populated by cross-validator; may be empty initially."

      implementation_steps:
        type: array
        items:
          type: object
          required: [step, description]
          properties:
            step: {type: integer, minimum: 1}
            description: {type: string}
            depends_on_steps:
              type: array
              items: {type: integer}
            touches_files:
              type: array
              items: {type: string}
            source_anchor: {type: string}

      test_strategy:
        type: object
        properties:
          preserved_testids:
            type: array
            items: {type: string}
          new_tests:
            type: array
            items:
              type: object
              required: [name, focuses_on]
              properties:
                name: {type: string}
                focuses_on: {type: string}
          e2e_delta: {type: string}

      non_goals:
        type: array
        items: {type: string}
        description: "Hard boundaries. skill-3 rejects tasks matching these."

      risks:
        type: array
        items:
          type: object
          required: [risk, mitigation]
          properties:
            risk: {type: string}
            mitigation: {type: string}
```

- [ ] **Step 2: Write task-hints example**

Write `skills/skill-0-ingest/schemas/task-hints.example.yaml`:

```yaml
task_hints:
  source_files:
    - "docs/superpowers/specs/2026-04-18-admin-portal-web-layout-design.md"

  file_changes:
    - path: "frontend/apps/admin-portal/src/components/shell/AdminShell.tsx"
      change_type: create
      purpose: "topbar + rail + canvas shell"
      source_anchor: "6-file-changes-new"
      related_gap_refs: ["GAP-017"]
    - path: "frontend/apps/admin-portal/src/components/AdminWorkspace.tsx"
      change_type: modify
      purpose: "slim down; delete top cs-tb title bar and cs-tabs rendering"
      source_anchor: "6-file-changes-modified"
      related_gap_refs: ["GAP-017"]

  implementation_steps:
    - step: 1
      description: "Build shell: AdminShell + AdminTopbar + AdminRail + new CSS"
      touches_files:
        - "frontend/apps/admin-portal/src/components/shell/AdminShell.tsx"
      source_anchor: "9-implementation-order"
    - step: 2
      description: "App.tsx wires AdminShell"
      depends_on_steps: [1]
      touches_files:
        - "frontend/apps/admin-portal/src/App.tsx"

  test_strategy:
    preserved_testids:
      - "tab-wizard"
      - "tab-dashboard"
    new_tests:
      - name: "AdminRail.test.tsx"
        focuses_on: "default active = notifications; 5 icons switch tabs"
    e2e_delta: "no new E2E"

  non_goals:
    - "no design-system changes (tokens.css / components.css unchanged)"
    - "no mobile-specific UX"

  risks:
    - risk: "test selector regression"
      mitigation: "baseline full test run before refactor"
```

- [ ] **Step 3: Write extended gap-analysis example**

Write `skills/skill-0-ingest/schemas/gap-analysis.example.yaml`:

```yaml
gap_analysis:
  scan_date: "2026-04-19"
  source_type: "ingested"
  source_files:
    - "docs/plans/2026-04-18-prd-full-journey-gap.md"

  summary:
    total_gaps: 3
    by_priority:
      P0: 1
      P1: 1
      P2: 1

  gaps:
    - id: GAP-001
      source_id: "A-①"
      source_file: "2026-04-18-prd-full-journey-gap.md"
      source_anchor: "a--register-step-p0"
      description: "Missing 'register' step before upload"
      module: "admin-portal-wizard"
      priority: P0
      gap_type: missing
      existing_code: []
      missing_parts:
        - "Wizard pre-RegisterStep component"
        - "countries -> compliance_profile mapping"
      estimated_effort: medium
      depends_on_gaps: []

    - id: GAP-002
      source_id: "B-⑧"
      source_file: "2026-04-18-prd-full-journey-gap.md"
      source_anchor: "b--confidence-triggered-humanrequested-p1"
      description: "Agent confidence-triggered HumanRequested not wired"
      module: "operator-console"
      priority: P1
      gap_type: partial
      existing_code: ["autoservice/triage.py"]
      missing_parts:
        - "agent confidence field"
        - "threshold trigger emitting HumanRequested event"
      estimated_effort: small
      depends_on_gaps: []

    - id: GAP-003
      source_id: "A-④"
      source_file: "2026-04-18-prd-full-journey-gap.md"
      source_anchor: "a--compliance-templates-by-tenant-countries-p2"
      description: "Compliance rules not filtered by tenant.countries"
      module: "compliance"
      priority: P2
      gap_type: partial
      existing_code: ["autoservice/compliance/compliance.py"]
      missing_parts:
        - "load_rules_for_tenant(countries) filter"
      estimated_effort: small
      depends_on_gaps: []
```

- [ ] **Step 4: Commit**

```bash
git add skills/skill-0-ingest/schemas/
git commit -m "feat(skill-0): define task-hints.yaml schema and examples"
```

---

## Task 3: Implement role-detector

**Files:**
- Create: `skills/skill-0-ingest/lib/role-detector.md`
- Create: `skills/skill-0-ingest/tests/fixtures/clear-gap.md`
- Create: `skills/skill-0-ingest/tests/fixtures/clear-spec.md`
- Create: `skills/skill-0-ingest/tests/fixtures/clear-plan.md`
- Create: `skills/skill-0-ingest/tests/fixtures/clear-prd.md`
- Create: `skills/skill-0-ingest/tests/fixtures/clear-stories.md`
- Create: `skills/skill-0-ingest/tests/fixtures/ambiguous.md`
- Create: `skills/skill-0-ingest/tests/expected/role-detection-table.txt`

- [ ] **Step 1: Write fixture — clear-gap.md**

Write `skills/skill-0-ingest/tests/fixtures/clear-gap.md`:

```markdown
---
type: gap
---

# Sample Gap Analysis

## Summary
17 items total. 6 P0 / 6 P1 / 5 P2.

## Act A · Wizard (6 items)

### A-① Missing register step · P0
- **Current**: flow starts at upload
- **Fix**: add RegisterStep

### A-② IM group auto-creation · P0
- **Current**: channel-select only
- **Fix**: auto-create group + join agents
```

- [ ] **Step 2: Write fixture — clear-spec.md**

Write `skills/skill-0-ingest/tests/fixtures/clear-spec.md`:

```markdown
# Admin Portal Web Layout — Design

**Status:** Draft
**Scope:** frontend/apps/admin-portal/

## 6. File Changes

### New
- `frontend/apps/admin-portal/src/components/shell/AdminShell.tsx` — topbar + rail + canvas shell

### Modified
- `frontend/apps/admin-portal/src/components/AdminWorkspace.tsx` — slim down

## 9. Implementation Order
1. Build shell
2. Wire App.tsx (depends on 1)

## 2. Non-Goals
- No design-system changes
```

- [ ] **Step 3: Write fixture — clear-plan.md**

Write `skills/skill-0-ingest/tests/fixtures/clear-plan.md`:

```markdown
# 2026-04-18 Execution Plan

## Milestones
- M1: Wizard done — 2026-04-20
- M2: Ops done — 2026-04-22

## Phase breakdown
- P0 contract
- P1 wizard
- P2 ops
```

- [ ] **Step 4: Write fixture — clear-prd.md**

Write `skills/skill-0-ingest/tests/fixtures/clear-prd.md`:

```markdown
# Sample PRD

## §3 Modules

### MOD-01 Conversation
Handles chat routing.

## §4 User Stories

### US-001 Agent views conversation
**Persona:** operator
**Action:** view live chat
**Acceptance:**
- AC-001: messages appear in 500ms

## §6 NFRs

### NFR-01 Performance
API p95 < 200ms
```

- [ ] **Step 5: Write fixture — clear-stories.md**

Write `skills/skill-0-ingest/tests/fixtures/clear-stories.md`:

```markdown
# User Stories v1.1

## US-010
As a customer, I want to click a floating button on the merchant's site, so that I can start a chat without leaving.

## US-011
As an operator, I want a squad sidebar, so that I can see all active customers.
```

- [ ] **Step 6: Write fixture — ambiguous.md**

Write `skills/skill-0-ingest/tests/fixtures/ambiguous.md`:

```markdown
# Notes on Admin Portal

Some thoughts on the admin portal work. Not sure what to do about the wizard yet. Will need to think about testing.

The current layout feels cramped.
```

- [ ] **Step 7: Write expected role-detection-table.txt**

Write `skills/skill-0-ingest/tests/expected/role-detection-table.txt`:

```
Role Detection Results
======================
File                  Detected       Score    Disposition
clear-gap.md          gap            90+      auto-accept
clear-spec.md         design-spec    80+      auto-accept
clear-plan.md         plan           70+      auto-accept
clear-prd.md          prd            80+      auto-accept
clear-stories.md      user-stories   70+      auto-accept
ambiguous.md          unknown        <40      drop with warning
```

- [ ] **Step 8: Write role-detector.md**

Write `skills/skill-0-ingest/lib/role-detector.md`:

```markdown
# role-detector

Detect the role of each input MD file. Output a confirmation table.

## Input

Array of absolute file paths.

## Output

For each file, emit:

```yaml
- path: "path/to/file.md"
  detected_role: gap | design-spec | plan | prd | user-stories | unknown
  score: 0-100
  evidence:
    - "filename matches *-gap.md (+30)"
    - "heading contains 'Gap' (+30)"
    - "structure has P0/P1/P2 tags (+20)"
  alternatives:
    - role: design-spec
      score: 42
```

## Rules

### Signal 1 — Filename (weight 30)

Check the basename (lowercase) against these patterns. Pick the single highest-scoring pattern (do not stack):

| Pattern | Role | Points |
|---|---|---|
| `*-gap.md`, `*-gap-analysis.md`, `*gap*.md` | gap | 30 |
| `*-design.md`, `*-design-spec.md`, `*-spec.md` | design-spec | 30 |
| `*-plan.md`, `*-execution-plan.md` | plan | 30 |
| `*-prd.md`, `*-requirements.md` | prd | 30 |
| `*-stories.md`, `*-userstories.md` | user-stories | 30 |
| (no pattern match) | — | 0 |

### Signal 2 — Frontmatter (weight 20)

Read YAML frontmatter between the first two `---` lines. If `type:` field exists and equals one of `gap | design-spec | plan | prd | user-stories`, award 20 points to that role.

### Signal 3 — First-50-lines keywords (weight 30)

Read the first 50 non-blank lines of the MD (strip frontmatter first). For each role, award 30 points if **any of its top-level headings** (lines starting with `#` or `##`) contain one of the following keywords (case-insensitive):

| Role | Keywords |
|---|---|
| gap | "gap", "缺口", "缺失", "偏差" |
| design-spec | "design", "spec", "设计规范", "架构设计" |
| plan | "plan", "execution plan", "schedule", "计划", "排期" |
| prd | "prd", "requirements", "需求文档" |
| user-stories | "user stories", "user story", "用户故事" |

### Signal 4 — Structural signatures (weight 20)

Scan the full file for these structural markers (regex on lines, case-sensitive unless noted):

| Signature | Role | Points |
|---|---|---|
| At least 3 lines matching `/\bP[012]\b/` (priority tags) | gap | 20 |
| Heading or section containing "file change" (case-insensitive) AND a list of paths starting with `/`, `frontend/`, `backend/`, `src/`, or ending in common code extensions | design-spec | 20 |
| At least 2 headings matching `/^##?#?\s*(M|Milestone|Phase|P)\d/` | plan | 20 |
| At least 3 lines matching `/^(US|NFR)-\d+/` | prd | 10 per type (max 20) |
| At least 3 lines matching `/As a .+, I want .+, so that/` | user-stories | 20 |

### Aggregation

For each role, sum the matched signals (min 0, cap at 100). The **detected_role** is the role with the highest score.

### Thresholds

- **score ≥ 70**: high confidence, auto-accept.
- **40 ≤ score < 70**: medium. Record `alternatives` as all roles with score ≥ 40. Ask user to confirm.
- **score < 40**: label as `unknown` with the single highest-scoring role as a hint.

### LLM fallback

If `detected_role == unknown` or the top two roles are within 10 points of each other, invoke the LLM:

> Read this full MD file and classify it as one of [gap, design-spec, plan, prd, user-stories, unknown]. Return `{role, confidence_0_to_100, rationale_one_sentence}`.

Merge the LLM result: take the max score between rule-based and LLM. If LLM says `unknown` with high confidence, keep `unknown`.

### Tag override

If the caller provides `--tag role=path`, **skip all scoring for that path** and force the role. Still record evidence: `["forced by --tag"]`, score 100.

## Return format

Return the evidence array verbatim, plus a table formatted for the confirmation checkpoint. See `templates/role-confirmation.md` for the table format.
```

- [ ] **Step 9: Manual verify role-detector**

Open a Claude Code session in the prd2impl repo. Invoke the skill-0-ingest role-detector manually:

> Following `skills/skill-0-ingest/lib/role-detector.md`, detect the role of each file in `skills/skill-0-ingest/tests/fixtures/` and print the confirmation table.

Expected output: roughly matches `tests/expected/role-detection-table.txt` — five clear files at score ≥70, ambiguous.md at score < 40 labeled unknown.

Write actual output to a scratch file and diff:
```bash
# after running, save claude's output to actual.txt
diff <(grep -E '^\w' skills/skill-0-ingest/tests/expected/role-detection-table.txt | sort) <(grep -E '^\w' actual.txt | sort)
```

If fixture scores drift significantly from expected, adjust thresholds in `role-detector.md` or tighten the keyword lists.

- [ ] **Step 10: Commit**

```bash
git add skills/skill-0-ingest/lib/role-detector.md skills/skill-0-ingest/tests/fixtures/*.md skills/skill-0-ingest/tests/expected/role-detection-table.txt
git commit -m "feat(skill-0): role-detector with 4-signal scoring + 6 fixtures"
```

---

## Task 4: Implement gap-extractor

**Files:**
- Create: `skills/skill-0-ingest/lib/gap-extractor.md`
- Create: `skills/skill-0-ingest/tests/expected/clear-gap.gap-analysis.yaml`

- [ ] **Step 1: Write expected output for clear-gap fixture**

Write `skills/skill-0-ingest/tests/expected/clear-gap.gap-analysis.yaml`:

```yaml
gap_analysis:
  scan_date: "<today>"
  source_type: "ingested"
  source_files:
    - "skills/skill-0-ingest/tests/fixtures/clear-gap.md"

  summary:
    total_gaps: 2
    by_priority:
      P0: 2

  gaps:
    - id: GAP-001
      source_id: "A-①"
      source_file: "clear-gap.md"
      source_anchor: "a--missing-register-step-p0"
      description: "Missing register step"
      module: null
      priority: P0
      gap_type: missing
      existing_code: []
      missing_parts:
        - "add RegisterStep"
      estimated_effort: small
      depends_on_gaps: []

    - id: GAP-002
      source_id: "A-②"
      source_file: "clear-gap.md"
      source_anchor: "a--im-group-auto-creation-p0"
      description: "IM group auto-creation"
      module: null
      priority: P0
      gap_type: missing
      existing_code: []
      missing_parts:
        - "auto-create group + join agents"
      estimated_effort: small
      depends_on_gaps: []
```

- [ ] **Step 2: Write gap-extractor.md**

Write `skills/skill-0-ingest/lib/gap-extractor.md`:

```markdown
# gap-extractor

Extract structured gap entries from an MD classified as `gap`. Produce entries compatible with the `gap_analysis` YAML schema, with the three new `source_*` fields populated.

## Input

Single MD file path classified as `gap` by role-detector.

## Output

Partial `gap_analysis.yaml` content — the `gaps` array and `summary` object. The caller (SKILL.md main flow) merges multiple extractor outputs.

## Extraction rules

### Step 1 · Read full MD

Load the file. Strip frontmatter.

### Step 2 · Find gap items

A "gap item" is identified by any of these patterns, tried in order:

1. **Heading with priority tag**: `^#{2,4}\s+(?P<source_id>[\w\u2460-\u2473\u4e00-\u9fff-]+)\s+.+·\s*(?P<priority>P[012])\s*$`
   — e.g. `### A-① Missing register step · P0`
2. **Heading followed by priority on next line**: a heading, then within next 3 lines a standalone line matching `^\s*\*?\*?(P[012])\*?\*?`
3. **List-item with tag**: lines matching `^\s*[-*]\s+\*?\*?(?P<source_id>[\w\u2460-\u2473-]+)\*?\*?.+\*?\*?(?P<priority>P[012])\*?\*?`
4. **Table row**: row whose first cell matches the source_id pattern and contains a P0/P1/P2 column.

For each matched item, record:

- `source_id`: captured group (e.g. `A-①`, `B-⑦`, `S1`). If absent, auto-generate `ITEM-NNN`.
- `priority`: P0 / P1 / P2.
- `heading_text`: the full heading or list-item line, excluding markup.
- `section_slug`: lowercase heading with non-alphanum → `-`, consecutive `-` collapsed.

### Step 3 · Body extraction

For each item, collect lines until the next gap item, next same-or-higher-level heading, or end of file. From the body, extract:

- `description`: first non-empty sentence after the heading (strip priority tag and leading hyphen markers).
- `missing_parts`: bullet lines under a heading containing "fix", "修复", "missing", "缺失", OR bullets under keys like `**Fix**:`. Take each bullet verbatim (strip leading `-`/`*`/whitespace).
- `existing_code`: bullets or inline references under a key like `**Current**:`, `**现状**:`, `**Existing**:` that look like file paths (contain `/` or end in `.py/.ts/.tsx/.md/.yaml/.yml`).
- `gap_type`:
  - `missing` if the body contains "missing", "缺", "not implemented"
  - `partial` if contains "partial", "部分", "半" or both `existing_code` and `missing_parts` are non-empty
  - `outdated` if contains "outdated", "stale", "过期"
  - default: `missing`
- `estimated_effort`:
  - `small` if `len(missing_parts) <= 1`
  - `large` if `len(missing_parts) >= 5`
  - `medium` otherwise
- `module`: if the heading or body mentions a path prefix (e.g. `frontend/apps/admin-portal`), derive module from the last significant path segment (`admin-portal`). Otherwise `null`.

### Step 4 · ID assignment

Sort items by first-appearance order in the MD. Assign canonical IDs `GAP-001`, `GAP-002`, … sequentially. Keep the human `source_id` in the `source_id` field.

### Step 5 · Cross-reference within the same MD

Skip on this pass — filled by `cross-validator` later.

### Step 6 · Emit

For each item emit the full gap entry matching `schemas/gap-analysis.example.yaml` structure. Compute summary:

```yaml
summary:
  total_gaps: <count>
  by_priority:
    P0: <count>
    P1: <count>
    P2: <count>
```

Omit priority keys whose count is zero.

## Edge cases

- **No priority tag** on an otherwise gap-looking heading: skip (don't guess P0).
- **Source_id clashes** across multiple MD files: the canonical GAP-NNN differs so there's no collision; but the user might see `source_id: A-①` repeated. The `source_file` field disambiguates.
- **Very long body (>200 lines)**: take first 3 paragraphs only; record `source_anchor` so the user can jump back to full context.
```

- [ ] **Step 3: Manual verify gap-extractor**

In Claude Code, run:

> Following `skills/skill-0-ingest/lib/gap-extractor.md`, extract gaps from `skills/skill-0-ingest/tests/fixtures/clear-gap.md`. Output the YAML to a file and diff against `skills/skill-0-ingest/tests/expected/clear-gap.gap-analysis.yaml` (ignoring `scan_date`).

Expected: 2 gaps, both P0, source_id `A-①` and `A-②`. Diff (ignoring scan_date) should be empty or whitespace-only.

- [ ] **Step 4: Commit**

```bash
git add skills/skill-0-ingest/lib/gap-extractor.md skills/skill-0-ingest/tests/expected/clear-gap.gap-analysis.yaml
git commit -m "feat(skill-0): gap-extractor with priority + source_* field extraction"
```

---

## Task 5: Implement spec-extractor

**Files:**
- Create: `skills/skill-0-ingest/lib/spec-extractor.md`
- Create: `skills/skill-0-ingest/tests/expected/clear-spec.task-hints.yaml`

- [ ] **Step 1: Write expected output for clear-spec fixture**

Write `skills/skill-0-ingest/tests/expected/clear-spec.task-hints.yaml`:

```yaml
task_hints:
  source_files:
    - "skills/skill-0-ingest/tests/fixtures/clear-spec.md"

  file_changes:
    - path: "frontend/apps/admin-portal/src/components/shell/AdminShell.tsx"
      change_type: create
      purpose: "topbar + rail + canvas shell"
      source_anchor: "6-file-changes"
      related_gap_refs: []
    - path: "frontend/apps/admin-portal/src/components/AdminWorkspace.tsx"
      change_type: modify
      purpose: "slim down"
      source_anchor: "6-file-changes"
      related_gap_refs: []

  implementation_steps:
    - step: 1
      description: "Build shell"
      touches_files: []
      source_anchor: "9-implementation-order"
    - step: 2
      description: "Wire App.tsx"
      depends_on_steps: [1]
      touches_files: []
      source_anchor: "9-implementation-order"

  test_strategy:
    preserved_testids: []
    new_tests: []
    e2e_delta: null

  non_goals:
    - "No design-system changes"

  risks: []
```

- [ ] **Step 2: Write spec-extractor.md**

Write `skills/skill-0-ingest/lib/spec-extractor.md`:

```markdown
# spec-extractor

Extract structured task hints from an MD classified as `design-spec`. Produce content for `task-hints.yaml`.

## Input

Single MD file path classified as `design-spec`.

## Output

Partial `task_hints` block. Caller merges multiple into one `task-hints.yaml`.

## Extraction rules

### 1 · File changes

Find section whose heading contains "file change" (case-insensitive, e.g. `## 6. File Changes`). Capture `source_anchor` as the heading slug.

Within that section, identify sub-sections by heading text:

| Sub-heading keyword | change_type |
|---|---|
| "new", "create", "added", "新增" | create |
| "modify", "modified", "changed", "修改" | modify |
| "delete", "remove", "删除" | delete |
| "unchanged", "no change", "not changed", "不改" | no-change |

For each sub-section, extract bullet items of the form:

```
- `path/to/file` — purpose description
- `path/to/file`: purpose description
- **path/to/file** (purpose description)
```

Normalize:
- `path`: exact path captured (strip backticks/bold markers).
- `purpose`: everything after `—`, `:`, or parentheses, trimmed.
- `change_type`: from sub-heading.
- `source_anchor`: the parent "file changes" section slug (not sub-section).
- `related_gap_refs`: `[]` (cross-validator fills).

If a bullet has no purpose description, set `purpose: ""`.

### 2 · Implementation steps

Find section whose heading contains "implementation order", "implementation steps", "实施顺序", "执行顺序". Capture its slug as `source_anchor`.

Within that section, find a numbered list (items starting `^\s*(\d+)\.\s`). For each item N:

- `step`: N.
- `description`: list-item text (strip leading `N.` and whitespace).
- `depends_on_steps`: if description contains `(depends on M)`, `(依赖 M)`, `after N,M`, or `depends on steps [M, P]`, extract the numeric list.  Otherwise `[]`.
- `touches_files`: if description references `path/to/file` in backticks or matches a path pattern, extract them into a list. Otherwise `[]`.
- `source_anchor`: the parent section slug.

### 3 · Test strategy

Find section whose heading contains "test strategy", "testing", "测试策略". Extract:

- `preserved_testids`: any list item under "preserved", "保留" that looks like a `testid` (usually short alphanumeric with hyphens).
- `new_tests`: any list item under "new tests", "新增测试" matching `^- ?\`?(?P<name>[\w\.]+)\`?:\s*(?P<focus>.+)$`. Omit if missing.
- `e2e_delta`: the first sentence of any text about E2E delta; null if absent.

If the section is absent entirely, emit:
```yaml
test_strategy:
  preserved_testids: []
  new_tests: []
  e2e_delta: null
```

### 4 · Non-goals

Find section whose heading contains "non-goals", "not doing", "non-scope", "非目标". Collect each bullet verbatim (strip leading `-`/`*`).

### 5 · Risks

Find section whose heading contains "risks", "open risks", "风险". Extract bullets or table rows matching `risk: ..., mitigation: ...` or parse structured entries:

```
- **risk**: ...
  **mitigation**: ...
```

If section absent, emit `risks: []`.

## Edge cases

- **File-change section uses table instead of bullets**: parse table rows; `| path | purpose |` header is ignored.
- **Step description spans multiple lines**: concatenate with spaces until the next numbered item.
- **Path with spaces in backticks**: preserve the path including spaces.
- **No implementation-order section**: `implementation_steps: []`.
- **Missing all four sections**: skill aborts with "not a design spec — no extractable structure" and the caller should re-classify via `--tag`.
```

- [ ] **Step 3: Manual verify spec-extractor**

Run:

> Following `skills/skill-0-ingest/lib/spec-extractor.md`, extract task hints from `skills/skill-0-ingest/tests/fixtures/clear-spec.md`. Diff against `skills/skill-0-ingest/tests/expected/clear-spec.task-hints.yaml`.

Expected: 2 file_changes, 2 implementation_steps, 1 non_goal, 0 risks. Diff should be empty.

- [ ] **Step 4: Commit**

```bash
git add skills/skill-0-ingest/lib/spec-extractor.md skills/skill-0-ingest/tests/expected/clear-spec.task-hints.yaml
git commit -m "feat(skill-0): spec-extractor with 5-section extraction"
```

---

## Task 6: Implement prd-extractor

**Files:**
- Create: `skills/skill-0-ingest/lib/prd-extractor.md`
- Create: `skills/skill-0-ingest/tests/expected/clear-plan.prd-structure.yaml`
- Create: `skills/skill-0-ingest/tests/expected/clear-prd.prd-structure.yaml`
- Create: `skills/skill-0-ingest/tests/expected/clear-stories.prd-structure.yaml`

- [ ] **Step 1: Write expected — clear-plan.prd-structure.yaml**

Write `skills/skill-0-ingest/tests/expected/clear-plan.prd-structure.yaml`:

```yaml
prd_structure:
  source_type: "ingested"
  source_files:
    - "skills/skill-0-ingest/tests/fixtures/clear-plan.md"

  modules: []
  user_stories: []
  nfrs: []

  constraints:
    - id: CON-01
      type: deployment
      description: "M1: Wizard done — 2026-04-20"
      rationale: "schedule milestone"
      prd_ref: "clear-plan.md#milestones"
    - id: CON-02
      type: deployment
      description: "M2: Ops done — 2026-04-22"
      rationale: "schedule milestone"
      prd_ref: "clear-plan.md#milestones"

  external_deps: []
```

- [ ] **Step 2: Write expected — clear-prd.prd-structure.yaml**

Write `skills/skill-0-ingest/tests/expected/clear-prd.prd-structure.yaml`:

```yaml
prd_structure:
  source_type: "ingested"
  source_files:
    - "skills/skill-0-ingest/tests/fixtures/clear-prd.md"

  modules:
    - id: MOD-01
      name: "Conversation"
      description: "Handles chat routing."
      prd_sections: ["§3 Modules"]
      sub_modules: []

  user_stories:
    - id: US-001
      module: MOD-01
      persona: "operator"
      action: "view live chat"
      goal: null
      acceptance_criteria:
        - "AC-001: messages appear in 500ms"
      prd_ref: "§4 User Stories"

  nfrs:
    - id: NFR-01
      category: performance
      requirement: "API p95 < 200ms"
      metric: "p95 latency"
      target: "200ms"
      prd_ref: "§6 NFRs"

  constraints: []
  external_deps: []
```

- [ ] **Step 3: Write expected — clear-stories.prd-structure.yaml**

Write `skills/skill-0-ingest/tests/expected/clear-stories.prd-structure.yaml`:

```yaml
prd_structure:
  source_type: "ingested"
  source_files:
    - "skills/skill-0-ingest/tests/fixtures/clear-stories.md"

  modules: []

  user_stories:
    - id: US-010
      module: null
      persona: "customer"
      action: "click a floating button on the merchant's site"
      goal: "start a chat without leaving"
      acceptance_criteria: []
      prd_ref: "clear-stories.md#us-010"
    - id: US-011
      module: null
      persona: "operator"
      action: "see a squad sidebar"
      goal: "see all active customers"
      acceptance_criteria: []
      prd_ref: "clear-stories.md#us-011"

  nfrs: []
  constraints: []
  external_deps: []
```

- [ ] **Step 4: Write prd-extractor.md**

Write `skills/skill-0-ingest/lib/prd-extractor.md`:

```markdown
# prd-extractor

Extract `prd_structure` content from an MD classified as `prd`, `plan`, or `user-stories`. Reuses most of skill-1's extraction logic; for `plan` type the extraction is narrower.

## Input

Single MD file path + its detected role (one of: `prd`, `plan`, `user-stories`).

## Output

Partial `prd_structure` content. Caller merges.

## Extraction by role

### Role = prd

Apply skill-1's full extraction logic (see `skills/skill-1-prd-analyze/SKILL.md` §"Extract Structured Data" and `skills/skill-1-prd-analyze/references/extraction-guide.md`). Extract all of:

- modules
- user_stories
- nfrs
- constraints
- external_deps

Tag top-level output `source_type: "ingested"` (distinct from skill-1's output which uses default / absent `source_type`).

### Role = user-stories

Extract **only** user_stories. Use the pattern:

```
^##\s+US-(\d+)$
```
as the story heading, with the body matching:

```
As a (?P<persona>.+), I want (?P<action>.+), so that (?P<goal>.+)
```

For each story:
- `id`: `US-<number>`
- `persona`, `action`, `goal`: captured groups (no trailing period)
- `acceptance_criteria`: `[]`
- `prd_ref`: `<source_file>#us-<number>`
- `module`: `null`

Emit `modules: []`, `nfrs: []`, `constraints: []`, `external_deps: []`.

### Role = plan

Extract **only** constraints, derived from milestones and schedule entries. Patterns:

- Heading "Milestones" or "milestones" → each bullet becomes a constraint:
  - `type: deployment`
  - `description`: the bullet text verbatim
  - `rationale: "schedule milestone"`
  - `prd_ref`: `<source_file>#milestones`
- Heading "Phase breakdown" or similar → skip (phases are task-level, handled by skill-4).

Assign `CON-01`, `CON-02`, … sequentially.

Emit `modules: []`, `user_stories: []`, `nfrs: []`, `external_deps: []`.

## Edge cases

- **PRD with no modules but many NFRs**: emit `modules: []`, still extract NFRs.
- **Plan with no milestones**: emit `constraints: []` (empty output — caller may warn).
- **Stories file without "As a X, I want Y, so that Z" structure**: fall back to skill-1 user-story extraction.
```

- [ ] **Step 5: Manual verify prd-extractor for each role**

Run three verifications:

**5a.** For clear-plan.md (role=plan):
> Following prd-extractor.md, role=plan, extract from clear-plan.md. Diff against clear-plan.prd-structure.yaml.

**5b.** For clear-prd.md (role=prd):
> Following prd-extractor.md, role=prd, extract from clear-prd.md. Diff against clear-prd.prd-structure.yaml.

**5c.** For clear-stories.md (role=user-stories):
> Following prd-extractor.md, role=user-stories, extract from clear-stories.md. Diff against clear-stories.prd-structure.yaml.

All three diffs should be empty or trivial whitespace.

- [ ] **Step 6: Commit**

```bash
git add skills/skill-0-ingest/lib/prd-extractor.md skills/skill-0-ingest/tests/expected/clear-plan.prd-structure.yaml skills/skill-0-ingest/tests/expected/clear-prd.prd-structure.yaml skills/skill-0-ingest/tests/expected/clear-stories.prd-structure.yaml
git commit -m "feat(skill-0): prd-extractor for prd/plan/user-stories roles"
```

---

## Task 7: Implement cross-validator

**Files:**
- Create: `skills/skill-0-ingest/lib/cross-validator.md`
- Create: `skills/skill-0-ingest/tests/fixtures/cross-val-orphan.md`
- Create: `skills/skill-0-ingest/tests/fixtures/cross-val-p0-uncovered.md`
- Create: `skills/skill-0-ingest/tests/fixtures/cross-val-dangling-step.md`
- Create: `skills/skill-0-ingest/tests/fixtures/cross-val-nongoal-conflict.md`
- Create: `skills/skill-0-ingest/tests/fixtures/cross-val-dead-anchor.md`
- Create: `skills/skill-0-ingest/tests/expected/cross-val-warnings.txt`

- [ ] **Step 1: Write fixtures for each cross-validation rule**

Write `skills/skill-0-ingest/tests/fixtures/cross-val-orphan.md`:

```markdown
# Orphan Spec Change

## 6. File Changes

### Modified
- `src/weird/orphan.py` — does something unrelated to any known gap
```

(No gap MD references this file — cross-validator should flag it.)

Write `skills/skill-0-ingest/tests/fixtures/cross-val-p0-uncovered.md`:

```markdown
# P0-Uncovered Gap

## A-① · P0
- **Fix**: massive work nobody planned
```

(Gap MD with one P0 item, and a paired design spec that doesn't cover it. Caller provides both to cross-validator. See Step 3.)

Write `skills/skill-0-ingest/tests/fixtures/cross-val-dangling-step.md`:

```markdown
# Dangling Step

## 6. File Changes

### New
- `src/a.py` — hello

## 9. Implementation Order

1. Create `src/a.py`
2. Edit `src/b.py` — but b.py is not in file changes!
```

Write `skills/skill-0-ingest/tests/fixtures/cross-val-nongoal-conflict.md`:

```markdown
# Non-Goal Conflict

## 2. Non-Goals
- No changes to `tokens.css`

## 6. File Changes

### Modified
- `packages/design-system/tokens.css` — tweak a token
```

Write `skills/skill-0-ingest/tests/fixtures/cross-val-dead-anchor.md`:

```markdown
# Dead Anchor — edit this file AFTER ingest to remove the heading

## 6. File Changes
- `src/a.py` — hello
```

- [ ] **Step 2: Write expected warnings output**

Write `skills/skill-0-ingest/tests/expected/cross-val-warnings.txt`:

```
Cross-validation Warnings
=========================
Orphan spec change (1)
  - src/weird/orphan.py — no gap in any input MD references this

P0 gap with no implementation plan (1)
  - GAP-001 (A-①) "massive work nobody planned"

Step references undeclared file (1)
  - step 2 "Edit `src/b.py`" — b.py not in file_changes

Non-goal conflict: FATAL (1)
  - non_goal "No changes to tokens.css" conflicts with file_change path packages/design-system/tokens.css

Dead source_anchor (1)
  - file_change for src/a.py references anchor that no longer exists in cross-val-dead-anchor.md
```

- [ ] **Step 3: Write cross-validator.md**

Write `skills/skill-0-ingest/lib/cross-validator.md`:

```markdown
# cross-validator

Run 5 consistency checks against the in-memory gap-analysis, task-hints, and prd-structure produced by extractors. Report warnings; abort on fatal errors.

## Input

- `gap_analysis` (dict)
- `task_hints` (dict)
- `prd_structure` (dict)
- Original source MD files (for anchor validation)

## Output

- `warnings: []` — non-fatal issues
- `errors: []` — fatal, aborts Phase 4
- Possibly mutated input dicts (e.g. backfilled `related_gap_refs`)

## Checks

### Rule 1 — Every file_change relates to a gap

For each `file_change` in `task_hints.file_changes` where `related_gap_refs` is empty:

1. Read the source MD file named in `task_hints.source_files` that matches this file_change's `source_anchor` origin.
2. Locate the section with the heading slug `source_anchor`.
3. Within that section's text, search for any `GAP-\d+` pattern OR any of the known `source_id` values from `gap_analysis.gaps[].source_id` (e.g. `A-①`, `B-⑦`).
4. If found, backfill `related_gap_refs` with the matching canonical GAP-IDs. Done.
5. If not found, add warning: `orphan spec change: {file_change.path}`.

Severity: Warning.

### Rule 2 — Every P0 gap is covered by spec

For each gap in `gap_analysis.gaps` where `priority == "P0"`:

- Check whether `task_hints.file_changes[].related_gap_refs` contains this GAP-ID (after Rule 1 has run).
- If not found, add warning: `P0 gap with no implementation plan: {gap.id} ({gap.source_id}) "{gap.description}"`.

Severity: Warning.

### Rule 3 — implementation_steps.touches_files ⊆ file_changes.path

Build `declared_paths = set(task_hints.file_changes[].path)`.

For each step in `task_hints.implementation_steps`:

- Build `used_paths = set(step.touches_files)`.
- Any path in `used_paths - declared_paths` triggers: `step references undeclared file: step {step.step} "{step.description}" references {path}`.

Severity: Warning.

### Rule 4 — non_goals don't contradict file_changes

For each `non_goal` in `task_hints.non_goals`:

- Extract file-like tokens from the non_goal text (any token matching `[\w/.\-]+\.(py|ts|tsx|js|jsx|css|yaml|yml|md|json)` or bare word matching known design-system markers like `tokens.css`, `components.css`).
- For each extracted token, check `task_hints.file_changes[].path`:
  - If any file_change path ends with or equals the token AND `change_type != "no-change"`:
    - Add error: `non-goal conflict: non-goal "{non_goal}" forbids changes to {token} but file_change modifies {path}`.

Severity: **Fatal**. Aborts Phase 4.

### Rule 5 — Source anchors resolve to real headings

For each `source_anchor` in gap_analysis.gaps and task_hints (file_changes, implementation_steps):

- Open the referenced source MD.
- Compute the set of all heading slugs in that MD (apply same slugification rule as extractors).
- If the anchor is not in the set, add warning: `dead anchor: {source_file} has no heading slug {anchor}`.

Severity: Warning.

## Emit order

After running all 5 rules, sort output:

1. Errors first (fatal).
2. Warnings grouped by rule.

Print formatted table (see `tests/expected/cross-val-warnings.txt` for format).

If any errors, return `{ok: false, errors, warnings}`. Caller aborts.
If only warnings, return `{ok: true, warnings}`. Caller prompts user `y/n`.

## Return schema

```yaml
result:
  ok: true | false
  warnings:
    - rule: rule-1-orphan-spec
      message: "orphan spec change: src/weird/orphan.py"
  errors:
    - rule: rule-4-nongoal-conflict
      message: "non-goal conflict: ..."
```
```

- [ ] **Step 4: Manual verify cross-validator**

For each fixture, construct the required inputs (gap_analysis + task_hints + source MD) and run cross-validator:

```bash
# Example: cross-val-orphan.md — run spec-extractor first, then feed its output
# plus an empty gap_analysis into cross-validator
```

Open Claude Code:

> For each fixture in `skills/skill-0-ingest/tests/fixtures/cross-val-*.md`:
> 1. Run the relevant extractor(s).
> 2. Run cross-validator on the combined result.
> 3. Collect the warning or error output.
>
> After all 5, diff the combined output against `skills/skill-0-ingest/tests/expected/cross-val-warnings.txt`.

Expected: each fixture trips exactly the rule it's named for. `cross-val-nongoal-conflict.md` produces an error (fatal); others produce warnings only. The dead-anchor test requires editing the MD after ingest — skip this one unless you want to perform the manual edit; confirm the rule is coded correctly by inspection.

- [ ] **Step 5: Commit**

```bash
git add skills/skill-0-ingest/lib/cross-validator.md skills/skill-0-ingest/tests/fixtures/cross-val-*.md skills/skill-0-ingest/tests/expected/cross-val-warnings.txt
git commit -m "feat(skill-0): cross-validator with 5 consistency rules"
```

---

## Task 8: Wire SKILL.md main flow

**Files:**
- Modify: `skills/skill-0-ingest/SKILL.md`
- Create: `skills/skill-0-ingest/templates/role-confirmation.md`

- [ ] **Step 1: Write the role-confirmation template**

Write `skills/skill-0-ingest/templates/role-confirmation.md`:

```markdown
Role Detection Results
======================
{{table}}

{{medium_confidence_section}}

Please confirm classification. Enter one of:
  > accept                                    # accept all suggestions
  > set <filename>=<role>                     # override one file
  > drop <filename>                           # exclude file from ingest
  > tag <filename> <role>                     # same as set (alias)
  > abort                                     # cancel ingest

(If score < 40 for a file and you don't `tag` it, it will be dropped with a warning.)
```

- [ ] **Step 2: Write full SKILL.md**

Overwrite `skills/skill-0-ingest/SKILL.md`:

```markdown
---
name: ingest-docs
description: "Ingest multiple existing Markdown documents (gap analyses, design specs, plans) and produce the YAML artifacts the rest of the prd2impl pipeline expects. Use when user already has hand-written intermediate docs and wants to skip straight to /task-gen, or says 'ingest docs', 'import these files', '/ingest-docs'."
---

# Skill 0: Ingest Docs

<SUBAGENT-STOP>
If you were dispatched as a subagent to execute a specific task, skip this skill.
</SUBAGENT-STOP>

Ingest multiple human-written Markdown documents and produce the YAML artifacts downstream prd2impl skills consume. Supports gap analyses, design specs, plans, PRDs, and user-stories documents.

## Trigger

- User runs `/ingest-docs <file1> <file2> ...`
- User says "ingest docs", "import these files", "bridge these MDs into the pipeline"
- Project has existing analysis MDs and user wants to skip `/prd-analyze` and `/gap-scan`

## Input

- **Required**: One or more MD file paths.
- **Optional**: `--tag <role>=<path>` overrides (repeatable). Forces that file to the given role.

Example invocations:

```
/ingest-docs docs/plans/2026-04-18-prd-full-journey-gap.md \
             docs/superpowers/specs/2026-04-18-admin-portal-web-layout-design.md \
             docs/plans/2026-04-18-admin-portal-web-layout.md

/ingest-docs docs/foo.md docs/bar.md --tag spec=docs/foo.md
```

## Execution flow

### Phase 1 — Role detection

1. For each input path, verify file exists. Abort with error listing missing paths if any.
2. Apply `--tag` overrides first (record them as `forced` in evidence).
3. For each remaining path, run `lib/role-detector.md`.
4. Collect results. Render confirmation table using `templates/role-confirmation.md`.
5. **HUMAN REVIEW CHECKPOINT 1**: print table, ask user to confirm or override.
6. Apply user's adjustments. Drop any path still at score < 40 with no tag; warn.
7. If zero paths remain classified, abort with instruction to use `--tag`.

### Phase 2 — Extraction

Partition the confirmed list by role:

- `gap` paths → run `lib/gap-extractor.md` on each, merge results into one `gap_analysis.gaps` array. Reassign canonical GAP-IDs globally (sort by source_file then source appearance order).
- `design-spec` paths → run `lib/spec-extractor.md` on each, merge results into one `task_hints` block (concatenate file_changes and implementation_steps, renumber steps globally, merge non_goals deduplicated, merge risks).
- `prd` / `plan` / `user-stories` paths → run `lib/prd-extractor.md` with the appropriate role, merge results into one `prd_structure` block. Reassign MOD/US/NFR/CON IDs globally.

Collect all three in memory. Do not write yet.

### Phase 3 — Cross-validation

Run `lib/cross-validator.md` against the in-memory data + original MD files.

Backfill any `related_gap_refs` the validator resolves.

Print the warnings/errors table.

If any errors: abort. No files written. Exit with remediation instructions (edit source MDs, re-run).

If warnings only:

**HUMAN REVIEW CHECKPOINT 2**: ask `y/n` to proceed despite warnings.

### Phase 4 — Write + summary

1. Determine output paths using today's date:
   - `docs/plans/{YYYY-MM-DD}-gap-analysis.yaml`
   - `docs/plans/{YYYY-MM-DD}-task-hints.yaml`
   - `docs/plans/{YYYY-MM-DD}-prd-structure.yaml`
2. If any path already exists, append `-v2`, `-v3`, etc. until a free name is found.
3. Write each YAML using the canonical key ordering from the example files in `schemas/`.
4. Skip writing a YAML file if its content is "empty" (no gaps / no file_changes / no modules+stories+nfrs+constraints).
5. Print summary:

```
Ingest complete.
================
Inputs:
  - {file1} (role={role})
  - ...

Outputs:
  - docs/plans/{date}-gap-analysis.yaml  ({N} gaps)
  - docs/plans/{date}-task-hints.yaml    ({M} file_changes, {K} steps)
  - docs/plans/{date}-prd-structure.yaml ({P} modules, {Q} stories, {R} constraints)

Warnings: {W}
Next: run /task-gen to generate tasks.yaml from these artifacts.
```

**HUMAN REVIEW CHECKPOINT 3**: final confirmation — does summary look right, ready for `/task-gen`?

## Input validation

- File not found: abort, list missing paths.
- File is not `.md`: warn but try to parse (role-detector may identify or drop).
- File is a directory: abort, not supported.
- Remote URL: abort, not supported.

## Backward compatibility

- The `gap-analysis.yaml` this skill produces has `source_type: "ingested"` at the top level; existing `/gap-scan` output does not (undefined ≡ `"scanned"`).
- `skill-3-task-gen` reads both the same way; the `source_type` field is metadata only.

## Relationship to other skills

- Alternative entry to `/prd-analyze` (skill-1). Run one or the other; don't mix for the same project run.
- Output feeds directly into `/task-gen` (skill-3). skill-3 gains optional `task-hints.yaml` input.
- `/gap-scan` (skill-2) is skipped by this entry; its output is synthesized from the ingested gap MD.

## Examples of ambiguous inputs

- A file with sections "Gap List" AND "Implementation Order" — role-detector may score both `gap` and `design-spec` high. Medium-confidence handling kicks in; user confirms.
- A plan MD that lists tasks by file path — role-detector sees "plan" keywords and "file changes" section. User should tag as `design-spec` if the file lists are authoritative; otherwise tag as `plan`.
```

- [ ] **Step 3: Manual verify SKILL.md with simulated invocation**

Run a dry-run in Claude Code with the clear fixtures:

> Following `skills/skill-0-ingest/SKILL.md`, run `/ingest-docs` on `skills/skill-0-ingest/tests/fixtures/clear-gap.md skills/skill-0-ingest/tests/fixtures/clear-spec.md skills/skill-0-ingest/tests/fixtures/clear-plan.md`. Print each phase's output. Do not write YAML files — just show what would be written.

Expected flow:
1. Phase 1 confirmation table: 3 files, all high-confidence.
2. Phase 2 extraction: 2 gaps, 2 file_changes + 2 steps + 1 non_goal, 2 constraints.
3. Phase 3 cross-validation: 2 orphan warnings (file_changes don't reference any gap) + 2 P0-uncovered warnings.
4. Phase 4 proposed output paths.

- [ ] **Step 4: Commit**

```bash
git add skills/skill-0-ingest/SKILL.md skills/skill-0-ingest/templates/role-confirmation.md
git commit -m "feat(skill-0): wire main SKILL.md with 4-phase flow"
```

---

## Task 9: Modify skill-3-task-gen for optional task-hints

**Files:**
- Modify: `skills/skill-3-task-gen/SKILL.md`

- [ ] **Step 1: Read current skill-3 input section**

Open `skills/skill-3-task-gen/SKILL.md`. Locate the `## Input` section (around lines 20-25).

- [ ] **Step 2: Update Input section to note optional task-hints.yaml**

Find:

```markdown
## Input

- **Required**: `docs/plans/*-gap-analysis.yaml` (output from skill-2)
- **Required**: `docs/plans/*-prd-structure.yaml` (output from skill-1)
- **Optional**: `docs/plans/project.yaml` (team configuration)
- **Optional**: Existing `docs/plans/tasks.yaml` (for incremental updates)
```

Replace with:

```markdown
## Input

- **Required**: `docs/plans/*-gap-analysis.yaml` (output from skill-2 or skill-0)
- **Required**: `docs/plans/*-prd-structure.yaml` (output from skill-1 or skill-0)
- **Optional**: `docs/plans/*-task-hints.yaml` (output from skill-0 only; see §2.5)
- **Optional**: `docs/plans/project.yaml` (team configuration)
- **Optional**: Existing `docs/plans/tasks.yaml` (for incremental updates)
```

- [ ] **Step 3: Insert new §2.5 "task-hints integration"**

After the existing `### Step 2: Generate Tasks` section and before `### Step 3: Dependency Analysis`, insert a new section `### Step 2.5: Apply task-hints (if present)`:

```markdown
### Step 2.5: Apply task-hints (if present)

If `docs/plans/*-task-hints.yaml` exists, load it. This file carries human-authored design decisions that should constrain task generation. Apply these three behaviors:

**Behavior 1 — Deliverables from file_changes:**

For each `file_change` in `task_hints.file_changes`:
  - Identify the **primary gap** as the first entry in `related_gap_refs` (if empty, treat as a "support" file_change — see Behavior 3).
  - Find the task generated in Step 2 for that gap.
  - Append the file_change to that task's `deliverables`:
    ```yaml
    - path: "{file_change.path}"
      type: code                      # code | test | doc | config (infer from path)
    ```
    Type inference: `.test.ts`, `_test.py`, `tests/`, `test_` → test. `.md`, `docs/` → doc. `.yaml`, `.json` under `config/` → config. Else code.
  - If the file_change has additional `related_gap_refs[1:]`, record them under the task's `cross_references` field:
    ```yaml
    cross_references:
      - GAP-002
      - GAP-003
    ```

**Behavior 2 — depends_on from implementation_steps:**

For each task generated in Step 2:
  - Find the set of implementation_step indices whose `touches_files` overlap any of this task's deliverables. Call this set `my_steps`.
  - For each step in `my_steps`, look at its `depends_on_steps` → find tasks whose deliverables overlap those steps' `touches_files` → add those tasks to this task's `depends_on` list.
  - Deduplicate.

**Behavior 3 — non_goals as hard boundary:**

For each task generated in Step 2:
  - For each `non_goal` in `task_hints.non_goals`:
    - Extract file-like tokens from non_goal text (pattern: `[\w/.\-]+\.(py|ts|tsx|js|jsx|css|yaml|yml|md|json)` or known design-system markers like `tokens.css`).
    - If any of this task's deliverable paths end with or equal a non_goal token, **reject this task**. Replace it with a log entry: "Task for GAP-NNN rejected per non_goal '{non_goal}'".
  - Task rejection is recorded in the final summary; the gap remains in gap-analysis.yaml but gets no task.

**Support file_changes (empty related_gap_refs):**

File_changes with no related gaps are bundled into a single "support task" per module:

```yaml
- id: T0-support-{module}
  name: "Support infrastructure changes for {module}"
  type: green
  deliverables:
    - path: "{file_change.path}"
      type: code
  # no gap_ref
```

This surfaces necessary supporting work (e.g. CSS refactors, shared utilities) without forcing a synthetic gap.
```

- [ ] **Step 4: Update summary section**

Find the `### Step 6: Statistics & Warnings` section. Add to the `warnings` list examples:

```markdown
  - "3 tasks rejected per non_goals from task-hints.yaml"
  - "5 file_changes without gap refs grouped into support tasks"
```

- [ ] **Step 5: Update Human Review Checkpoint message**

In `### Step 8: Human Review Checkpoint`, add to the review questions:

```markdown
> 5. If task-hints was present: are the auto-generated `cross_references` and `support tasks` reasonable?
```

- [ ] **Step 6: Verify backward compatibility by inspection**

Read the entire modified `skill-3-task-gen/SKILL.md`. Confirm:
- The Step 2.5 text explicitly says "If task-hints.yaml exists" — gated.
- Behavior 1, 2, 3 all key off `task_hints.*` — when dict is empty/absent, none of them fire.
- Step 2's existing logic is unchanged.
- Deliverables, depends_on, and rejections are all **additive** to the existing schema.

- [ ] **Step 7: Commit**

```bash
git add skills/skill-3-task-gen/SKILL.md
git commit -m "feat(skill-3): optional task-hints.yaml input with 3 gated behaviors"
```

---

## Task 10: Register /ingest-docs in using-prd2impl router

**Files:**
- Modify: `skills/using-prd2impl/SKILL.md`

- [ ] **Step 1: Read current router SKILL.md**

Open `skills/using-prd2impl/SKILL.md`. Locate the `## Routing Rules` section (around lines 45-60) and the pipeline overview section.

- [ ] **Step 2: Update Pipeline Overview section**

Find:

```markdown
## Pipeline Overview

```
Phase 1: Upstream Analysis (PRD → Tasks)
  skill-1  /prd-analyze     — Structured PRD extraction
  skill-2  /gap-scan        — Codebase vs PRD gap analysis
  skill-3  /task-gen        — Task generation with dependencies
  skill-4  /plan-schedule   — Execution plan & batch scheduling
```

Replace with:

```markdown
## Pipeline Overview

```
Phase 1: Upstream Analysis

  Entry A (from a PRD):
    skill-1  /prd-analyze     — Structured PRD extraction
    skill-2  /gap-scan        — Codebase vs PRD gap analysis

  Entry B (from existing docs):
    skill-0  /ingest-docs     — Ingest multiple hand-written MDs
                                produces prd-structure + gap-analysis + task-hints

  Converge:
    skill-3  /task-gen        — Task generation with dependencies
    skill-4  /plan-schedule   — Execution plan & batch scheduling
```

- [ ] **Step 3: Update Routing Rules table**

Find the routing rules table. Add the row for skill-0 at the top:

```markdown
| User Intent | Skill |
|-------------|-------|
| "Ingest these docs", "import existing MDs", "/ingest-docs file1.md file2.md" | skill-0-ingest |
| "Analyze this PRD", "parse requirements", "read the PRD" | skill-1-prd-analyze |
| ...
```

- [ ] **Step 4: Add Quick Start section for Entry B**

Find the `## Quick Start` section. Add a new subsection after the existing "new project from PRD" block:

```markdown
For a **project that already has hand-written analysis docs**:

```
/ingest-docs docs/plans/gap-xxx.md docs/specs/design-yyy.md [...]  → 3 YAMLs
/task-gen                                                            → tasks.yaml
/plan-schedule                                                       → batches, milestones
```

Skip `/prd-analyze` and `/gap-scan` — they're replaced by `/ingest-docs`.
```

- [ ] **Step 5: Add mutual exclusion note**

After the Entry B Quick Start, add:

```markdown
### Entry A vs Entry B

Choose one entry point per project run:

- **Entry A** (`/prd-analyze` → `/gap-scan`): Start from a PRD document; let the pipeline discover what's already implemented.
- **Entry B** (`/ingest-docs`): Start from human-written gap + spec documents; skip to task generation.

If you have both a PRD and hand-written gap docs, prefer Entry A — the PRD is your source of truth. Save the gap docs for reference or feed them into a second ingest run with `--tag gap=...`.
```

- [ ] **Step 6: Commit**

```bash
git add skills/using-prd2impl/SKILL.md
git commit -m "feat(router): register skill-0-ingest as Entry B alternative"
```

---

## Task 11: Update README with Entry B documentation

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update skill list**

Find the skill list in the "Verify installation" section (around lines 33-48). Add the skill-0 entry at the top:

```markdown
```
prd2impl:ingest-docs       — Ingest multiple existing MDs (alternative entry)
prd2impl:prd-analyze       — Structured PRD extraction
prd2impl:gap-scan           — Codebase vs PRD gap analysis
...
```
```

- [ ] **Step 2: Add Entry B Quick Start**

Find the `## Quick Start` section. After "### New project from PRD", add:

```markdown
### Existing project with hand-written analysis docs

```
/ingest-docs docs/plans/gap.md docs/specs/design.md    # Bridge to pipeline
/task-gen                                              # Generate tasks
/plan-schedule                                         # Create execution plan
```

Use this when you already have gap analyses, design specs, or plans and want
to skip `/prd-analyze` and `/gap-scan`. The skill auto-detects each file's
role (gap / design-spec / plan / prd / user-stories) with a confirmation
step; fall back to `--tag role=path` if auto-detect fails.
```

- [ ] **Step 3: Update Pipeline Overview diagram**

Find the ASCII diagram in "## Pipeline Overview" (around lines 87-110). Replace the "Phase 1" block with:

```
Phase 1: Upstream Analysis (two entries converging into /task-gen)

Entry A — PRD source:
┌─────────────┐    ┌──────────┐
│/prd-analyze │ →  │/gap-scan │
│ Skill 1     │    │ Skill 2  │
└──────┬──────┘    └─────┬────┘
       ↓                 ↓
       └──┬──────────────┘
          ↓
Entry B — Existing docs:                   ┌──────────┐    ┌──────────────┐
┌──────────────┐                           │/task-gen │ →  │/plan-schedule│
│/ingest-docs  │ ───────────────────────→  │ Skill 3  │    │ Skill 4      │
│ Skill 0      │                           │ Tasks+deps│    │ Batches+time │
└──────────────┘                           └──────────┘    └──────────────┘
       ↓ review                             ↓ review        ↓ review
```

- [ ] **Step 4: Update Data Flow section**

Find the "## Data Flow" section. Update to note the new artifact:

```markdown
## Data Flow

This plugin uses **YAML as source of truth** with markdown as human-readable views:

```
PRD document (Entry A) OR multiple MDs (Entry B)
  → prd-structure.yaml     (Skill 1 or Skill 0)
  → gap-analysis.yaml      (Skill 2 or Skill 0)
  → task-hints.yaml        (Skill 0 only; optional but recommended)
  → tasks.yaml             (Skill 3, source of truth for all tasks)
  → execution-plan.yaml    (Skill 4)
  → task-status.md         (auto-generated view from tasks.yaml)
  ...
```

When `task-hints.yaml` is present, skill-3 uses it to align task deliverables,
dependencies, and non-goal boundaries with human-authored design decisions.
```

- [ ] **Step 5: Update Directory Structure**

Find `## Directory Structure`. Update the `skills/` tree:

```
├── skills/
│   ├── using-prd2impl/          # Router skill (entry point)
│   ├── skill-0-ingest/          # Existing-docs ingest (alternative entry)
│   │   ├── SKILL.md
│   │   ├── lib/                 # role-detector, gap-/spec-/prd-extractor, cross-validator
│   │   ├── schemas/             # task-hints + gap-analysis examples
│   │   ├── templates/
│   │   └── tests/               # fixtures + expected outputs
│   ├── skill-1-prd-analyze/     # PRD structured extraction
│   ...
```

- [ ] **Step 6: Commit**

```bash
git add README.md
git commit -m "docs(readme): document skill-0-ingest and Entry A/B pipeline"
```

---

## Task 12: End-to-end acceptance test with real AutoService files

**Files:**
- Create: `skills/skill-0-ingest/tests/e2e-autoservice.md` (results notes)

- [ ] **Step 1: Copy the three real AutoService MDs into fixture dir as reference**

Copy (do NOT modify the originals):

```bash
cp "D:/Work/h2os.cloud/AutoService-dev-a/docs/plans/2026-04-18-prd-full-journey-gap.md" \
   skills/skill-0-ingest/tests/fixtures/autoservice-gap.md

cp "D:/Work/h2os.cloud/AutoService-dev-a/docs/superpowers/specs/2026-04-18-admin-portal-web-layout-design.md" \
   skills/skill-0-ingest/tests/fixtures/autoservice-design.md

# admin-portal-web-layout.md may not exist yet; note and skip
```

Verify:

```bash
ls skills/skill-0-ingest/tests/fixtures/autoservice-*.md
wc -l skills/skill-0-ingest/tests/fixtures/autoservice-*.md
```

Expected: 2 files, each ~200-500 lines.

- [ ] **Step 2: Run full /ingest-docs flow**

Open Claude Code in the prd2impl repo. Invoke:

```
/ingest-docs skills/skill-0-ingest/tests/fixtures/autoservice-gap.md skills/skill-0-ingest/tests/fixtures/autoservice-design.md
```

Walk through all 4 phases:

- Phase 1 confirmation: expect `autoservice-gap.md` as `gap` (score ≥80), `autoservice-design.md` as `design-spec` (score ≥80).
- Phase 2 extraction:
  - gap-extractor should produce **~17 gaps** split **P0=6 / P1=6 / P2=5** (matching the source MD's own summary table).
  - spec-extractor should produce **~12 file_changes** (from §6 of the design spec) and **~12 implementation_steps** (from §9).
- Phase 3 cross-validation: expect some orphan warnings (design spec doesn't reference every gap) and some P0-uncovered warnings (spec covers admin-portal only, but many gaps are outside admin-portal). These are EXPECTED and acceptable.
- Phase 4: write three YAMLs to `docs/plans/2026-04-19-*.yaml` (or `-v2` if files exist from prior runs).

- [ ] **Step 3: Verify extracted counts**

Run:

```bash
# Count gaps
python -c "import yaml; d=yaml.safe_load(open('docs/plans/2026-04-19-gap-analysis.yaml')); print('gaps:', len(d['gap_analysis']['gaps'])); print('priorities:', d['gap_analysis']['summary']['by_priority'])"

# Count file_changes and steps
python -c "import yaml; d=yaml.safe_load(open('docs/plans/2026-04-19-task-hints.yaml')); print('file_changes:', len(d['task_hints']['file_changes'])); print('steps:', len(d['task_hints']['implementation_steps']))"
```

Expected:
- gaps: 17 (± 2 depending on extraction fidelity)
- priorities: P0=6, P1=6, P2=5 (approx)
- file_changes: ≥ 8
- steps: ≥ 10

- [ ] **Step 4: Run /task-gen against the produced YAMLs**

In Claude Code:

```
/task-gen
```

Expected:
- Skill-3 detects all three YAMLs (gap-analysis, prd-structure, task-hints).
- Task generation emits `docs/plans/2026-04-19-tasks.yaml`.
- The tasks for admin-portal-related gaps (GAP-017 or whichever the design spec covers) should have deliverables matching the spec's §6 file list.
- Some tasks should have `non_goal` rejections logged (e.g. any task touching tokens.css should be rejected because the spec non_goal forbids it).

- [ ] **Step 5: Write acceptance notes**

Write `skills/skill-0-ingest/tests/e2e-autoservice.md`:

```markdown
# E2E Acceptance Test — 2026-04-19

Inputs:
- autoservice-gap.md: {N_gaps} gaps extracted, priorities P0={P0}, P1={P1}, P2={P2}
- autoservice-design.md: {N_file_changes} file_changes, {N_steps} steps

Cross-validation:
- Orphan spec changes: {count} (expected: design spec only covers admin-portal, many gaps elsewhere)
- P0 uncovered: {count} (expected: most P0 gaps don't have spec coverage yet)
- Fatal errors: 0 (required)

Task generation:
- Tasks emitted: {N_tasks}
- Rejected by non_goals: {N_rejected}
- Support tasks (orphan file_changes): {N_support}

Verdict: PASS / FAIL (reasons)
```

Fill in actual numbers after the run.

- [ ] **Step 6: Commit acceptance notes**

```bash
git add skills/skill-0-ingest/tests/fixtures/autoservice-*.md skills/skill-0-ingest/tests/e2e-autoservice.md
git commit -m "test(skill-0): e2e acceptance with real AutoService MDs"
```

- [ ] **Step 7: Clean up generated artifacts**

The generated YAMLs from the E2E test live under `docs/plans/` of the prd2impl repo. Since prd2impl itself isn't using the pipeline for its own development, delete them:

```bash
rm docs/plans/2026-04-19-*.yaml 2>/dev/null || true
# if docs/plans is now empty:
rmdir docs/plans 2>/dev/null || true
```

(If `docs/plans/` contains other files used by prd2impl development, keep those.)

No commit for cleanup.

---

## Self-Review Checklist (performed by plan author, not by the executor)

After writing this plan, I verified:

**Spec coverage:**
- §3 Architecture → Tasks 1, 8, 10 (directory, main flow, router)
- §4 Components → Tasks 3-7 + 8
- §5 Role detection → Task 3
- §6.1 gap-analysis.yaml extended schema → Task 4 (+ Task 2 for example)
- §6.2 task-hints.yaml new schema → Task 2 + Task 5
- §6.3 prd-structure.yaml source marker → Task 6
- §7 skill-3 integration → Task 9
- §8 Cross-validation 5 rules → Task 7
- §9 Error handling (abort + warnings + date-suffix) → Task 8 (flow) + Task 7 (rules)
- §10 Testing strategy → Tasks 3-7 (per-component) + Task 12 (E2E)
- §11 File changes → Tasks 1-11
- §12 Implementation order → this plan (11 tasks match 1:1 with a 12th for E2E acceptance)

**Placeholder scan:** No TBDs, TODOs, or "implement later" phrases in the plan.

**Type/name consistency:** `source_id`, `source_file`, `source_anchor`, `related_gap_refs`, `cross_references`, `non_goals`, `file_changes`, `implementation_steps`, `depends_on_steps`, `touches_files` — used consistently across Tasks 2, 4, 5, 7, 9.

One consistency note fixed after review: in Task 2's example, `source_anchor: "6-file-changes"` vs Task 5's expected `"6-file-changes"` — confirmed matching.
