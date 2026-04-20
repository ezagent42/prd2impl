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

- **Required**: `{plans_dir}/*-gap-analysis.yaml` (output from skill-2 or skill-0)
- **Required**: `{plans_dir}/*-prd-structure.yaml` (output from skill-1 or skill-0)
- **Optional**: `{plans_dir}/*-task-hints.yaml` (output from skill-0 only — see §Step 2.5)
- **Optional**: `docs/plans/project.yaml` (team configuration; always at project root)
- **Optional**: Existing `{plans_dir}/tasks.yaml` (for incremental updates — see docs/superpowers/specs/2026-04-20-plans-dir-scoping-design.md §8 Limitation 6 for status)

## Execution Flow

> **Path resolution**: Before constructing any output path, resolve `{plans_dir}` per `lib/plans-dir-resolver.md`. All `docs/plans/` references below (except `docs/plans/project.yaml`, which stays at repo root) are relative to that resolved directory.

### Step 1: Load Gap Analysis

1. Find the most recent `gap-analysis.yaml` and `prd-structure.yaml`
2. Also check for the most recent `task-hints.yaml` — if found, load it (see §Step 2.5)
3. Group gaps by module
4. Sort by estimated effort and dependency chain

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

When `task-hints.yaml` is present, apply three behaviors that override the defaults in Step 2:

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
