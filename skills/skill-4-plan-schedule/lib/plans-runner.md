# plans-runner — Self-driven invocation contract for superpowers:writing-plans

Used by: `skills/skill-4-plan-schedule/SKILL.md` Step 4.5 (per-task plan generation).

When skill-4 invokes `superpowers:writing-plans` for each task in `tasks.yaml`, it does NOT do so in the skill's default "design a multi-step task from scratch" mode. The design has already been done by the upstream chain (skill-1 → skill-3). Skill-4's job here is to crystallize each task's existing spec into a writing-plans-format md without re-asking design questions that have already been settled.

## Why a runner contract

`superpowers:writing-plans` is designed to assume a developer with full context will follow its output. When invoked freshly per-task by skill-4, it lacks that context. Without this contract, it would ask "what are you building?" for every task — 30 tasks × discovery = unusable.

The runner contract gives writing-plans a complete spec package PER task, defines exactly which questions still warrant user input, and bounds interactivity.

## Inputs

For each task being planned, skill-4 assembles a spec package:

```yaml
spec_package:
  task:
    id: T1A.3
    name: "EventBus subscriber registration"
    type: green
    phase: P1
    module: "engine"
    deliverables:
      - {path: "autoservice/engine/eventbus.py", change_type: create}
      - {path: "tests/engine/test_eventbus.py", change_type: create}
    verification:
      - "subscribers can register; messages route to all subscribers; unregister works"
    story_refs: [US-3]
    depends_on: [T1A.2]
  prd_modules:
    # The full module entries from prd-structure.yaml that this task touches
    - id: MOD-engine
      description: "..."
  gap_refs:
    # The gap-analysis entries this task addresses
    - id: GAP-007
      severity: P0
      description: "..."
  conventions:
    # From project.yaml + conventions.md
    test_framework: pytest
    naming_id: "secrets.token_urlsafe(36)"
    timestamps: "datetime.utcnow().isoformat()"
  ambiguity_resolutions:
    # From skill-1 Phase 0.5; only the resolutions that affect THIS task
    - "Multi-tenant mode is enabled via SINGLE_TENANT_MODE=0 env (A1 decision)"
```

## Writing-plans framing prompt

When skill-4 invokes writing-plans, pass this framing as preamble:

```
You are running in PER-TASK-PLAN-GENERATION mode for prd2impl skill-4.

Your goal is to produce one writing-plans-format markdown plan for the task in
the spec_package below. The design has ALREADY been done by upstream skills
(skill-1 PRD analysis, skill-2 gap-scan, skill-3 task-gen). Do NOT re-ask design
questions that the spec already answers.

You MUST self-drive these aspects without pausing:

  - File Structure section (from task.deliverables + conventions)
  - Phase / sub-task decomposition WITHIN this plan (split task into 3-8
    plan-tasks by natural boundaries: setup, core, integration, tests, docs)
  - TDD-rhythm step pairs (failing test → run → verify FAIL → impl → run → verify
    PASS → commit) — use writing-plans' standard 5-step rhythm
  - Code-block content for tests and impl (derive from task.verification +
    task.deliverables[].path)
  - Commit cadence (one commit per plan-task, at the close)

You MUST PAUSE and surface a pause_point when:

  - 2+ genuinely different approaches exist and the spec doesn't pick one
    (e.g., "REST vs gRPC", "Postgres vs SQLite")
  - A decision is irreversible (DB schema shape, public API contract,
    serialization format on the wire)
  - task.deliverables[] contradicts a prd_modules constraint
  - A constraint applies that the task entry doesn't fully express, and
    applying it changes the plan shape

You MUST NOT pause for:

  - Naming style choices — defer to conventions.naming_id, conventions.timestamps,
    or the file/directory style already present in the codebase.
  - File path placement within an established directory — use conventions.
  - Test framework selection — use conventions.test_framework.
  - Granularity of step decomposition — use writing-plans' own guidance.
  - Whether to add error handling — only add what's tested; don't speculate.

Output format: see "## Output schema" section below in this document.
```

## Output schema

plans-runner returns one of two result shapes per task.

When the plan was self-driven to completion:

```yaml
result:
  task_id: <task.id>
  status: ok
  plan_md_path: "docs/superpowers/plans/{date}-{task_id}.md"
  plan_md_content: |
    <full writing-plans-format markdown — the file's contents>
  pause_points: []
```

When the plan needs user input on at least one pause_point:

```yaml
result:
  task_id: <task.id>
  status: paused
  plan_md_path: null
  plan_md_content: null
  pause_points:
    - decision_label: "<short label, e.g., 'sync transport: REST vs gRPC'>"
      options:
        - {label: "...", impact: "..."}
      recommended: "<one of the labels>"
      rationale: "<one sentence>"
      reversibility: low | medium | high
```

## Interactive batch sizing

Skill-4 accumulates `pause_points` across all tasks before invoking the user. If `total_pause_points > 8`, split into rounds of ≤8, prioritized by `reversibility: low` first (irreversible decisions need careful review), then `medium`, then `high`.

Each round is its own user-interaction pass. After the user answers a round, skill-4 replays `plans-runner.invoke()` for each affected task with the answer applied to its `spec_package.ambiguity_resolutions` — the second call should return `status: ok`.

**When a user refuses to answer a question** (clicks "Skip" or equivalent): apply the most-reversible default option from `pause_points[*].options` (the one whose `reversibility` is `high`; tie-break by the entry's `recommended` label). Replay `plans-runner.invoke()` with that default applied to `spec_package.ambiguity_resolutions`. The replay's generated `plan_md_content` MUST include a `[NEEDS_REVIEW: <decision_label>]` marker at the top of the affected plan-task body. Skill-4 then writes the plan_md with `plan_status: needs_review` recorded in tasks.yaml. Skill-9 surfaces these as "{N} tasks need review" in the Active Tasks dashboard.

## Acceptance criteria

The contract holds when, applied to a `spec_package` of typical complexity:
- `status: ok` produces a plan_md that parses cleanly via `skill-0-ingest/lib/plan-parser.md` (returns `error: null`, `tasks` non-empty, `steps` per task non-empty).
- The plan_md's H1 ends with "Implementation Plan" (so role-detector Signal 0 recognizes it as plan-passthrough).
- The plan_md's File Structure section enumerates exactly the deliverables from `spec_package.task.deliverables[]` (no extras, no omissions).
- Each plan-task within the plan_md has 4-8 steps.
- The plan_md's first step is "Write the failing test" or similar TDD-first action.

`status: paused` is acceptable only when the spec_package genuinely fails the "must NOT pause for" list.

## Verification fixture

For task `T-CONFLICT.1` derived from the conflict-prd fixture (Task 1), the expected plan_md is at `tests/expected/conflict-prd.sample-plan-md.md`. The sample shows the canonical shape: H1, agentic-workers blockquote, File Structure, Phase A, Task 1 with 4-6 steps, Task 2 with 4-6 steps.

## What happens after

`plans-runner` returns `result` to skill-4 Step 4.5. Skill-4:
1. If `status: ok`: writes `plan_md_content` to `plan_md_path`; updates the task entry in `tasks.yaml` with `source_plan_path: <plan_md_path>` and `plan_status: ok`.
2. If `status: paused`: stores pause_points in an in-memory queue; does NOT yet write a plan_md for this task.
3. After all tasks are processed: if any tasks paused, run Step 4.5b (batched user-interaction) → Step 4.5c (replay paused tasks with answers).
4. End of Step 4.5: `tasks.yaml` is updated; all plan_mds are on disk.

## Graceful degradation

If `superpowers:writing-plans` is not installed:
- Skill-4 Step 4.5 logs: `"superpowers:writing-plans not installed; per-task plan generation unavailable; tasks fall back to dev-loop Step 5 type-specific workflow."`
- No `source_plan_path` is set on any task
- Skill-4 continues to Step 5 (execution-plan.yaml output) — backward-compatible with 0.4.x
- End-of-run banner: `"Phase A/B/C completed; 0 tasks have source_plan_path (superpowers:writing-plans missing). Install it and re-run /plan-schedule to enable plan-passthrough."`

## Stub fallback (per spec § 7)

If `plans-runner.invoke()` returns an error or fails to produce a parseable plan_md for a task (e.g., spec_package is too thin), skill-4 generates a stub plan_md:

````markdown
# {task.name} Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

> **[STUB PLAN — DO NOT EXECUTE]** This plan was auto-generated as a placeholder because the task spec was insufficient for plans-runner to produce a full plan. Regenerate via `/generate-plan {task_id}` after enriching the task entry in tasks.yaml.

**Goal:** {task.verification[0]}

---

## Phase A — placeholder

### Task 1: {task.name}

**Files:**
{for each deliverable: "- {Create|Modify}: `{path}`"}

- [ ] **Step 1: TODO — fill in steps via /generate-plan**
````

The stub IS written to disk and `source_plan_path` IS set, but `plan_status: stub` is set in tasks.yaml. Skill-5 Step 5' refuses to delegate when it reads the `[STUB PLAN — DO NOT EXECUTE]` marker.
