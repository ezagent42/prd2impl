---
name: autorun
description: "Full-autopilot orchestrator — AI picks task order and parallelism, auto-approves default decisions, and drives all remaining tasks to completion without STOP checkpoints. Use when the user says 'autorun', 'full autopilot', 'run everything', '全托管', or runs /autorun."
---

# Skill 13: Autorun (Full Autopilot)

<SUBAGENT-STOP>
If you were dispatched as a subagent to execute a specific task, skip this skill.
</SUBAGENT-STOP>

Orchestrate the entire task queue autonomously. Pick order, pick parallelism, auto-approve default decisions at every dev-loop STOP point, and drive to completion.

## Trigger

- `/autorun` — autopilot all Green tasks (safe default)
- `/autorun green` — same as above
- `/autorun yellow` — autopilot Green + Yellow (AI self-reviews Yellow drafts)
- `/autorun all` — autopilot Green + Yellow + Red (AI picks default on every design decision; **risky**)
- `/autorun until {milestone}` — stop when the given milestone passes smoke-test
- `/autorun {task-ids}` — autopilot a specific subset
- Natural language: "跑完所有任务", "全托管", "finish everything"

## Preflight

Before the loop starts, confirm scope with a **one-shot summary** (not a question):

```
Autorun starting — level: {green|yellow|all}
Scope: {N} tasks in queue ({G} Green, {Y} Yellow, {R} Red)
Will skip: {what's excluded based on level}
Stop conditions: test failure after 3 retries, dependency cycle, explicit STOP commit marker
Estimated parallelism: up to {K} concurrent worktrees

Starting in 10s. Type 'cancel' to abort.
```

If `--dangerously-skip-permissions` is NOT in effect, warn once:

```
⚠️ Claude Code is in interactive-permission mode. Autorun will still prompt
for Bash/Edit. For true hands-off mode, restart with:
  claude --dangerously-skip-permissions
or set .claude/settings.json → permissions.defaultMode = "bypassPermissions".

Continue in interactive mode anyway? (yes/cancel)
```

## Execution Flow

> **Path resolution**: Before constructing any read/write path, resolve `{plans_dir}` per `lib/plans-dir-resolver.md`. All `docs/plans/` references (except `docs/plans/project.yaml`, which stays at repo root) are relative to that resolved directory. Bare references to `tasks.yaml`, `task-status.md`, etc. are also `{plans_dir}`-scoped.

### Step 1: Build Work Queue

1. Load `tasks.yaml` and `execution-plan.yaml` (if present)
2. Filter by autopilot level:
   - `green` → only `type == Green`
   - `yellow` → `type in [Green, Yellow]`
   - `all` → all non-completed tasks
3. Exclude: tasks already `completed`, tasks marked `blocked` with no resolution, tasks with unmet external `blocked_by`
4. Topologically sort by `depends_on`; tasks at the same depth are **parallelizable candidates**

### Step 2: Plan Parallelism

For each dependency level (batch):

1. Read `project.yaml` → `autorun.max_parallel` (default: 3; cap: 5)
2. Partition the level into parallel groups of ≤ `max_parallel`
3. Verify no two tasks in the same group touch overlapping files:
   - Read `task.files_touched` if declared in tasks.yaml
   - If not declared, assume safe within the same `module` only if explicitly marked `parallel_safe: true`; otherwise serialize
4. Emit a plan preview (one screen) and proceed — do **not** stop for confirmation unless `--dry-run` was passed

### Step 3: Dispatch Loop

For each planned group:

1. If group size > 1 → invoke `skill-8-batch-dispatch` with `--autopilot={level}`
2. If group size == 1 → invoke `skill-5-start-task {ID} --autopilot={level}`
3. Wait for all agents in the group to report completion (success or terminal failure)
4. For each completed task, invoke `skill-6-continue-task {ID} --autopilot={level}` if not already auto-closed
5. Update `task-status.md` after each task state transition
6. Commit progress after every **group** (not every task — keeps history readable)

### Step 4: Handle Failures

Autorun does **not** ask for permission to retry or fix. It follows this decision tree:

| Failure mode | Action |
|--------------|--------|
| Test failure (attempt 1-3) | Re-enter `skill-6-continue-task` with diagnostic context; invoke `superpowers:systematic-debugging` if available |
| Test failure after 3 retries | Mark task `failed`, record diagnostic report, **continue with rest of queue**, surface at end |
| Dependency cycle detected | Halt queue, report cycle, exit with NO-GO |
| Contract drift | Invoke `/contract-check`; if impact is bounded to Green tasks, auto-replan; else halt |
| Worktree conflict / dirty tree | Clean worktree via `ExitWorktree`, retry once, then mark `failed` |
| Missing Red decision (in `yellow` mode) | Mark task `blocked: needs Red decision`, skip, continue |

### Step 5: Self-Review Checkpoints (Yellow mode)

In `--autopilot=yellow` or `all`, Yellow tasks still need a "review". Autorun performs a **self-review pass** instead of human STOP:

1. Draft the Yellow deliverable
2. Invoke `superpowers:requesting-code-review` to dispatch the `code-reviewer` subagent (independent review — not self-graded)
3. If reviewer returns ≥1 **blocking** issue → revise once, then accept (do not loop indefinitely)
4. Record reviewer verdict in the commit message: `task: {ID} → completed (autopilot-yellow, reviewer: {summary})`

If `superpowers:requesting-code-review` is unavailable, Yellow tasks are **always deferred** (not auto-completed) regardless of level.

### Step 6: Red-Task Default Picking (`all` mode only)

For Red tasks in `--autopilot=all`:

1. Draft the deliverable as normal
2. For each design-decision question, **pick the most conservative / least-lock-in option** and record the rationale:
   - "Option X chosen: it's reversible. Option Y would require a schema migration."
3. Commit with explicit marker: `task: {ID} → completed (autopilot-all, DEFAULT-PICKED)`
4. Emit a **post-run red-decisions review list** at the end of autorun — user sees every auto-picked Red decision in one place for retroactive audit

### Step 7: Milestone Gates

If the queue crosses a milestone boundary:

1. At each boundary, invoke `skill-10-smoke-test {milestone}`
2. If smoke-test passes → continue
3. If smoke-test fails → halt queue, report, exit NO-GO (do **not** auto-fix milestone failures; those deserve human triage)
4. If `/autorun until {milestone}` → exit after that milestone's smoke-test (pass or fail)

### Step 8: Final Report

When the queue drains (or halts), emit:

```
Autorun complete — level: {green|yellow|all}
Duration: {HH:MM:SS}
Completed: {N} tasks ({G} Green, {Y} Yellow, {R} Red)
Failed: {M} tasks — see details below
Auto-picked Red decisions: {K} — listed below for audit
Milestones passed: {list}

--- Failures ---
{per-task diagnostic summary}

--- Red Decisions Log ---
{per-decision: task, question, chosen option, rationale}

Next: {/smoke-test {next-milestone} | /retro | /task-status}
```

## Safeguards (Non-Negotiable)

These apply even in `--autopilot=all`:

1. **Never `git push --force`** to shared branches (dev, main)
2. **Never merge to integration branch** without smoke-test green
3. **Never delete a worktree with uncommitted changes** that haven't been pushed to the task owner's branch
4. **Halt and surface** on any change outside the declared task scope (`files_touched` breach)
5. **Commit every group boundary** so the user can always `git log` + revert a single group

## State Machine

```
queue_building → planning → dispatching → awaiting_group → processing_group → 
  (success)  → next_group or done
  (failure)  → diagnose → (recoverable → retry) or (terminal → mark_failed → next_group)
  (cancel)   → halt → final_report
```

## Resume After Interrupt

If autorun is interrupted (user cancel, context loss, crash):

1. On `/autorun resume`: read `task-status.md`, find last `in_progress` set, re-plan the remaining queue at the same level
2. Do not retry `failed` tasks automatically — user must `/start-task` them manually (autorun already tried 3x)

## Error Recovery

- **No `project.yaml` → autorun.max_parallel**: fall back to 3
- **No `execution-plan.yaml`**: build batches ad-hoc from `tasks.yaml` dependency graph
- **`superpowers:dispatching-parallel-agents` unavailable**: serialize the queue (log a warning once)
- **User typed `cancel` during preflight countdown**: abort cleanly, no state changes

## Companion Skill Dependencies

| Mode | Required | Degrades gracefully if missing |
|------|----------|-------------------------------|
| `green` | skill-5, skill-6 | skill-8 (sequential fallback), dev-loop-skills, superpowers:systematic-debugging |
| `yellow` | `green` reqs + `superpowers:requesting-code-review` | (Yellow tasks deferred if review unavailable) |
| `all` | `yellow` reqs | superpowers:brainstorming (Red tasks still run with default-picking) |
