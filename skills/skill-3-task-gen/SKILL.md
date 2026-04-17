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

- **Required**: `docs/plans/*-gap-analysis.yaml` (output from skill-2)
- **Required**: `docs/plans/*-prd-structure.yaml` (output from skill-1)
- **Optional**: `docs/plans/project.yaml` (team configuration)
- **Optional**: Existing `docs/plans/tasks.yaml` (for incremental updates)

## Execution Flow

### Step 1: Load Gap Analysis

1. Find the most recent `gap-analysis.yaml` and `prd-structure.yaml`
2. Group gaps by module
3. Sort by estimated effort and dependency chain

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
        type: code
      - path: "tests/unit/test_mode_gate.py"
        type: test
    verification: "pytest tests/unit/test_mode_gate.py — all green"
    estimated_effort: small  # small (<2h) | medium (2-8h) | large (>8h)
    status: pending
    owner: null
    artifacts: []
```

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

1. Write `docs/plans/{date}-tasks.yaml` (structured data)
2. Write `docs/plans/{date}-tasks.md` (human-readable table format)
3. Write dependency graph as Mermaid in the markdown file
4. Print summary to terminal

### Step 8: Human Review Checkpoint

**STOP here.** Present task list and wait for user review.

> Task generation complete. {N} tasks across {P} phases.
> Type split: {G} Green / {Y} Yellow / {R} Red
> Critical path: {CP} tasks deep
>
> Review `docs/plans/{date}-tasks.yaml` and confirm:
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
