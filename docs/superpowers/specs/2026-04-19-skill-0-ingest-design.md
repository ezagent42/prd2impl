# prd2impl · skill-0-ingest Design

**Status:** Draft
**Date:** 2026-04-19
**Scope:** Add `skill-0-ingest` to prd2impl; minor additive changes to `skill-3-task-gen` and the `using-prd2impl` router.
**Non-scope:** skill-1/2/4 and all execution-phase skills (5-12) unchanged.

## 1. Motivation

`prd2impl` pipeline today assumes a single upstream PRD document and auto-generates YAML step-by-step:

```
PRD → skill-1 prd-analyze → prd-structure.yaml
    → skill-2 gap-scan → gap-analysis.yaml
    → skill-3 task-gen → tasks.yaml
    → skill-4 plan-schedule → execution-plan.yaml
```

Real projects often **already have human-written intermediate artifacts**: gap analyses, design specs, layout plans. Currently there is no way to feed these into the pipeline. Users either:

- Discard them and re-run the pipeline from scratch (wasteful; loses human judgment embedded in the MDs), or
- Hand-author `tasks.yaml` (loses pipeline discipline — dependency graph, phase grouping, type classification).

This skill adds a **mid-entry path** that ingests multiple heterogeneous Markdown documents and produces the same YAML artifacts the existing skill-1 and skill-2 do, letting the rest of the pipeline (skill-3 onward) run unchanged.

Concrete motivating case: AutoService project has `docs/plans/2026-04-18-prd-full-journey-gap.md` (17 gaps with P0/P1/P2 tags) and `docs/superpowers/specs/2026-04-18-admin-portal-web-layout-design.md` (detailed file-change list + 12-step implementation order). Neither can currently feed `/task-gen`.

## 2. Goals and Non-Goals

**Goals:**
- Accept multiple heterogeneous MD files as input; produce `prd-structure.yaml` + `gap-analysis.yaml` + `task-hints.yaml` (the last is new).
- Preserve human IDs (`A-①`, `P0`, etc.) as `source_id` / `source_file` / `source_anchor` metadata while generating canonical IDs (`GAP-001`).
- Let `skill-3-task-gen` consume `task-hints.yaml` so human-designed file-change granularity and implementation order survive into `tasks.yaml`.
- Auto-detect document role with user confirmation; explicit `--tag` as fallback.
- Backward compatible: no existing skill's output format changes; new YAML fields are optional; `skill-3` behavior unchanged when `task-hints.yaml` is absent.

**Non-goals:**
- No PDF / DOCX / remote-URL input (MD only).
- No auto-repair of source MDs (cross-validator reports; it never writes back).
- No incremental ingest (each run is full re-extraction; existing YAMLs are preserved via date-suffixed filenames).
- No changes to `skill-4` and downstream execution skills.
- No "merge with existing `prd-structure.yaml` from prior `/prd-analyze` run" — when both entries produce files, they co-exist with distinct `source_type` markers; user picks which to feed `/task-gen` via file path.

## 3. Architecture

Two parallel entries into the pipeline; merge at `skill-3`:

```
Entry A (existing)          Entry B (new)
┌──────────────────┐        ┌─────────────────────┐
│ skill-1          │        │ skill-0-ingest      │
│ /prd-analyze X.md│        │ /ingest-docs A B C  │
└────────┬─────────┘        └──────────┬──────────┘
         │                             │
         ↓                             ↓
   prd-structure.yaml          ┌───────┴────────┐
         │                     ↓       ↓        ↓
         │          prd-structure  gap-analysis  task-hints
         │          (ingested)     (ingested)    (new)
         │                  │       │              │
         └──────────────────┴───────┘              │
                       ↓                           │
                 skill-2 gap-scan (optional)       │
                       ↓                           │
                 gap-analysis.yaml                 │
                       ↓                           │
         ┌─────────────┴─────────────┬─────────────┘
         ↓                           ↓
              skill-3 task-gen (modified: optional task-hints input)
                       ↓
                  tasks.yaml
                       ↓
               skill-4 plan-schedule
```

Contract:
- skill-0 output YAMLs are **format-compatible** with skill-1/2 outputs; distinguishing marker is `source_type: "ingested"` at the top level.
- `task-hints.yaml` is a new artifact; `skill-3` reads it if present, otherwise behaves exactly as today.
- skill-0 and skill-1 are **mutually exclusive** per project (run one or the other; the router enforces this).

## 4. Components

```
prd2impl/skills/skill-0-ingest/
├── SKILL.md                       # main entry + flow orchestration
├── lib/
│   ├── role-detector.md           # Phase 1
│   ├── gap-extractor.md           # Phase 2a
│   ├── spec-extractor.md          # Phase 2b
│   ├── prd-extractor.md           # Phase 2c
│   └── cross-validator.md         # Phase 3
├── schemas/
│   ├── task-hints.schema.yaml     # new schema (skill-3 shares)
│   └── gap-analysis.example.yaml  # example incl. new source_* fields
└── templates/
    └── role-confirmation.md       # Phase 1 confirmation table template
```

### 4.1 Component contracts

| Component | Input | Output | Responsibility |
|---|---|---|---|
| **role-detector** | List of MD paths | `[{path, detected_role, confidence, evidence}]` | Reads frontmatter + first 50 lines + filename; outputs role guess + evidence. Does **not** extract content. |
| **gap-extractor** | MD(s) classified as `gap` | Additions to gap-analysis.yaml | Detects `P0/P1/P2` priorities, `A-①/B-⑦` style source IDs, fix suggestions; assigns canonical `GAP-NNN` + fills `source_*` fields. |
| **spec-extractor** | MD(s) classified as `design-spec` | task-hints.yaml | Extracts file-change lists (new/modify/delete), implementation steps with dependencies, test strategy, non-goals, risks. |
| **prd-extractor** | MD(s) classified as `prd` or `plan` | prd-structure.yaml | Reuses skill-1 extraction logic for PRD type; for plan type, extracts only modules and constraints (not user stories / NFRs). |
| **cross-validator** | All three produced YAMLs | Warnings + fatal errors | Checks: orphan spec changes, uncovered P0 gaps, dangling step references, non-goals ↔ file-changes conflicts, invalid source_anchors. |

### 4.2 Execution flow (inside SKILL.md)

```
Phase 1 · Role detection
  run role-detector on all inputs
  → print confirmation table
  → [HUMAN REVIEW 1] accept / override / drop

Phase 2 · Extraction (parallel, per role)
  for each MD:
    dispatch to gap-extractor | spec-extractor | prd-extractor
  produce: in-memory gap-analysis + task-hints + prd-structure data

Phase 3 · Cross-validation
  run cross-validator
  → print warnings table
  → if any fatal error: ABORT, no files written
  → [HUMAN REVIEW 2] accept warnings y/n

Phase 4 · Write + summary
  write 3 YAMLs to docs/plans/{date}-*.yaml
  print summary
  → [HUMAN REVIEW 3] "ready for /task-gen?"
```

## 5. Role detection rules

Six recognized roles:

| Role | Typical signals | Produces |
|---|---|---|
| **gap** | Title contains "Gap / 缺口 / 缺失 / 偏差"; items have P0/P1/P2 tags; item structure ID-priority-fix | gap-analysis.yaml |
| **design-spec** | Title contains "Design / Spec / 设计"; has §file-change section, §implementation-order, §architecture | task-hints.yaml |
| **plan** | Title contains "Plan / 计划"; has milestone / phase / timeline; task-like items but no implementation detail | prd-structure.yaml (partial) + task-hints.yaml (steps only) |
| **prd** | Title contains "PRD / Requirements"; has user stories, NFRs, acceptance criteria | prd-structure.yaml (full, via skill-1 logic) |
| **user-stories** | Standalone US list ("As a X, I want Y, so that Z") | prd-structure.yaml (user_stories section only) |
| **unknown / mixed** | No clear signal | Skipped with warning; requires `--tag` to include |

### 5.1 Confidence scoring (0–100)

Four signals, weighted:

| Signal | Weight | Detail |
|---|---|---|
| **Filename** | 30 | `*-gap.md` / `*-design.md` / `*-plan.md` / `*-prd.md` / `*-stories.md` direct hit |
| **Frontmatter** | 20 | YAML frontmatter `type:` field (if present) |
| **First 50 lines keywords** | 30 | Heading contains role keyword (Gap / Design / Spec / Plan / PRD / Requirements) |
| **Structural signatures** | 20 | Contains `P0/P1/P2` / `§file-change` / `US-xxx` / `NFR-xxx` etc. |

Thresholds:
- **≥ 70**: high confidence, auto-accepted in the table.
- **40–69**: medium, shown with top-2 candidates plus evidence, user confirms.
- **< 40**: low; labeled `unknown`. If user doesn't override with `--tag`, the file is dropped with a warning.

### 5.2 Heuristic-first, LLM-fallback

1. Rule-based scorer runs first (fast, zero token).
2. Only if top score < 70 does the detector invoke the LLM to read the full MD and return `{role, confidence}` — normalized into the same scoring space, then merged with rule score (take max).
3. User confirmation table always runs.

This keeps ~90% of cases token-free while handling ambiguous documents with LLM judgment.

### 5.3 Explicit-tag fallback

CLI accepts `--tag role=path` overrides:
```
/ingest-docs a.md b.md c.md --tag spec=a.md --tag gap=b.md
# a.md forced to spec; b.md forced to gap; c.md goes through auto-detect
```

If auto-detect produces all-unknown, the skill aborts Phase 1 with a message instructing the user to re-run with `--tag`.

## 6. YAML schemas

### 6.1 gap-analysis.yaml (extended)

Adds `source_type` + per-gap `source_*` fields; all other fields unchanged from skill-2 output:

```yaml
gap_analysis:
  scan_date: "2026-04-19"
  source_type: "ingested"                 # new: "scanned" | "ingested"
  source_files:                           # new: input MD list
    - "docs/plans/2026-04-18-prd-full-journey-gap.md"

  summary:
    total_gaps: 17
    by_priority:
      P0: 6
      P1: 6
      P2: 5

  gaps:
    - id: GAP-001                         # canonical ID (generated)
      source_id: "A-①"                    # new: original human ID
      source_file: "2026-04-18-prd-full-journey-gap.md"   # new
      source_anchor: "a--缺注册接入独立步骤-p0"              # new: heading slug
      description: "缺'注册接入'独立步骤"
      module: "admin-portal-wizard"       # inferred
      priority: P0
      gap_type: missing                   # missing | partial | outdated
      existing_code: []
      missing_parts:
        - "Wizard 前置 RegisterStep 组件"
        - "countries → compliance_profile 映射"
      estimated_effort: medium
      depends_on_gaps: []                 # populated by cross-validator
```

### 6.2 task-hints.yaml (new)

Design specs already embed task-level thinking — file lists, step order, test scope, non-goals. This schema preserves that structure so `skill-3` uses human-designed granularity instead of re-deriving.

```yaml
task_hints:
  source_files:
    - "docs/superpowers/specs/2026-04-18-admin-portal-web-layout-design.md"

  # 1. File-change list (spec §"file changes")
  file_changes:
    - path: "frontend/apps/admin-portal/src/components/shell/AdminShell.tsx"
      change_type: create                 # create | modify | delete | no-change
      purpose: "topbar + rail + canvas shell"
      source_anchor: "6--file-changes--new"
      related_gap_refs: ["GAP-017"]       # populated by cross-validator

  # 2. Implementation order (spec §"implementation steps")
  implementation_steps:
    - step: 1
      description: "Build shell: AdminShell + AdminTopbar + AdminRail + new CSS"
      touches_files:
        - "frontend/apps/admin-portal/src/components/shell/AdminShell.tsx"
        - "frontend/apps/admin-portal/src/index.css"
      source_anchor: "9--implementation-order"
    - step: 2
      description: "App.tsx wires AdminShell"
      depends_on_steps: [1]
      touches_files:
        - "frontend/apps/admin-portal/src/App.tsx"

  # 3. Test strategy (spec §"testing")
  test_strategy:
    preserved_testids:
      - "tab-wizard"
      - "tab-dashboard"
    new_tests:
      - name: "AdminRail.test.tsx"
        focuses_on: "default active = notifications; 5 icons switch tabs"
      - name: "InlineWidget.test.tsx"
        focuses_on: "4 structured message types each render expected DOM"
    e2e_delta: "no new E2E"

  # 4. Non-goals (spec §"non-goals") — hard boundary for skill-3
  non_goals:
    - "no design-system level changes (tokens.css / components.css unchanged)"
    - "no mobile-specific UX"
    - "no ⌘K real search (placeholder only)"

  # 5. Open risks (spec §"risks") — flow into task.blocked_by / warnings
  risks:
    - risk: "test selector regression"
      mitigation: "baseline full test run before refactor"
```

### 6.3 prd-structure.yaml (unchanged, plus source marker)

Plan / PRD MDs use existing skill-1 extraction. Only addition is `source_type: "ingested"` at the top level, letting cross-validator and skill-3 know the origin.

## 7. skill-3-task-gen integration

`skill-3` gains **one optional input** and **three behaviors** that only activate when that input exists:

### 7.1 Additional input

```yaml
# skill-3 inputs (after change)
Required: gap-analysis.yaml, prd-structure.yaml
Optional: project.yaml, existing tasks.yaml
Optional (NEW): task-hints.yaml
```

### 7.2 Behaviors activated when task-hints.yaml is present

1. **Deliverables come from `file_changes`**:
   Each `file_change` entry becomes a task's `deliverables` entry. Multiple file_changes sharing the same `related_gap_refs` collapse into one task (one task per gap, multiple deliverables). If a `file_change` carries more than one `related_gap_refs` entry, the **first** gap ref is treated as primary (the file_change is placed under its task); the remaining refs are stored as `cross_references` on the task for traceability but do not cause deliverable duplication.

2. **`depends_on` comes from `implementation_steps`**:
   When task A's deliverables overlap with step N's `touches_files`, and task B's overlap with step M > N where step M depends on step N — then task B `depends_on` task A.

3. **`non_goals` is a hard boundary**:
   Before emitting a task, skill-3 checks task.deliverables against `non_goals` keyword list. Any match → task is rejected (not generated) with a warning "excluded per non_goal X".

### 7.3 Backward compatibility guarantee

If `task-hints.yaml` is absent, skill-3's behavior is **byte-identical** to today. The three behaviors above are gated behind a single `if task_hints_yaml.exists()` check at the top of step 2.

## 8. Cross-validation rules

Five checks run after all three YAMLs are in memory, before write:

| Rule | Detection | Severity | Handling |
|---|---|---|---|
| Every `file_change` relates to a gap | If `related_gap_refs` empty, search within the section identified by `source_anchor` in the original MD for any `GAP-NNN` or known `source_id` string (e.g. `A-①`) | Warning | Backfill `related_gap_refs` if match found; flag "orphan spec change" otherwise |
| Every P0 gap is covered by spec | For each P0 GAP-ID, check any `task_hints.file_changes.related_gap_refs` contains it | Warning | Flag "P0 gap with no implementation plan" |
| `implementation_steps.touches_files` ⊆ `file_changes.path` | Set comparison | Warning | Flag "step references undeclared file" |
| `non_goals` doesn't contradict `file_changes` | Keyword match (e.g., non_goal "tokens.css unchanged" vs file_change path containing "tokens.css") | **Fatal** | Abort Phase 4; no files written |
| All `source_anchor` values resolve to real headings in their MD | Re-read source MD, match heading slug | Warning | Flag "dead anchor" — usually means MD edited after ingest |

## 9. Error handling

| Scenario | Handling | User-visible signal |
|---|---|---|
| Input MD file not found | Abort immediately; list missing paths | `ERROR: file not found: xxx.md` |
| All MDs score < 40 in role detection | Abort Phase 1 | Suggest `--tag role=path` explicit form |
| Extractor exception on one MD (encoding, malformed structure) | Skip that file + warning; others continue | Warning table notes "file produced no entries" |
| Cross-validator fatal conflict | Abort Phase 4; no partial writes | Conflict pairs printed; user fixes MD and re-runs |
| Cross-validator non-fatal warnings | Proceed with write; warnings printed | `y/n` confirmation before write |
| Target YAML filename already exists | Default: date-suffix sidecar (`2026-04-19-gap-analysis.yaml`); if same-day collision, append `-v2` | Zero data loss |
| Filesystem write failure (permissions / disk) | Abort; discard in-memory | Clear error code |

## 10. Testing strategy

Per-component fixtures plus one end-to-end smoke run:

| Layer | What | How |
|---|---|---|
| role-detector | 6 roles × confidence scoring | Fixture set: 3 MDs per role spanning clear/medium/unclear; assert score bands + role labels |
| gap-extractor | Real gap MD end-to-end | Input: AutoService `2026-04-18-prd-full-journey-gap.md`; assert 17 gaps + priority split P0=6/P1=6/P2=5 + all source_* fields populated |
| spec-extractor | Real design spec end-to-end | Input: AutoService `2026-04-18-admin-portal-web-layout-design.md`; assert ≥8 file_changes + 12 implementation_steps + non_goals populated |
| prd-extractor | Plan + PRD inputs | Reuse skill-1 fixtures; also test plan-only mode extracts constraints but no user_stories |
| cross-validator | 5 rules each | Five minimal fixtures, each designed to trip one rule exactly |
| End-to-end | 3 MDs → 3 YAMLs → skill-3 consumes | AutoService real files; assert tasks.yaml deliverables pulled from file_changes; assert depends_on derived from implementation_steps |

The AutoService 3-MD run is the authoritative acceptance test.

## 11. File changes

### New files

```
prd2impl/
├── skills/skill-0-ingest/
│   ├── SKILL.md
│   ├── lib/role-detector.md
│   ├── lib/gap-extractor.md
│   ├── lib/spec-extractor.md
│   ├── lib/prd-extractor.md
│   ├── lib/cross-validator.md
│   ├── schemas/task-hints.schema.yaml
│   ├── schemas/gap-analysis.example.yaml
│   └── templates/role-confirmation.md
└── docs/superpowers/specs/2026-04-19-skill-0-ingest-design.md   (this file)
```

### Modified files

| File | Change |
|---|---|
| `skills/skill-3-task-gen/SKILL.md` | Add optional `task-hints.yaml` input; three gated behaviors (see §7). Backward-compatible. |
| `skills/using-prd2impl/SKILL.md` | Register `/ingest-docs` routing to skill-0; note Entry A / Entry B mutual exclusion |
| `README.md` | Add Entry B Quick Start section; update pipeline diagram |

### Unchanged

Every other skill (1, 2, 4, 5, 6, 7, 8, 9, 10, 11, 12) — all execution, planning, and verification skills are untouched.

## 12. Implementation order

11 steps, each producing an independently verifiable artifact. Commit after each.

| # | Step | Artifact | Verification |
|---|---|---|---|
| 1 | Create skill-0-ingest directory skeleton + empty SKILL.md | Directory tree | Structure exists; SKILL.md has frontmatter |
| 2 | Define `task-hints.yaml` schema + example | `schemas/task-hints.schema.yaml` | Schema validates the example |
| 3 | Implement role-detector (heuristic only) | `lib/role-detector.md` | Fixture set scores ≥70 for 6 clear cases |
| 4 | Implement gap-extractor | `lib/gap-extractor.md` | Real AutoService gap MD → 17 gaps with priorities and source_* fields |
| 5 | Implement spec-extractor | `lib/spec-extractor.md` | Real AutoService design spec → ≥8 file_changes, 12 steps, non_goals populated |
| 6 | Implement prd-extractor (reuses skill-1 logic) | `lib/prd-extractor.md` | Existing skill-1 fixtures pass |
| 7 | Implement cross-validator (5 rules) | `lib/cross-validator.md` | 5 rule-specific fixtures each trip exactly one rule |
| 8 | Wire SKILL.md main flow with 3 human-review checkpoints | `SKILL.md` | Full run on AutoService 3 MDs produces 3 YAMLs + summary |
| 9 | Modify skill-3-task-gen for optional task-hints input | `skill-3-task-gen/SKILL.md` diff | With hints: deliverables map file_changes; without: byte-identical to today |
| 10 | Register `/ingest-docs` in router | `using-prd2impl/SKILL.md` diff | Command triggers skill-0 |
| 11 | README update | `README.md` diff | Entry B documented; pipeline diagram updated |

End-to-end acceptance: `/ingest-docs` on AutoService's 3 real MDs → valid YAMLs → `/task-gen` → viable tasks.yaml.

## 13. Open risks

| Risk | Mitigation |
|---|---|
| Role-detector heuristic fragile on non-English filenames / non-standard structures | LLM fallback path (§5.2) handles residual cases; explicit `--tag` is always available |
| skill-3 behavior change breaks existing users despite backward-compat claim | Acceptance test #6 (prd-extractor) runs full skill-1 fixture suite through new skill-3 path without task-hints — asserts byte-identical output |
| `file_changes` without `related_gap_refs` produces orphan tasks in skill-3 | Cross-validator warns; skill-3 treats orphan file_changes as a "support" category, generating `infra` tasks without gap_ref |
| Two runs on same day overwrite each other | Date-suffix + `-v2/-v3` naming eliminates collision |
| Extractors on very large MDs blow token budget | Extractors read MD in sections (frontmatter + TOC + section-by-section); upper bound is O(sections) LLM calls, not O(lines) |

## 14. Future extensions (not in this scope)

- PDF / DOCX input (via conversion layer)
- Remote URL fetch
- Incremental ingest (diff against prior run's YAMLs)
- Round-trip: edit YAML → regenerate MD view
- Jira / Linear / GitHub Issues export ingestion
- `--merge` mode: combine new ingest with existing prd-structure.yaml from prior `/prd-analyze` run

---

**End of design.**
