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
  1. `docs/plans/*-execution-plan.yaml` (for batch definitions)
  2. `docs/plans/tasks.yaml` (for task details)
  3. `docs/plans/task-status.md` (for current status)

## Execution Flow

### Step 1: Resolve Tasks

**If batch ID provided**:
1. Load execution-plan.yaml
2. Find the batch definition
3. Extract task list

**If task IDs provided**:
1. Parse comma-separated IDs
2. Load each task from tasks.yaml

### Step 2: Pre-flight Checks

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

### Step 3: Update Status

For all tasks that pass pre-flight:
1. Mark as `in_progress` (🟦) in task-status
2. Assign owner based on task line (DevA for A-line, DevB for B-line)
3. Commit: `task: batch-{N} dispatch — {IDs} → in_progress`

### Step 4: Construct Agent Prompts

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
"""
```

### Step 5: Dispatch Agents

Use the Agent tool to launch tasks in parallel:

```
For Green tasks: run_in_background=true (they can work independently)
For Yellow tasks: run_in_background=true (they'll stop at review checkpoint)
```

**Dispatch rules**:
- Maximum 5 concurrent agents (to avoid resource contention)
- If >5 tasks, dispatch in waves
- Each agent uses `isolation: "worktree"` to avoid file conflicts
- Group agents by line (A-line tasks don't conflict with B-line tasks)

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
- **Limit concurrency** — respect system resources, max 5 agents
- **Auto-stop on conflict** — if two agents try to modify the same file, pause and alert

## Fallback (No Agent Tool)

If the Agent tool is not available or the user prefers manual dispatch:
1. Generate a list of `/start-task` commands the user can run sequentially
2. Suggest opening multiple terminal tabs
3. Provide the monitoring table for manual tracking
