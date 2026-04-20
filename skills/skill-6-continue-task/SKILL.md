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
- User runs `/continue-task {Task ID} --autopilot={green|yellow|all}`
- User says "continue T1A.1", "resume task", "next step for T1A.1"
- User says "approved {Task ID}" (for Yellow/Red tasks)

## Input

- **Required**: Task ID
- **Optional**: `--autopilot={green|yellow|all}` — auto-approve default decisions at STOP points. If omitted, this skill **reads `autopilot: {level}` meta from task-status.md** (set by prior `/start-task --autopilot=...` or `/autorun`). Explicit flag overrides stored meta.
- **Context**: Current conversation history, `.artifacts/registry.json`

## Execution Flow

> **Path resolution**: Before constructing any read/write path, resolve `{plans_dir}` per `lib/plans-dir-resolver.md`. All `docs/plans/` references (except `docs/plans/project.yaml`, which stays at repo root) are relative to that resolved directory. Bare references to `tasks.yaml`, `task-status.md`, etc. are also `{plans_dir}`-scoped.

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

> **Autopilot note:** if `--autopilot={level}` was passed OR task-status
> carries `autopilot: {level}` meta, every STOP point below is replaced by
> an auto-proceed rule. Rules are defined in the
> [Autopilot Mode section of skill-5-start-task](../skill-5-start-task/SKILL.md#autopilot-mode).
> The same semantics apply here (same levels, same non-overridable
> safeguards). Do not duplicate the table — honor it by reference.

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
4. If failures → **classify the failure surface first**:
   - **UI surface with Playwright evidence** (failed test produced
     `test-failed-*.png` / `video.webm` / `trace.zip` under the e2e-report's
     `evidence/{test_id}/`) → enter the **UI-regression closed loop**
     (Step 4a below). Skip the traditional debug retry.
   - **All other failures** (terminal, API, unit-level): **diagnose via
     `superpowers:systematic-debugging` (if available)**, fix, re-run (up to
     3 attempts). The debugging skill enforces hypothesis / evidence
     discipline instead of guess-and-patch cycles. If unavailable, proceed
     with ad-hoc diagnosis.
5. If still failing after 3 attempts (non-UI path) or 2 iterations (UI
   closed-loop path) → use diagnostic template:
   ```
   {Task ID} dev-loop failing after {N} attempts.
   Common failure: {pattern}
   Possible causes:
   a) Contract mismatch → run /contract-check
   b) Missing Red decision → mark blocked
   c) Logic bug → {specific location}
   d) Bad test case → revise test-plan
   e) Visual regression unresolvable → escalate to design review
   ```

#### Step 4a: UI-regression closed loop (new)

Triggers only when a failed test's evidence directory contains Playwright
artifacts. Purpose: turn a visual failure into a new eval-doc → new test-plan
→ new test-code cycle automatically, instead of hand-patching the
implementation and guessing what "looked wrong".

Loop iteration (cap: 2 iterations per task; combined with the 3-attempt
non-UI debug path this yields a hard cap of 5 total retries before the
diagnostic template):

1. **Collect inputs** — for each failed UI test:
   - Path to `test-failed-*.png` (actual viewport on failure)
   - Path to `video.webm` / `trace.zip` (if present)
   - pytest traceback
   - The task's most recent eval-doc (expected behavior / mockup)

2. **Invoke skill-5-feature-eval in verify mode, automated sub-flow**
   (see dev-loop-skills/skill-5-feature-eval SKILL.md "Verify 模式 → 自动反馈来源"):
   - Input: the artifacts from step 1
   - Output: a new eval-doc with `visual_classification` filled
     (`layout-broken` / `content-mismatch` / `element-missing` /
     `selector-drift` / `timing-flaky`)

3. **Route by classification**:
   - `selector-drift` / `timing-flaky` → invoke `skill-3-test-code-writer`
     directly to adjust test selectors or waits. **Do not change
     implementation code.** Re-run skill-4.
   - `layout-broken` / `content-mismatch` / `element-missing` → invoke
     `skill-2-test-plan-generator` with the new eval-doc to produce an
     incremental test-plan, then `skill-3-test-code-writer` to extend the
     test suite, then implementation fix, then skill-4 re-run.

4. **Track iteration chain** — update `.artifacts/registry.json` on the task
   entry:
   ```json
   {
     "iteration_chain": [
       "eval-{name}-001",
       "test-plan-{name}-001",
       "test-diff-{name}-001",
       "e2e-report-{name}-001",   // first failure
       "eval-{name}-002",          // verify-mode auto-iteration
       "test-plan-{name}-002",     // or test-diff-{name}-002 for selector-drift
       "e2e-report-{name}-002"     // re-run
     ]
   }
   ```
   Each iteration **must** add at least one new artifact ID. If a retry
   produces no new artifact (e.g., AI tweaked impl in place), that retry does
   not count against the cap — but also means the loop is not making
   traceable progress; flag it.

5. **Termination**:
   - Green on re-run → proceed to closing (Step 4 success path)
   - Still red after iteration 2 → emit the diagnostic template from Step 5
     above, include `iteration_chain` and the last classification, stop for
     human review.

#### All green → Close Task
1. **Independent review (recommended):** invoke
   `superpowers:requesting-code-review` if available. It dispatches the
   `code-reviewer` subagent so the review is not self-graded. Receive and
   process feedback via `superpowers:receiving-code-review` before closing.
   On unavailable → skip and proceed (Yellow/Red tasks already have human
   review; Green tasks will still be caught at milestone smoke-test).
2. Update task status: `in_progress` → `completed` (🟩)
3. Fill artifact links in task-status (eval-doc, test-plan, test-diff, e2e-report IDs)
4. Commit: `task: {ID} → completed`
5. Push to the task owner's branch
6. Recommend next available task:
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
- **Autopilot meta present but superpowers unavailable** (Yellow review path): if `autopilot: yellow` or `all` is set but `superpowers:requesting-code-review` cannot be invoked for a Yellow review checkpoint, **fall back to STOP** rather than self-approving the draft. Record the reason in the status update. Red tasks in `all` mode continue with default-picking since that path does not require an independent reviewer.
