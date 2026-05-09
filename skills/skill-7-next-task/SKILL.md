---
name: next-task
description: "Recommend the next executable task based on dependency satisfaction, priority, and team assignment. Use when the user says 'what should I do next', 'next task', 'recommend task', or runs /next-task."
---

# Skill 7: Next Task

<SUBAGENT-STOP>
If you were dispatched as a subagent to execute a specific task, skip this skill.
</SUBAGENT-STOP>

Analyze the task graph and recommend the best next task(s) to work on.

## Trigger

- User runs `/next-task [identity]`
- User says "what should I do next", "next task", "recommend a task"
- Called automatically after task completion

## Input

- **Optional**: Identity hint (e.g., `Dev1`, `Alice`), inferred from git branch if not provided
- **Data sources**:
  1. `{plans_dir}/tasks.yaml` (preferred)
  2. `{plans_dir}/task-status.md` (fallback)
  3. `{plans_dir}/*-execution-plan.yaml` (for batch context)

## Execution Flow

> **Path resolution**: Before constructing any read/write path, resolve `{plans_dir}` per `lib/plans-dir-resolver.md`. All `docs/plans/` references (except `docs/plans/project.yaml`, which stays at repo root) are relative to that resolved directory. Bare references to `tasks.yaml`, `task-status.md`, etc. are also `{plans_dir}`-scoped.

### Step 1: Identify Current Developer

1. Check user-provided identity argument
2. If not provided, infer from git branch:
   - Match branch name against `project.yaml` team entries
   - If only 1 team member → auto-select
   - If no match → ask user to pick from team list

### Step 2: Check In-Progress Tasks

1. Scan for tasks with status `in_progress` (🟦) owned by this developer
2. If found:
   ```
   You have an in-progress task:
   🟦 {Task ID} — {name} ({type})
   
   Suggest: /continue-task {Task ID}
   
   Or if you want to park it and pick something else, 
   update its status first.
   ```
3. If no in-progress tasks, proceed to recommendation

### Step 3: Find Executable Tasks

**CRITICAL: Only recommend tasks with status `pending` (⬜). NEVER recommend tasks that are `completed` (🟩), `in_progress` (🟦), `blocked` (⚠️), or `failed` (🟥).**

A task is **executable** if ALL of these are true:
- Status is EXACTLY `pending` (⬜) — reject any other status
- All `depends_on` tasks have status EXACTLY `completed` (🟩)
- No items in `blocked_by` are active
- Task line matches developer's line or is `shared`
- **Not tombstoned** (0.4.0+): drop any task with `tombstone: true`,
  `status: DEFERRED_*`, or a leading `TOMBSTONE:` comment per the
  tombstone gate in `using-prd2impl/SKILL.md`. If after filtering the
  candidate set is empty AND tombstoned tasks exist, return:
  > "No active candidates. N tasks are tombstoned (deferred to future
  > milestones); run `/task-status` for details."

**Parsing task-status.md (fallback mode):**
When reading markdown tables, pay careful attention to the status column emoji:
- ⬜ = pending (ONLY these are candidates)
- 🟦 = in_progress (SKIP)
- 🟩 = completed (SKIP)
- ⚠️ = blocked (SKIP)
- 🟥 = failed (SKIP)

If unsure about a task's status, re-read the specific row. Do NOT guess.

Algorithm:
1. Load all tasks
2. **First pass: collect ONLY tasks where status column is ⬜ pending** — discard everything else
3. **Second pass: from the pending set**, filter to dependencies satisfied + matching line
4. Sort by priority:
   a. **Critical path first**: Tasks on the critical path get top priority
   b. **Type priority**: Green > Yellow > Red (Green can be started immediately without waiting)
   c. **Phase order**: Earlier phase tasks before later ones
   d. **Batch order**: Tasks in the current/next batch first
   e. **Downstream impact**: Tasks that unblock the most other tasks rank higher

### Step 4: Check for Urgent Items

Before presenting the recommendation, check for:
- **Red tasks that need early start**: Check execution plan for Red tasks scheduled to start in parallel with the current milestone
- **Blocked tasks that became unblocked**: Tasks that were blocked but whose blocker was recently resolved
- **Overdue milestones**: If current date > milestone target date and tasks remain

### Step 5: Verify & Present Recommendations

**Before outputting, verify each recommended task:**
For each task in your recommendation list, re-read its row in task-status.md and confirm the status emoji is ⬜. If it's not ⬜, remove it from the list. This catches parsing errors.

Output a table of up to 5 recommended tasks:

```
## Recommended Tasks for {Developer}

Current milestone: {Mx} ({milestone name})
Current batch: batch-{n}

| # | Task ID | Name | Type | Batch | Unblocks | Est. Effort |
|---|---------|------|------|-------|----------|-------------|
| 1 | T1A.3 | EventBus | 🟢 | 2 | 4 tasks | small |
| 2 | T1A.4 | Soul.md | 🟡 | 2 | 3 tasks | medium |
| 3 | T1A.6 | Placeholder stream | 🟢 | 3 | 1 task | small |
| 4 | T2A.1 | Protocol commands | 🟢 | 4 | 5 tasks | medium |
| 5 | T3A.4 | Compliance schema | 🔴 | 5 | 3 tasks | large |

⚠️ Note: T3A.4 (Red) is scheduled for early start — consider beginning this week.

Pick one: /start-task T1A.3
```

### Step 6: Parallel Dispatch Option

If multiple Green tasks are available and independent:
```
💡 Tasks {T1A.3, T1A.6, T1A.7} are all Green, independent, and in the same batch.
Consider batch dispatch: /batch-dispatch batch-2
```

## Edge Cases

- **No tasks available**: All remaining tasks are blocked or belong to other lines
  → Report blocked status and suggest checking with other team members
- **Only Red tasks left**: All Green/Yellow done, only Red remain
  → Present Red tasks with their decision questions
- **All tasks complete**: Congratulations! Suggest `/smoke-test {current-milestone}`
- **Cross-line task**: If a `shared` task is available and no line-specific tasks are
  → Suggest the shared task with a note about coordination
- **Solo developer**: Skip line filtering entirely, show all executable tasks
