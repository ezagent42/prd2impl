---
name: task-gen
description: "Task generation with dependency analysis — convert gap analysis into a structured task list with types (Green/Yellow/Red), dependencies, and deliverables. Use when the user says 'generate tasks', 'break down into tasks', 'create task list', or after /gap-scan."
---

# Skill 3: Task Generation

<SUBAGENT-STOP>
If you were dispatched as a subagent to execute a specific task, skip this skill.
</SUBAGENT-STOP>

Convert gap analysis results into a structured task list with dependency graph, color classification, and verification criteria.

## Trigger

- User runs `/task-gen`
- User says "generate tasks", "break down into tasks", "create task list"
- After `/gap-scan` has produced `gap-analysis.yaml`

## Input

- **Required (or B2 fallback)**: `{plans_dir}/*-gap-analysis.yaml` (output from skill-2 or skill-0) — see §Step 1.5 B2 Degradation
- **Required (or B2 fallback)**: `{plans_dir}/*-prd-structure.yaml` (output from skill-1 or skill-0) — see §Step 1.5 B2 Degradation
- **Optional (REQUIRED for B2 fallback mode)**: `{plans_dir}/*-task-hints.yaml` (output from skill-0 only — see §Step 2.5)
- **Optional**: `docs/plans/project.yaml` (team configuration; always at project root)
- **Optional**: Existing `{plans_dir}/tasks.yaml` (for incremental updates — see docs/superpowers/specs/2026-04-20-plans-dir-scoping-design.md §8 Limitation 6 for status)

## Execution Flow

> **Path resolution**: Before constructing any output path, resolve `{plans_dir}` per `lib/plans-dir-resolver.md`. All `docs/plans/` references below (except `docs/plans/project.yaml`, which stays at repo root) are relative to that resolved directory.

### Step 1: Load Gap Analysis

1. Find the most recent `gap-analysis.yaml` and `prd-structure.yaml`. **Do NOT error on miss** — if either file is absent, remember which is missing and proceed to §Step 1.5 to evaluate B2 degradation before emitting any error.
2. Also check for the most recent `task-hints.yaml` — if found, load it (see §Step 2.5)
3. Group gaps by module (skip if `gap_analysis` was synthesized in §Step 1.5)
4. Sort by estimated effort and dependency chain

### Step 1.5: B2 Degradation — task-hints-only mode

skill-3 can operate without `prd-structure.yaml` and/or `gap-analysis.yaml` provided `task-hints.yaml` is present and has a non-empty `implementation_steps` list. This unblocks the design-spec workflow where no gap-scan has run.

#### Trigger

At the end of Step 1 (Load Gap Analysis), check what was loaded:

- If `gap-analysis.yaml` was NOT found AND `task-hints.yaml` WAS found: synthesize `gap_analysis = { gaps: [] }` in memory.
- If `prd-structure.yaml` was NOT found AND `task-hints.yaml` WAS found: synthesize a skeleton `prd_structure` in memory (see §Skeleton synthesis below).
- If `task-hints.yaml` was NOT found OR `implementation_steps` is empty: do NOT synthesize — fall through to the original hard-error behavior of Step 1.

The synthesized structures are **never written to disk** — they exist only for the duration of this `/task-gen` invocation.

#### Skeleton synthesis

```yaml
prd_structure:
  source_type: "synthesized-from-task-hints"
  source_role: "design-spec"
  modules:
    # One module per implementation_step entry
    - id: MOD-01
      name: "<step.description truncated to 60 chars>"
      description: "<step.description (full)>"
      prd_sections: []
      sub_modules:
        # One sub_module per file in step.touches_files
        - id: MOD-01a
          name: "<file basename>"
          description: "<file path>"
  user_stories: []
  nfrs: []
  constraints: []
  external_deps: []
```

Sequential numbering: MOD-01, MOD-02, ... matching the step numbers. Sub-module suffix: MOD-01a, MOD-01b, ... per file within a step.

#### Task output marker

Every task emitted under B2 degradation MUST include:

```yaml
tasks:
  - id: T<phase><line>.<seq>
    ...
    traceability: task-hints-only      # NEW field — absent in normal mode
    synthesized_module_id: MOD-NN      # NEW field — links to skeleton module
```

Downstream skills (contract-check, retro) key off `traceability: task-hints-only` to skip checks that need real `user_stories` / `constraints` / `external_deps`.

#### User-facing warning

Before writing `tasks.yaml`, print:

```
─────────────────────────────────────────────────────
B2 degradation mode active
─────────────────────────────────────────────────────
Missing: {list of absent required files}
Synthesized {N} skeleton modules (MOD-01..MOD-{N}) from implementation_steps.
user_stories / nfrs / constraints / external_deps are empty — downstream
skills (contract-check, retro) will skip checks that depend on these fields.
Re-run /ingest-docs on a richer source document to upgrade.
─────────────────────────────────────────────────────
```

#### What does NOT change

- If all three input files are present → zero behavior change.
- Synthesized structures are NEVER persisted. Running `/ingest-docs` afterward produces real files; this skeleton was only scaffolding for this `/task-gen` invocation.

### Step 2: Generate Tasks

For each gap, generate one or more tasks:

**Task ID Convention**: `T{Phase}{Line}.{Seq}`
- Phase: 0-9 (milestone/phase number)
- Line: identifier from `project.yaml` team config (e.g. `A`, `front`, `infra`), or `S` for shared/cross-line
- Seq: sequential within phase+line

**Classification Rules**:
- **Green** (AI-independent): Pure code implementation with clear specs. No ambiguous design decisions. Has existing patterns to follow.
- **Yellow** (AI + human review): Involves prompt engineering, ML model selection, strategy design, or content that needs domain expert review.
- **Red** (human-driven): Requires stakeholder decisions, legal/compliance review, external API negotiations, or architecture trade-offs with no clear winner.

**Auto color-promotion (0.4.0+)**: After applying the standard rules
above, run the auto-promote check. A task originally typed `green` is
promoted to `yellow` (and `auto_promoted: true` is set on the task)
when ANY of:

1. `affects_files` / `deliverables[*].path` glob matches any of:
   - `**/auth*/**`, `**/permission*/**`, `**/login*`, `**/token*`, `**/credential*`
   - `**/*contract*`, `**/*protocol*`, `**/*schema*` (excluding test files)
2. `must_call_unchanged` list is non-empty
3. `meta.connector_seam: true` (already set by R15 / 0.3.1 connector-seam rule)
4. `env_var.class: A` (security boundary)

When auto-promotion fires, set `type: yellow` and `auto_promoted: true`
on the generated task. Yellow handling proceeds as normal (review,
preflight, contract re-read).

Rationale: M3 retro batch-2 §🟢 finding *"some Green tasks have
hidden security surface that should go through review."* The 14/14
reviewer-caught Critical bug rate in M3 confirms this is high ROI.

**Task Structure**:
```yaml
tasks:
  - id: T1A.1
    name: "Mode/Gate minimal implementation"
    description: "Implement state machine for conversation modes and gate transitions"
    line: backend    # Line identifier from project.yaml, or 'shared'
    type: green      # green | yellow | red
    phase: P1
    module: MOD-01
    gap_ref: GAP-003  # Links to gap-analysis
    story_refs: [US-005, US-006]  # Links to PRD stories
    depends_on: [T0.4]
    blocked_by: []    # External blockers (not task deps)
    deliverables:
      - path: "autoservice/conversation_engine/mode_gate.py"
        type: code       # code | test | doc | config
      - path: "tests/unit/test_mode_gate.py"
        type: test
    may_touch:             # Files this task might modify beyond deliverables
      - "autoservice/conversation_engine/__init__.py"  # Add import
      - "autoservice/config.yaml"                       # Add config entry
    verification: "pytest tests/unit/test_mode_gate.py — all green"
    estimated_effort: small  # small (<2h) | medium (2-8h) | large (>8h)
    status: pending
    owner: null
    artifacts: []
```

### Step 2.5: Apply task-hints (only when task-hints.yaml is present)

**Gate**: Skip this entire step if no `task-hints.yaml` was found in Step 1. When absent, task generation is byte-identical to before this change was made.

When `task-hints.yaml` is present, FIRST check for the plan-passthrough short-circuit (Step 2.5.0). If it fires, the Behavior 1/2/3 logic below does NOT apply. Otherwise, apply the three behaviors that override defaults in Step 2.

#### Step 2.5.0 — Plan-passthrough mapping (Option B, coarse-grained — 0.4.1+)

**Triggers when**: `task_hints.source_type == "ingested"` AND `task_hints.tasks[]` is present and non-empty AND every entry in `tasks[]` carries a `source_plan_path`.

When triggered, use the plan-file mapping below INSTEAD of Behaviors 1/2/3 below. The legacy file_changes / implementation_steps logic remains the default for design-spec ingest and hand-written plans without the writing-plans header.

##### Emission rule — one task per plan FILE

Group `task_hints.tasks[]` by `source_plan_path`. For each unique plan-file group, emit exactly one prd2impl task to `tasks.yaml`:

```yaml
- id: "{see ID rule}"
  name: "{see name rule}"
  type: green                              # default; see type-inference rule
  phase: "{see phase rule}"
  module: ""                                # plan itself is the module
  source_plan_path: "{unique plan path for this group}"
  source_plan_task_count: {count of entries in this group}
  source_plan_step_count: {sum of len(steps) across the group}
  deliverables:
    # aggregated across all plan-tasks in the group, de-duplicated by path
    - path: "{path}"
      change_type: "create | modify"
  verification:
    - "All checkbox steps in {source_plan_path} are checked (executing-plans tick state)"
    - "git diff vs base branch matches the plan's aggregated File Structure (see skill-10 Step 2.5)"
  depends_on: []                            # see dependency-inference rule
```

Note: prd2impl tasks emitted via Step 2.5.0 do NOT carry `source_plan_anchor` (no anchor — the whole plan is the unit). The per-plan-task anchors, files, and step counts stay in `task-hints.yaml` and are read directly by skill-9 / skill-10.

##### Aggregation rule for deliverables

For each unique `source_plan_path`:
- Union `files.create` across all `tasks[]` entries → `change_type: create`.
- Union `files.modify` across all entries → `change_type: modify`.
- Union `files.test` and merge into `create` if the test path is a new file under `tests/`, else into `modify`.
- De-duplicate by `path`. If a file appears in both create and modify across different plan-tasks, prefer `create`.

##### ID rule

Match the plan filename pattern `\d{4}-\d{2}-\d{2}-(?:[a-z0-9-]+-)?p(\d+)([a-z]?)-.+\.md` to extract the plan-letter:

- `*-p1-*.md` → `T1`
- `*-p2-*.md` → `T2`
- `*-p4a-*.md` → `T4A`
- `*-p4b-*.md` → `T4B`
- `*-p6a-*.md` → `T6A`

If the filename does NOT match the `p\d+[a-z]?` pattern, fall back to `TP{1-based ordinal of plan in input list}` (e.g. `TP3` for the 3rd plan).

##### Name rule

Use the plan's H1 with the trailing `Implementation Plan` stripped. Fall back to the filename stem (with date prefix stripped) if the H1 is missing or generic.

##### Phase rule

If `project.yaml` defines `phases[]`, match the plan-letter to a phase (e.g. `p1` → phase `P1`). If no match, set `phase: "ingested"`.

##### Type-inference rule

Default: `type: green`. The granularity is now plan-level — most plans bundle a mix of green/yellow/red work. Default to green and let the user re-classify in `tasks.yaml` if needed. Exception: if the plan filename or H1 mentions `design`, `policy`, `decision`, `architecture`, default to `red` (these plans typically front-load design decisions).

##### Dependency-inference rule

For each emitted task, order by plan-letter (p1 < p2 < p3 < p4a < p4b < p5 < p6a < p6b — natural ordering by digit then letter suffix). Set `depends_on: ["T{prev-plan-letter}"]` if a prev plan was ingested in the same call. Sequential chaining is the safe default — the user edits `tasks.yaml` afterward for non-linear deps.

Print a hint at end of generation:

```
Cross-plan dependencies inferred sequentially (T2 depends on T1, T3 on T2, ...).
Review tasks.yaml depends_on if your plans have non-linear deps.
```

##### What is NOT done in plan-passthrough mode

- No `gap-analysis.yaml` cross-referencing (writing-plans format does not carry GAP-NNN refs)
- No NFR mapping (plans encode "how", not "what" — NFRs come from prd-structure)
- No intra-plan parallelism (executing-plans / subagent-driven-development runs plan-tasks sequentially within one plan; cross-plan parallelism still works via batch-dispatch)
- No batch packing (skill-4-plan-schedule does that)

##### When this step fires, skip Behaviors 1/2/3 below

The legacy file_changes / implementation_steps / non_goals logic is not applicable: writing-plans format doesn't use those fields. Continue to Step 2.6 (house conventions) after this step.

---

> **Branching note**: the three Behaviors below run ONLY when Step 2.5.0 did NOT fire (i.e., `task_hints` carries legacy file_changes / implementation_steps but no `tasks[]`). For plan-passthrough hints, Step 2.5.0 fully replaces them.

#### Behavior 1 — Deliverables come from file_changes

Instead of inferring deliverable paths from gap descriptions:

1. For each `task_hints.file_changes` entry, create a deliverable.
2. Group `file_changes` by their `related_gap_refs[0]` (primary gap ref). All `file_changes` sharing the same primary gap → one task with multiple deliverables.
3. If a `file_change` has additional `related_gap_refs` beyond the first, store those as `cross_references` on the task (do not create duplicate deliverables).
4. `file_changes` with empty `related_gap_refs` → assign to a shared catch-all task; emit warning "orphan file_change assigned to shared task".

#### Behavior 2 — depends_on comes from implementation_steps

Instead of (or in addition to) dependency inference in Step 3:

1. For each `task_hints.implementation_steps` entry:
   - Identify which task(s) own the files listed in `touches_files` (matched via deliverables from Behavior 1).
   - For each `step.depends_on_steps` reference → find the tasks that own those step's files → add those tasks to `depends_on`.
2. Cross-step dependencies take precedence over implicit inference; explicit gap `depends_on_gaps` still applies.

#### Behavior 3 — non_goals is a hard boundary

Before emitting any task, check each `task.deliverables[*].path` against `task_hints.non_goals`:
1. Tokenize each non_goal string (split on spaces; strip punctuation).
2. If any token appears in the deliverable path → reject the task; emit warning: `"task excluded per non_goal: '{non_goal}' matches '{path}'"`
3. Rejected tasks are not written to `tasks.yaml`; they are listed at the bottom of the summary.

### Step 2.6: Inline house conventions into task context (0.4.0+)

Before emitting each task, read `{plans_dir}/conventions.md` (if
exists, written by `skill-2-gap-scan` Step 3.5). For each task whose
`affects_files` glob matches a file referenced by the conventions
cheat-sheet, inline the relevant conventions into the task's
`context_block` field:

```yaml
- id: T-EXAMPLE.2
  ...
  context_block: |
    Project conventions for files touched here:
    - IDs: secrets.token_urlsafe(36) (see autoservice/customer_manager.py:42)
    - Timestamps: ISO 8601 (`datetime.utcnow().isoformat()`)
    - Logger: `logger = logging.getLogger(__name__)` per module
    - MCP servers: hook into cc_pool.py:691 auto-inject — DO NOT duplicate
```

Subagents in `skill-8-batch-dispatch` see this in their dispatch
prompt, eliminating the "reinvented ID format" and "reinvented MCP
bootstrap" failure modes.

When `conventions.md` is absent (skill-2 not run, or skill-2 missing
Step 3.5 from older 0.3.x install), skip silently — task generation
proceeds without the inlined block.

### Step 3: Dependency Analysis

1. **Explicit dependencies**: From gap_ref → gap.depends_on_gaps → task mapping
2. **Implicit dependencies** (auto-inferred):
   - If task A produces a file that task B imports → B depends on A
   - If task A defines an interface that task B implements → B depends on A
   - If task A is in phase N and task B is in phase N+1 of same module → likely dependency
3. **Cross-line dependencies**: Frontend tasks depending on backend APIs
4. **Validate**: No circular dependencies (topological sort check)

Generate dependency graph:
```yaml
dependency_graph:
  # Adjacency list: task → [tasks that depend on it]
  T0.1: [T0.3, T0.4, T1A.4]
  T0.2: [T0.3, T0.5, T0.6]
  T0.4: [T0.5, T1A.1, T1A.2, T1A.3]
  # ...

critical_path: [T0.1, T0.4, T1A.1, T2A.1, T3A.7, T4A.4, T5A.1]
critical_path_length: 7  # Longest chain
```

### Step 4: Phase Assignment

Group tasks into phases/milestones based on:
1. Dependency ordering (topological sort)
2. Module cohesion (keep related tasks in same phase)
3. Logical checkpoints (each phase should be independently verifiable)

```yaml
phases:
  - id: P0
    name: "Contracts & Skeleton"
    milestone: M0
    tasks: [T0.1, T0.2, T0.3, T0.4, T0.5, T0.6]
    gate: "All contract files frozen, skeleton code compiles"
    
  - id: P1
    name: "Core Features"
    milestone: M1
    tasks: [T1A.1, T1A.2, ..., T1B.1, T1B.2, ...]
    gate: "End-to-end conversation flow works"
```

### Step 5: Line Assignment

If `project.yaml` defines team lines, assign tasks:
- Check each task's module → which line owns that module (match module skills to line skills)
- Check deliverable file paths → which line's directory
- Cross-cutting tasks → assign to `shared` with designated driver
- If only 1 line defined → assign all tasks to that line (no splitting needed)

### Step 6: Statistics & Warnings

Generate summary:
```yaml
summary:
  total_tasks: 75
  by_type:
    green: 48 (64%)
    yellow: 18 (24%)
    red: 9 (12%)
  by_line:
    # Dynamic — one entry per line from project.yaml
    backend: 43
    frontend: 29
    shared: 3
  by_phase:
    P0: 6
    P1: 17
    P2: 12
    # ...
  critical_path_length: 7
  estimated_duration: "3 days (with 2 parallel lines)"
  
warnings:
  - "T3A.4 (Red) blocks 3 downstream tasks — start early"
  - "P5 has 8 tasks depending on external zchat API (DEP-01)"
  - "Line 'backend' has 48% more tasks than 'frontend' — consider rebalancing"
```

### Step 7: Output

1. Write `{plans_dir}/{date}-tasks.yaml` (structured data)
2. Write `{plans_dir}/{date}-tasks.md` (human-readable table format)
3. Write dependency graph as Mermaid in the markdown file
4. Print summary to terminal

### Step 8: Human Review Checkpoint

**STOP here.** Present task list and wait for user review.

> Task generation complete. {N} tasks across {P} phases.
> Type split: {G} Green / {Y} Yellow / {R} Red
> Critical path: {CP} tasks deep
>
> Review `{plans_dir}/{date}-tasks.yaml` and confirm:
> 1. Task granularity — any too large (>8h) or too small (<30min)?
> 2. Color classification — any Green that should be Yellow/Red?
> 3. Dependencies — any missing or incorrect links?
> 4. Phase grouping — any tasks in the wrong phase?
>
> When ready, run `/plan-schedule` to create the execution plan.

## Task Granularity Guidelines

- **Too large**: If a task has >3 deliverables or touches >3 files in different modules → split
- **Too small**: If a task is <30 min of work with no interesting design → merge with related task
- **Sweet spot**: 1-4 hours of focused work, 1-2 deliverables, clear verification
- **Red tasks**: Can be larger (design docs, compliance reviews) since they're human-paced

## Pipeline Integration Test Rule

When task decomposition splits a producer/consumer pair across separate tasks (e.g. one task implements a data emitter, a sibling task implements the consumer that filters/routes/displays it), the decomposition leaves a **connector seam**: each unit-tests cleanly in isolation, but a missing field or contract mismatch at the seam makes the whole pipeline silently inert in production.

### When this applies

Detect connector seams by these signals during task generation:

- Two or more tasks share a `module` but cover different stages of a data flow (one writes a field, another reads it)
- A task's `gap_ref` says "evaluate per-tenant" / "filter by X" / "route to Y" while a sibling task says "produce records of type X" — the producer must populate the field the consumer keys on
- A task's `deliverables` produce records consumed by another task's `deliverables` (cross-task data dependency, not just file-import dependency)

### Required additional task

For every detected seam, append an integration task:

```yaml
- id: T<phase><line>.<seq>
  name: "Integration: {producer task} → {consumer task} pipeline"
  type: green
  module: <shared module>
  description: "End-to-end test that exercises the full pipeline from {producer} through {consumer}, asserting the observable behavior at the consumer end (not just that each unit's tests pass)."
  depends_on: [<producer task id>, <consumer task id>]
  deliverables:
    - path: "tests/integration/test_<feature>_pipeline.py"
      type: test
  verification: "Test fails if producer omits the connector field OR consumer ignores it OR the wire format drifts."
  estimated_effort: small  # usually 30-60min
  meta:
    connector_seam: true
    connects: [<producer task id>, <consumer task id>]
```

### Why this matters

M3 retro evidence (T2S.5 AlertEngine): producer task built `FiredAlert` records, consumer task added per-tenant push filter. Both tasks' unit tests passed. **The producer never set `tenant_id` on the record** — so the consumer's filter always short-circuited and the feature was dead in production despite 100% green tests. Reviewer caught it; integration test would have caught it earlier and cheaper.

### Heuristic budget

Add at most one integration task per connector seam. Do not generate integration tasks for trivial seams where the producer and consumer share a single file and the unit tests already exercise the full path. The goal is catching cross-task data drift, not test inflation.
