---
name: continue-task
description: "Resume a task at its next dev-loop checkpoint. Determines current progress and advances to the next step (eval → test-plan → test-code → implement → test-run → complete). Use when the user says 'continue task', 'resume', 'next step for T1A.1', or runs /continue-task."
---

# Skill 6: Continue Task

<SUBAGENT-STOP>
If you were dispatched as a subagent to execute a specific task, skip this skill.
</SUBAGENT-STOP>

Resume a task that's already `in_progress`, determine where it left off, and advance to the next dev-loop step.

## Trigger

- User runs `/continue-task {Task ID}`
- User says "continue T1A.1", "resume task", "next step for T1A.1"
- User says "approved {Task ID}" (for Yellow/Red tasks)

## Input

- **Required**: Task ID
- **Context**: Current conversation history, `.artifacts/registry.json`

## Execution Flow

### Step 1: Verify Task State

1. Load task from `tasks.yaml` or `task-status.md`
2. Confirm status is `in_progress` (🟦)
3. If not in_progress:
   - If pending → suggest `/start-task {ID}`
   - If completed → inform user, suggest `/next-task`
   - If blocked → show blocker, ask if resolved

### Step 2: Determine Current Progress

Check what artifacts exist for this task (in order of the pipeline):

| Artifact | Found? | Implies |
|----------|--------|---------|
| eval-doc | No | Start from eval-doc (skill-5-feature-eval) |
| eval-doc | Yes, not reviewed | Waiting for user review |
| eval-doc | Yes, reviewed | Proceed to test-plan |
| test-plan | Yes, not confirmed | Waiting for user confirmation |
| test-plan | Yes, confirmed | Proceed to test-code |
| test-diff | Yes | Proceed to implementation |
| Implementation code | Yes | Proceed to test-runner |
| e2e-report (green) | Yes | Ready for closing |

**Detection methods**:
1. Check `.artifacts/registry.json` for artifacts tagged with this task ID
2. Check conversation context for recent review/approval
3. Check git log for recent commits mentioning this task ID
4. If user says "approved" or "confirmed" → treat as approval for the pending artifact

### Step 3: Execute Next Step

Based on detected progress:

#### After eval-doc review → Test Plan
1. Invoke `skill-2-test-plan-generator` (from dev-loop-skills)
2. Use the eval-doc as input
3. Produce test-plan artifact
4. **STOP — wait for user confirmation**

#### After test-plan confirmation → Test Code
1. Invoke `skill-3-test-code-writer` (from dev-loop-skills)
2. Use the confirmed test-plan as input
3. Write test files to the project
4. Report what tests were written

#### After test code → Implementation
1. Read the test files to understand expected behavior
2. Implement the business logic to make tests pass
3. Follow existing code patterns in the project
4. Run tests incrementally as you implement

#### After implementation → Test Runner
1. Invoke `skill-4-test-runner` (from dev-loop-skills)
2. Run the full test suite for this task's scope
3. If all green → proceed to closing
4. If failures → diagnose, fix, re-run (up to 3 attempts)
5. If still failing after 3 attempts → use diagnostic template:
   ```
   {Task ID} dev-loop failing after 3 attempts.
   Common failure: {pattern}
   Possible causes:
   a) Contract mismatch → run /contract-check
   b) Missing Red decision → mark blocked
   c) Logic bug → {specific location}
   d) Bad test case → revise test-plan
   ```

#### All green → Close Task
1. Update task status: `in_progress` → `completed` (🟩)
2. Fill artifact links in task-status (eval-doc, test-plan, test-diff, e2e-report IDs)
3. Commit: `task: {ID} → completed`
4. Push to the task owner's branch
5. Recommend next available task:
   ```
   Task {ID} completed! ✅
   
   Next available tasks (dependencies satisfied):
   1. T1A.3 — EventBus (Green, same module)
   2. T1A.4 — Soul.md (Yellow, needs review)
   
   Run /start-task {recommended} or /next-task for full list.
   ```

### Step 4: Handle Yellow/Red Task Approval

If the user says "approved {Task ID}" or "rejected {Task ID}: {reason}":

**Approved**:
1. Commit the drafted deliverables
2. Mark task completed (🟩)
3. Fill artifact links
4. Commit: `task: {ID} → completed (approved)`

**Rejected**:
1. Mark task as `failed` (🟥) with rejection reason
2. Note the feedback
3. Re-draft based on feedback
4. Re-submit for review (status back to `review_pending`)
5. SLA: complete revision within 30 minutes

## Resuming After Context Loss

If the conversation context was lost (new session):

1. Read `task-status.md` to find in_progress tasks
2. Read `.artifacts/registry.json` for this task's artifacts
3. Read recent git log for commits mentioning this task
4. Reconstruct progress state
5. Report to user:
   ```
   Resuming {Task ID} ({name}).
   Last detected step: {step}
   Artifacts found: {list}
   Last commit: {hash} "{message}"
   
   Suggested next action: {what to do}
   ```

## Error Recovery

- **Conflict with another task**: If the current task's files conflict with another in_progress task, flag immediately
- **Missing dev-loop-skills**: If dev-loop-skills aren't installed, fall back to manual test writing (skip skill-2/3/4, do implementation directly with manual testing)
- **Artifact registry corrupted**: Rebuild from git log + file existence checks
