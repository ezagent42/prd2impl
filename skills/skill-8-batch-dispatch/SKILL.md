---
name: batch-dispatch
description: "Parallel agent dispatch for a batch of tasks — verify dependencies, construct agent prompts, and launch multiple tasks concurrently. Use when the user says 'dispatch batch', 'launch batch-3', 'parallel dispatch', or runs /batch-dispatch."
---

# Skill 8: Batch Dispatch

<SUBAGENT-STOP>
If you were dispatched as a subagent to execute a specific task, skip this skill.
</SUBAGENT-STOP>

Launch multiple tasks in parallel using Claude Code's Agent tool. Verify all prerequisites, construct prompts, and dispatch.

## Trigger

- User runs `/batch-dispatch {batch-id}` (e.g., `/batch-dispatch batch-3`)
- User runs `/batch-dispatch {task-list}` (e.g., `/batch-dispatch T1A.3,T1A.6,T1A.7`)
- User says "dispatch batch 3", "launch these tasks in parallel"

## Input

- **Required**: Batch ID or comma-separated task IDs
- **Data sources**:
  1. `{plans_dir}/*-execution-plan.yaml` (for batch definitions)
  2. `{plans_dir}/tasks.yaml` (for task details)
  3. `{plans_dir}/task-status.md` (for current status)

## Execution Flow

> **Path resolution**: Before constructing any read/write path, resolve `{plans_dir}` per `lib/plans-dir-resolver.md`. All `docs/plans/` references (except `docs/plans/project.yaml`, which stays at repo root) are relative to that resolved directory. Bare references to `tasks.yaml`, `task-status.md`, etc. are also `{plans_dir}`-scoped.

### Step 1: Resolve Tasks

**If batch ID provided**:
1. Load execution-plan.yaml
2. Find the batch definition
3. Extract task list

**If task IDs provided**:
1. Parse comma-separated IDs
2. Load each task from tasks.yaml

### Step 2: Pre-flight Checks

#### 2a. Worktree base branch (MANDATORY — do this FIRST)

Worktrees inherit the base branch HEAD. **Default base is `dev` (integration branch from `project.yaml`).**

1. Run `git fetch origin`
2. Determine base branch:
   - **Default**: use `dev` (or `project.yaml` → `branches.integration`)
   - **If current branch is NOT `dev`**: warn and ask user to confirm:
     ```
     ⚠️ Current branch is '{branch}', not 'dev'.
     Worktrees will be created from 'dev' (default).
     
     Continue with 'dev'? Or use '{branch}' instead? (dev / {branch} / cancel)
     ```
3. Sync the base branch to latest remote:
   ```bash
   git checkout dev && git pull origin dev
   ```
   Report:
   ```
   ✅ Synced dev: pulled {N} commits from origin
   ```
4. **If pull fails** (conflicts, dirty tree): STOP dispatch, report the issue, do NOT proceed
5. **If already up to date**: proceed silently
6. All worktrees will be created from this synced base branch

#### 2b. Task readiness

For each task, verify:
- [ ] Task status is `pending` (⬜)
- [ ] All dependencies are `completed` (🟩)
- [ ] No active external blockers
- [ ] Task type is Green or Yellow (Red tasks should not be auto-dispatched)

If any check fails:
```
Pre-flight failed:
❌ T1A.5 — dependency T1A.4 is still in_progress
❌ T3A.4 — Red task, needs manual start (/start-task T3A.4)
✅ T1A.3 — ready
✅ T1A.6 — ready
✅ T1A.7 — ready

Dispatch 3 of 5 tasks? (y/n)
Or wait for T1A.4 to complete first.
```

#### 2c. File conflict prediction (MANDATORY)

Before dispatching, predict which files each task will modify and detect overlaps.

**Step 1 — Build per-task file footprint:**

For each task, collect its **predicted file set** from 3 sources:

| Source | Method | Confidence |
|--------|--------|-----------|
| **Explicit deliverables** | Read `deliverables[].path` from tasks.yaml | High |
| **Module init files** | For each deliverable dir, add `__init__.py` if it exists | High |
| **Import dependents** | Grep codebase for `from {module} import` or `import {module}` to find files that import the deliverable module — these may need updating | Medium |

Also add **known shared files** that every task might touch:
- `{plans_dir}/task-status.md` — expected, handled by sequential merge
- `.artifacts/registry.json` — expected, handled by sequential merge

**Step 2 — Detect overlaps:**

Build an overlap matrix:
```
File Overlap Matrix:
                    T1A.3    T1A.6    T1A.7
engine/__init__.py    ✗        ✗        ✗      ← 3-way conflict!
plugins/__init__.py   -        ✗        ✗      ← 2-way conflict
mode_gate.py          ✗        -        -      ← no conflict
placeholder.py        -        ✗        -      ← no conflict
lifecycle.py          -        -        ✗      ← no conflict
```

**Step 3 — Classify and act:**

| Overlap Type | Action |
|-------------|--------|
| **No overlap** | Safe to dispatch in parallel |
| **Shared `__init__.py` only** | Warn but allow — these are usually additive (import lines), easy to merge |
| **Same business logic file** | BLOCK parallel dispatch — must run sequentially |
| **Known shared files** (task-status.md, registry.json) | Allow — these are expected; merge sequentially after all agents complete |

**Output conflict report before dispatching:**

```
## File Conflict Analysis

✅ No conflicts: T1A.3, T1A.7 — safe to parallel
⚠️ Low-risk overlap: T1A.3 ↔ T1A.6 share engine/__init__.py (import-only, likely additive)
❌ High-risk overlap: T2A.1 ↔ T2A.3 both modify autoservice/sla_aggregator.py

Recommendation:
  Wave 1: T1A.3, T1A.7 (parallel)
  Wave 2: T1A.6 (after wave 1, to avoid __init__.py conflict)
  Sequential: T2A.1 then T2A.3 (same file)

Proceed with this plan? (y / adjust / cancel)
```

**Step 4 — Inject file boundaries into agent prompts:**

For each agent, add to its prompt:
```
## File Boundaries (CRITICAL)
You MUST only modify these files:
- {deliverable_1}
- {deliverable_2}
- {test_file}

You MUST NOT modify these files (other agents are working on them):
- {conflicting_file_1}
- {conflicting_file_2}

If you need to modify a file outside your boundary, STOP and report instead of editing.
```

This prevents agents from making unexpected changes that cause merge conflicts.

### Step 3: Update Status

For all tasks that pass pre-flight:
1. Mark as `in_progress` (🟦) in task-status
2. Assign owner based on task line (match to team member from `project.yaml`)
3. Commit: `task: batch-{N} dispatch — {IDs} → in_progress`

### Step 4: Construct Agent Prompts

> **Branching note (0.4.1+)**: when a task has `source_plan_path` in its tasks.yaml entry, run **Step 4a — Plan-Passthrough block** instead of the legacy Type-Specific Workflow lines. Step 4a is documented immediately after this Step 4. All other prompt sections (Task Definition, Context Files, File Boundaries, Mock discipline) still apply.


For each task, build a self-contained prompt that includes all context the agent needs:

```python
prompt_template = """
You are working on task {task_id} ({task_name}) in the {project_name} project.

## Task Definition
- Type: {type} ({"Full dev-loop" if green else "Draft + review" if yellow})
- Phase: {phase}
- Module: {module}
- Deliverables: {deliverables}
- Verification: {verification}

## Context Files to Read
1. {contract_files}
2. {related_source_files}
3. {prd_sections}

## Instructions
{"Enter dev-loop: skill-5-feature-eval simulate mode → produce eval-doc → STOP for review" if green}
{"Draft deliverables → produce review checklist → STOP for approval" if yellow}

## Important
- Read task-status.md before starting
- Follow existing code patterns in the project
- Do NOT modify files outside your task scope
- Commit with message format: "task: {task_id} — {description}"
- When done or blocked, update task-status.md

## Mock discipline (0.4.0+)
- See references/mock-policy.md for what may / must-not be mocked.
- Bare MagicMock() / AsyncMock() without spec= is FORBIDDEN in
  tests/ for any production class. Use MagicMock(spec=Class).
- Hand-rolled _FakeX classes require a paired contract test
  (see skill-12-contract-check/references/ast-walk-template.md).

## Yellow review expectations (0.4.0+)
- Yellow tasks receive TWO reviewer passes per
  superpowers:subagent-driven-development:
    Stage A — spec compliance: "did you deliver only what was asked?"
              Catches over-building (helpers, flags, scaffolds not in spec).
    Stage B — code quality: standard 0.3.x review.
- Do NOT bundle extras "while you're in the file"; spec wins.
- Both stages run via superpowers:requesting-code-review.
"""
```

### Step 4a: Plan-Passthrough block (0.4.1+, when source_plan_path present)

When the task being dispatched has `source_plan_path` in its `tasks.yaml` entry, REPLACE the "Type-Specific Workflow" portion of the agent prompt with the block below. The subagent delegates execution to `superpowers:subagent-driven-development` (preferred) or `superpowers:executing-plans` (fallback), which handles per-step TDD discipline internally — skill-8 does NOT inject step-level instructions itself.

**Step 4a.1**: Before dispatch, run `skill-0-ingest/lib/plan-parser.md` against `{source_plan_path}` as a sanity check. If the parser returns an error (`not-a-plan` / `plan-without-tasks`), do NOT dispatch — surface the parser error to the user instead. This prevents launching a subagent at a malformed plan.

**Step 4a.2**: Construct this block and use it INSTEAD of the green/yellow workflow lines in the prompt_template:

````
## Plan-Passthrough Execution

Your task is plan-passthrough mode. The source plan lives at `{source_plan_path}`. It is a writing-plans-format implementation plan with `### Task N:` headings and `- [ ] **Step M: <description>**` checkboxes. Your job is to execute the WHOLE plan end-to-end inside your isolated worktree.

### Required workflow

1. Read the source plan in full: `{source_plan_path}`.
2. Invoke `superpowers:subagent-driven-development` on it. If subagent-driven-development is not available, invoke `superpowers:executing-plans` instead. If neither is available, STOP and report — do NOT improvise step execution.
3. The chosen superpowers skill enforces:
   - One step at a time (the plan's `- [ ]` checkbox rhythm)
   - TDD discipline (write failing test → run, verify FAIL → write minimal impl → run, verify PASS → commit)
   - Verbatim execution of `Run: <cmd>` lines with actual output reporting
   - Commit cadence as the plan declares
4. Tick `- [x]` boxes in the source plan md AS YOU GO (the superpowers skill does this; do not skip it — the prd2impl progress dashboard reads these ticks for the `step_progress` metric).

### Hard rules (apply ON TOP of the superpowers skill's discipline)

- **Worktree scope**: only modify files this prd2impl task's `deliverables[]` declares, OR files the source plan declares under `**Files:**` per-plan-task. Anything else is out-of-scope and must STOP-and-report.
- **No plan editing**: if you find a step is wrong (referenced symbol missing, command syntax broken, etc.), STOP and report. Do NOT "fix the plan as you go" — the user owns plan revisions.
- **No early exit**: do NOT mark the prd2impl task completed until ALL `### Task N:` headings in the source plan have all their checkboxes ticked.

### Completion criteria

Before marking the prd2impl task `completed`:
- Every `- [ ]` in `{source_plan_path}` is now `- [x]`.
- All tests declared in the plan pass under their declared command.
- `git diff {base_branch}...HEAD --name-status` matches the plan's aggregated File Structure (skill-10-smoke-test will cross-check this at milestone time; you should self-check it now).
- Commit message format: `task: {task_id} — plan-passthrough complete ({source_plan_step_count} steps across {source_plan_task_count} plan-tasks)`.
````

**Step 4a.3**: Why this is cleaner than inlining the plan steps verbatim into the prompt: the writing-plans format is purpose-built for `superpowers:executing-plans` and `superpowers:subagent-driven-development` to consume. Re-encoding the steps into a prd2impl prompt would duplicate that contract and drift out of sync as superpowers evolves. The subagent just opens the plan file like any developer would and follows it.

**Step 4a.4**: Verify the dispatch prompt. Before launching the agent, print the constructed prompt to logs (debug-level). Confirm it contains:
- `## Plan-Passthrough Execution`
- The literal `source_plan_path` value (not a placeholder)
- The "Required workflow" section
- The "Hard rules" section
- The "Completion criteria" section

If any are missing, halt — there's a template bug.

### Step 5: Dispatch Agents

Use the Agent tool to launch tasks in parallel.

**CRITICAL: Verify HEAD is on the correct base branch before dispatching.**
Right before the first Agent call, run:
```bash
git branch --show-current   # Must be the base branch from Step 2a
git log --oneline -1         # Confirm it's the expected latest commit
```
If HEAD is not on the expected base branch, `git checkout {base_branch}` first.

```
For Green tasks: run_in_background=true (they can work independently)
For Yellow tasks: run_in_background=true (they'll stop at review checkpoint)
```

**Dispatch rules**:
- Maximum 5 concurrent agents (to avoid resource contention)
- If >5 tasks, dispatch in waves
- Each agent uses `isolation: "worktree"` — worktree is created from current HEAD, which MUST be the synced base branch
- Group agents by line (tasks on different lines don't conflict)
- **Include base branch info in each agent prompt**: "Your worktree was created from `{base_branch}` at commit `{sha}`"

### Step 6: Monitoring Dashboard

After dispatch, output a monitoring table:

```
## Batch {N} Dispatch — {timestamp}

| Task ID | Name | Type | Agent | Status | Expected Output |
|---------|------|------|-------|--------|-----------------|
| T1A.3 | EventBus | 🟢 | agent-1 | 🚀 dispatched | eval-doc |
| T1A.6 | Placeholder | 🟢 | agent-2 | 🚀 dispatched | eval-doc |
| T1A.7 | Lifecycle plugin | 🟢 | agent-3 | 🚀 dispatched | eval-doc |

📊 Progress: 0/3 complete
⏰ Estimated completion: ~30 min
🔍 Check status: /task-status

Next check recommended in 15 minutes.
```

### Step 7: Completion Handling

As agents complete (via background notifications):
1. Read agent output
2. Verify deliverables were produced
3. Update task-status.md
4. Report to user:
   ```
   Agent completed: T1A.3 (EventBus)
   ✅ eval-doc produced → needs your review
   
   Remaining: 2/3 agents still running
   ```

## Safety Rules

- **Never dispatch Red tasks** — they require human-in-the-loop from the start
- **Never dispatch tasks with unmet dependencies** — even if user insists, warn and require explicit override
- **Always use worktree isolation** — prevent file conflicts between parallel agents
- **Always verify branch freshness before dispatch** — worktrees inherit the base branch HEAD; stale base = stale worktrees = merge conflicts
- **Limit concurrency** — respect system resources, max 5 agents
- **Auto-stop on conflict** — if two agents try to modify the same file, pause and alert

## Fallback (No Agent Tool)

If the Agent tool is not available or the user prefers manual dispatch:
1. Generate a list of `/start-task` commands the user can run sequentially
2. Suggest opening multiple terminal tabs
3. Provide the monitoring table for manual tracking
