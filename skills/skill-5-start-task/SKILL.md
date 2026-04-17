---
name: start-task
description: "Launch a task into the dev-loop pipeline. Reads task definition, checks dependencies, updates status, and enters the appropriate workflow (Green/Yellow/Red). Use when the user says 'start task', 'launch task', 'begin T1A.1', or runs /start-task."
---

# Skill 5: Start Task

<SUBAGENT-STOP>
If you were dispatched as a subagent to execute a specific task, skip this skill.
</SUBAGENT-STOP>

Launch a specific task, verify its prerequisites, update the status tracker, and enter the appropriate dev-loop workflow based on task type.

## Trigger

- User runs `/start-task {Task ID}` (e.g., `/start-task T1A.1`)
- User says "start task T1A.1", "launch T1A.1", "begin working on T1A.1"

## Input

- **Required**: Task ID (e.g., `T1A.1`)
- **Data sources** (checked in order):
  1. `docs/plans/tasks.yaml` (structured, preferred)
  2. `docs/plans/*-tasks*.md` (markdown fallback)
  3. `docs/plans/task-status.md` (legacy fallback)

## Execution Flow

### Step 1: Load Task Definition

1. Find the task by ID in `tasks.yaml` or fallback to markdown files
2. Extract: name, type, phase, dependencies, deliverables, verification criteria
3. If task not found, list similar task IDs and ask user to clarify

### Step 2: Dependency Check

1. For each task in `depends_on`, verify status is `completed` (🟩)
2. Check `blocked_by` for external blockers
3. If any dependency is not met:
   ```
   Cannot start {Task ID}: dependency {Dep ID} is {status}.
   
   Options:
   1. Start {Dep ID} first (/start-task {Dep ID})
   2. Override and start anyway (if you know the dependency is soft)
   3. See other available tasks (/next-task)
   ```
4. If all dependencies are met, proceed

### Step 3: Update Status

1. Set task status to `in_progress` (🟦)
2. Set owner based on current git branch:
   - Branch `dev-a` or containing `dev-a` → DevA
   - Branch `dev-b` or containing `dev-b` → DevB
   - Other → ask user for identity
3. Update `tasks.yaml` (if exists) and `task-status.md`
4. Commit: `task: {ID} → in_progress ({Owner})`

### Step 4: Load Context

1. Read task deliverables to understand expected output
2. Read verification criteria
3. Read related contract files (`docs/contracts/*`) if referenced
4. Read the PRD sections relevant to this task (via `story_refs` → `prd-structure.yaml`)

### Step 5: Enter Type-Specific Workflow

#### Green Tasks (AI-independent)

Full dev-loop pipeline:
1. Enter `skill-5-feature-eval` (from dev-loop-skills) in **simulate** mode
2. Produce eval-doc
3. **STOP — wait for user review**

After user approves eval-doc, the flow continues via `/continue-task`:
eval-doc → test-plan → test-code → implementation → test-runner → complete

#### Yellow Tasks (AI + human review)

Modified workflow:
1. Read PRD section and related references
2. Read existing code in the area for style/pattern consistency
3. Draft the deliverable(s)
4. Set status to `review_pending` in task-status
5. Output a **Review Checklist**:
   ```
   ## Review Checklist for {Task ID}
   - [ ] {Key point 1 to verify}
   - [ ] {Key point 2 to verify}
   - [ ] {Consistency with existing code}
   - [ ] {Domain accuracy}
   ```
6. **STOP — wait for user approval or rejection**

On approval: commit + mark completed
On rejection: note reason, revise, re-submit

#### Red Tasks (Human-driven)

"Draft worker" mode:
1. Read all related reference materials
2. Draft the deliverable (design doc, schema, policy)
3. List **3-5 key design decision questions** for the human:
   ```
   ## Design Decisions for {Task ID}
   1. {Question A}: Option X vs Option Y?
   2. {Question B}: {trade-off description}
   ...
   ```
4. **STOP — do not commit anything**
5. Wait for human decisions
6. After `approved {Task ID}`: commit + mark completed

### Step 6: Report

Output a concise status:
```
Task {ID} ({name}) started.
Type: {Green/Yellow/Red}
Owner: {Owner}
Dependencies: all satisfied ✅
Next step: {what's happening / what we're waiting for}
```

## Status Transitions

```
⬜ pending → 🟦 in_progress  (this skill)
🟦 in_progress → 🟩 completed  (after dev-loop or approval)
🟦 in_progress → ⚠️ blocked   (if blocker discovered)
🟦 in_progress → 🟥 failed    (if rejected, needs redo)
```

## Error Handling

- **Task already in_progress**: Suggest `/continue-task {ID}` instead
- **Task already completed**: Inform user, suggest `/next-task`
- **Task blocked**: Show blocker details, suggest alternatives
- **Missing data files**: Guide user to run upstream skills first
