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
- User runs `/start-task {Task ID} --autopilot={green|yellow|all}` (no STOP points)
- User says "start task T1A.1", "launch T1A.1", "begin working on T1A.1"

## Input

- **Required**: Task ID (e.g., `T1A.1`)
- **Optional**: `--autopilot={green|yellow|all}` — auto-approve default decisions at STOP points. See "Autopilot Mode" below.
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
   - Match branch name against `project.yaml` team entries (each member has a `branch` field)
   - If no match found → ask user to identify themselves from the team list
   - If `project.yaml` has only 1 team member → auto-assign
3. Update `tasks.yaml` (if exists) and `task-status.md`
4. Commit: `task: {ID} → in_progress ({Owner})`

### Step 4: Load Context

1. Read task deliverables to understand expected output
2. Read verification criteria
3. Read related contract files (`docs/contracts/*`) if referenced
4. Read the PRD sections relevant to this task (via `story_refs` → `prd-structure.yaml`)

### Step 5: Enter Type-Specific Workflow

> **Autopilot note:** if `--autopilot` was passed, the STOP points in the
> subsections below become **auto-proceed** per the "Autopilot Mode" section
> at the bottom of this skill. Read that section before executing.

#### Green Tasks (AI-independent)

Full dev-loop pipeline:
1. Enter `skill-5-feature-eval` (from dev-loop-skills) in **simulate** mode
2. Produce eval-doc
3. **STOP — wait for user review**

After user approves eval-doc, the flow continues via `/continue-task`:
eval-doc → test-plan → test-code → implementation → test-runner → complete

**Implementation discipline (strongly recommended):** when `/continue-task`
reaches the implementation step, invoke `superpowers:test-driven-development`
if available. It enforces red/green/refactor rhythm while dev-loop owns the
plan and runner. Division of labor:
- `dev-loop-skills:skill-2-test-plan-generator` — produces the **what** (test-plan)
- `dev-loop-skills:skill-3-test-code-writer` — produces the **how** (pytest code)
- `superpowers:test-driven-development` — enforces the **rhythm** (one failing test at a time, minimal code to green, then refactor)
- `dev-loop-skills:skill-4-test-runner` — produces the **verdict** (new vs regression report)

If `superpowers` is unavailable, proceed without TDD rhythm enforcement — the
dev-loop plan/code/runner chain still works.

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

**Pre-draft brainstorm (recommended):** invoke
`superpowers:brainstorming` if available before drafting. Red tasks hinge on
design decisions — brainstorming surfaces the trade-off space so the questions
listed below are grounded, not speculative.

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

## Autopilot Mode

When `--autopilot={level}` is passed, STOP checkpoints are replaced by
auto-proceed rules. The flag **must be persisted** to task-status meta so
`/continue-task` and subsequent re-entries honor it without re-passing.

Persist by writing a meta line to `task-status.md` under the task:
`autopilot: {level}` (removed automatically when task reaches `completed`
or `failed`).

### Level semantics

| Level | Green | Yellow | Red |
|-------|-------|--------|-----|
| `green` | auto-proceed through eval-doc, test-plan, impl, test-run | fall back to normal STOP | fall back to normal STOP |
| `yellow` | auto-proceed | auto-proceed via self-review pass (see below) | fall back to normal STOP |
| `all` | auto-proceed | auto-proceed | default-pick on every design decision + explicit audit marker |

### Auto-proceed replaces STOP with

- **After eval-doc** (Green): do not stop for user review. Log the eval-doc
  path + a one-line "AI-self-reviewed: assumptions look consistent with PRD
  section {ref}" note, then proceed to test-plan.
- **After test-plan**: do not stop for user confirmation. Sanity-check:
  every TC has a priority and references a deliverable; if OK, proceed.
  If sanity-check fails, treat as a terminal failure (mark blocked, do not
  fabricate a plan).
- **After review checklist** (Yellow): do not stop for user approval.
  Instead invoke `superpowers:requesting-code-review` for an independent
  review pass. If the reviewer returns ≥1 blocking issue, revise **once**,
  then accept and commit. Record reviewer verdict in commit message:
  `task: {ID} → completed (autopilot-yellow, reviewer: {one-line verdict})`.
  If `superpowers:requesting-code-review` is unavailable, **do not
  auto-approve Yellow** — fall back to STOP regardless of level.
- **Design decisions** (Red, `all` only): pick the most
  reversible / least lock-in option and record the rationale inline.
  Commit: `task: {ID} → completed (autopilot-all, DEFAULT-PICKED)`.
  Every auto-picked Red decision must be logged to
  `.artifacts/autopilot-decisions.log` for retroactive audit.

### Autopilot never overrides

- Pre-flight dependency checks (Step 2) — still refuse to start if
  dependencies are unmet; autopilot does not "override and start anyway"
- Worktree base-branch safety (from skill-8 preflight) — still syncs `dev`
  and refuses to dispatch on dirty tree
- Test failure 3-retry cap — after 3 failed attempts autopilot marks the
  task `failed` and surfaces it; does **not** fabricate passing tests
- `files_touched` scope breach — any edit outside declared scope halts the
  task and surfaces for human triage

### How invoked by /autorun

`skill-13-autorun` always calls this skill with the level it received. If
a user invokes `/start-task {ID}` without a flag but the task-status already
has `autopilot: {level}` meta (inherited from a previous autorun invocation
on the same task), this skill honors that meta.
