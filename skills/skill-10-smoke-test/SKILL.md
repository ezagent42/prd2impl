---
name: smoke-test
description: "Milestone gate verification — run automated checks and produce a structured pass/fail report for a milestone. Use when the user says 'smoke test', 'verify milestone', 'M1 gate check', or runs /smoke-test."
---

# Skill 10: Smoke Test

<SUBAGENT-STOP>
If you were dispatched as a subagent to execute a specific task, skip this skill.
</SUBAGENT-STOP>

Run milestone gate verification: check task completion, run automated tests, verify artifacts, and produce a structured go/no-go report.

## Trigger

- User runs `/smoke-test {milestone}` (e.g., `/smoke-test M1`)
- User says "smoke test M1", "verify milestone", "gate check"
- At the end of a milestone when all tasks are expected to be complete

## Input

- **Required**: Milestone ID (e.g., `M0`, `M1`, `M2`)
- **Data sources**:
  1. `{plans_dir}/*-execution-plan.yaml` (milestone definitions, gate checks)
  2. `{plans_dir}/tasks.yaml` or `{plans_dir}/task-status.md` (task statuses)
  3. `.artifacts/registry.json` (artifact completeness)
  4. Batch kickoff files (smoke test scenarios)

## Execution Flow

> **Path resolution**: Before constructing any read path, resolve `{plans_dir}` per `lib/plans-dir-resolver.md`. All `docs/plans/` references (except `docs/plans/project.yaml`, which stays at repo root) are relative to that resolved directory. `.artifacts/` paths are NOT scoped — they remain shared across plans_dir (see design spec §8 Limitation 1).

### Step 0: Layer-3 drift gate (0.4.0+, when dev-loop-skills installed)

`dev-loop-skills:skill-0-project-builder` maintains a
`baseline_commit` frontmatter on the project's "Skill 1" knowledge
file plus a `self-update.sh --check` script returning drift count
(new top-level modules, renamed dirs, etc. since the last bootstrap).

Before running any milestone test verification, check it:

```
/project-builder self-update --check
```

**Gate rule**:
- `drift_count > 50` (configurable via `{plans_dir}/project.yaml::drift_threshold`)
  → emit a STAGED warning prompting user to run `/bootstrap` re-baseline
  before gate close. NOT an automatic NO-GO — drift can be intentional.
- `drift_count <= 50` → proceed silently.

**Why**: a stale module map silently passes milestone gates against
imagined code structure. PV2 shipped `pipeline_v2/kb_mcp/` because
the planning step didn't know `cc_pool.py:691` already auto-injects
an MCP server. A re-baseline before PV2 task-gen would have surfaced
the duplication.

**Graceful degradation**: when `dev-loop-skills` missing, skip with a
logged warning, gate proceeds.

### Step 1: Load Milestone Definition

1. Find the milestone in execution-plan.yaml
2. Extract:
   - Phase and associated tasks
   - Gate checks (verification criteria)
   - Smoke test scenarios
   - Required services

### Step 2: Task Completion Check

Verify all tasks in this milestone's phase are completed:

```
## Task Completion — M1

| Task | Name | Status | Result |
|------|------|--------|--------|
| T1A.1 | Mode/Gate | 🟩 | ✅ Pass |
| T1A.2 | Timer | 🟩 | ✅ Pass |
| T1A.3 | EventBus | 🟩 | ✅ Pass |
| T1B.2 | Message UI | 🟦 | ❌ Still in progress |

Result: 16/17 complete — FAIL (1 task remaining)
```

If any tasks are not complete, report and ask whether to proceed with partial verification.

### Step 2.5: Plan-vs-Actual File Structure Check (0.4.1+, Option B coarse-grained)

**Triggers when**: at least one task in the milestone has `source_plan_path` in its `tasks.yaml` entry.

For each such task, read the matching `task-hints.yaml` entries (rich per-plan-task data) to extract per-plan-task `files.create` + `files.modify` lists. If `task-hints.yaml` is missing or out of sync, re-parse the plan with `skill-0-ingest/lib/plan-parser.md` (Rule 3) as a fallback. Cross-check against actual git history.

The report breaks down to per-PLAN-TASK rows (e.g. `T1 / plan-task-1`, `T1 / plan-task-2`) for granularity, even though the prd2impl task is plan-FILE level. This is the "richness preserved" half of the plan-passthrough deal — task_hints.yaml is the source of truth for that richness.

#### Step 2.5.1 — Build the declared set per plan-task

For each prd2impl task `T` with `source_plan_path = P`:
- Lookup the `task_hints.tasks[]` entries whose `source_plan_path == P` (these are the plan-tasks within this prd2impl task).
- For each such entry `pt` (1-based index `i`), record:
  - `declared_create[T/pt_i] = pt.files.create`
  - `declared_modify[T/pt_i] = pt.files.modify`

If `task-hints.yaml` cannot be located (e.g. ingest-docs was never run or task-hints was deleted), parse `P` directly with plan-parser and use the parsed `tasks[]`. Surface a WARN: "task-hints.yaml not found for {P}; re-parsed plan at smoke-test time (slower; please regenerate via /ingest-docs)."

#### Step 2.5.2 — Build the actual set (one-shot, scoped to base branch)

```bash
git diff --name-status {base_branch}...HEAD | awk '$1 == "A" { print $2 }'    # actually created
git diff --name-status {base_branch}...HEAD | awk '$1 == "M" { print $2 }'    # actually modified
```

Define:
- `actual_create` = the "A" set
- `actual_modify` = the "M" set
- (also note: "D" = deleted, "R..." = renamed — handle as their own row class)

The actual set is computed ONCE for the whole milestone (not per-plan-task) — it's the cumulative diff vs the milestone's base branch.

#### Step 2.5.3 — Compute the four delta sets per plan-task

For each `T/pt_i` row built in Step 2.5.1:

| Delta | Definition | Severity |
|---|---|---|
| `missing_create` | `declared_create[T/pt_i] ∩ NOT(actual_create)` | NO-GO (declared file does not exist) |
| `unexpected_create` | `actual_create - ⋃(declared_create across all T/pt_i)` | WARN (file created outside any plan; reported ONCE at milestone level, not per-plan-task) |
| `declared_modify_not_modified` | `declared_modify[T/pt_i] ∩ NOT(actual_modify ∪ actual_create)` | NO-GO (plan said to modify but no diff) |
| `unexpected_modify` | `actual_modify - ⋃(declared_modify across all T/pt_i)` | WARN (modification outside any plan; reported ONCE at milestone level) |

`declared_modify_not_modified` subtracts `actual_create` because a file declared as "modify" but actually created from scratch in this milestone is a NAMING mismatch, not a missing change — surface it as a WARN with hint "plan said modify; actual was create — was this file new this milestone?"

#### Step 2.5.4 — Build the report block

Add a new section to the gate report (Step 6):

```markdown
## Plan vs Actual File Structure

Each prd2impl task with `source_plan_path` is broken down to its plan-tasks
(read from task-hints.yaml). The "Plan-Task" column shows `{prd2impl-task} /
plan-task-{N}` where N is the 1-based ordinal within the plan.

| Plan-Task | Status | Declared (C/M) | Actual (C/M) | Delta |
|-----------|--------|----------------|--------------|-------|
| T1 / plan-task-1 | ✅ | 5/0 | 5/0 | none |
| T1 / plan-task-2 | ❌ | 2/3 | 2/1 | declared_modify_not_modified: api_routes.py, auth.py |
| T1 / plan-task-4 | ⚠️ | 1/2 | 3/2 | unexpected_create: helpers/utils.py, helpers/__init__.py |

### Blocking deltas (NO-GO contributors)
- T1 / plan-task-2: declared but missing modify on `autoservice/api_routes.py`
- T1 / plan-task-2: declared but missing modify on `autoservice/auth.py`

### Warning deltas (CONDITIONAL GO contributors)
- T1 / plan-task-4: unexpected create `helpers/utils.py` — scope creep or incidental?
```

#### Step 2.5.5 — Gate-decision contribution

- Any `missing_create` row → contributes a NO-GO to the milestone gate.
- Any `declared_modify_not_modified` row → contributes a NO-GO.
- `unexpected_create` and `unexpected_modify` rows are WARNINGs only — they contribute a CONDITIONAL GO if no NO-GO is otherwise present.

#### Step 2.5.6 — Graceful degradation

If NO tasks in the milestone have `source_plan_path`, skip this step entirely (silent — no warning). The milestone may simply not be a plan-passthrough milestone.

If a task has `source_plan_path` but the file is missing, surface a CONDITIONAL GO with the diagnostic "plan file missing — cannot verify file structure" and proceed with Step 3.

### Step 3: Automated Test Verification

#### Primary path (when dev-loop-skills is installed)

Invoke `dev-loop-skills:skill-4-test-runner` and consume its `e2e-report`
artifact. Unlike raw `pytest`, the runner mechanically distinguishes new
failures from regression failures and emits an evidence manifest the
gate can read.

1. Run the test runner scoped to this milestone's phase keyword:
   ```
   /test-runner --phase {phase_keyword} --emit-report
   ```

2. Read the resulting artifact at `.artifacts/e2e-report-{milestone}-*.yaml`.

3. Parse three signal classes from the report:
   - `new_failure: count` — failures in tests added during this milestone
   - `regression_failure: count` — failures in tests that previously passed
     (auto-escalates to NO-GO regardless of other counts)
   - `pass_count`, `skip_count`

4. **Gate rule**:
   - any `regression_failure > 0` → NO-GO (do NOT downgrade to "1 env-blocked")
   - `new_failure > 0` → STAGED (review with the user before declaring GO)
   - all clean → continue to Step 4

#### Fallback path (when dev-loop-skills is missing)

Fall back to raw pytest with a logged warning. Without dev-loop, the
gate cannot mechanically distinguish new vs regression failures —
this is a structural weakness, not a stylistic preference.

1. **Unit/Integration tests**:
   ```bash
   echo "WARN: dev-loop-skills not detected; smoke-test cannot distinguish"
   echo "      new vs regression failures. Install dev-loop-skills for"
   echo "      milestone-grade reporting."
   pytest tests/ -k "{phase_keyword}" --tb=short
   ```

2. **Contract tests** (if applicable):
   ```bash
   pytest tests/contract/ --tb=short
   ```

3. **Type checks** (if configured):
   ```bash
   # Python
   mypy autoservice/ --ignore-missing-imports
   # TypeScript
   npx tsc --noEmit
   ```

4. **Build check**:
   ```bash
   make check  # or equivalent
   ```

Treat any failure as ambiguous in the fallback path. Prompt the user
to triage manually before declaring GO.

### Step 4: Artifact Completeness

Check that all tasks in this phase have the expected artifacts:

```
## Artifact Completeness — M1

| Task | eval-doc | test-plan | test-diff | e2e-report |
|------|----------|-----------|-----------|------------|
| T1A.1 | ✅ eval-003 | ✅ plan-003 | ✅ diff-003 | ✅ e2e-003 |
| T1A.2 | ✅ eval-T1A.2 | ✅ plan-T1A.2 | ⚠️ missing | ⚠️ missing |
| T1B.1 | �� eval-004 | ✅ plan-003 | ✅ diff-003 | ✅ e2e-003 |

Yellow/Red tasks (no dev-loop): Check deliverable files exist
| T1A.4 | N/A | N/A | N/A | ✅ agents/*/soul.md |

Result: 15/17 complete artifacts — WARN (2 missing)
```

### Step 5: Smoke Test Scenarios

Execute or guide E2E scenarios from the kickoff doc:

For each scenario:
```
### Scenario: Customer sends first message

Steps:
1. Start web server: make run-web
2. Open browser to localhost:8000
3. Send a test message in the chat widget
4. Verify: Message appears, AI response within 5s
5. Verify: Conversation ID assigned

Result: [ ] Auto-testable  [x] Manual verification needed
```

Categorize each scenario:
- **Auto-testable**: Run it and report result
- **Manual**: Generate checklist for human verification

#### Step 5.x: Regression list as NO-GO trigger

If Step 3's `e2e-report` listed any `regression_failure` rows, copy
each row into the gate report's `## Blocking failures` section
verbatim. Do NOT downgrade these to "1 env-blocked, structurally
identical to verified counterpart" — that footnote pattern is what
the design spec §1 explicitly forbids. A regression failure in the
e2e-report means a previously-passing test is now red; that is a
NO-GO regardless of how the new tests perform.

### Step 6: Generate Gate Report

```
# Milestone M1 Gate Report — {date}

## Summary
| Check | Result | Details |
|-------|--------|---------|
| Task completion | ✅ PASS | 17/17 tasks completed |
| Plan vs Actual files | ✅ PASS | (0.4.1+) 0 missing_create, 0 declared_not_modified, 1 unexpected_create (WARN) |
| Automated tests | ✅ PASS | 42 tests, 0 failures |
| Contract tests | ✅ PASS | 109 cases, all green |
| Artifact completeness | ⚠️ WARN | 2 artifacts missing (non-critical) |
| Build check | ✅ PASS | make check successful |
| Smoke scenarios | 🔵 PARTIAL | 3/5 auto-verified, 2 need manual |

## Overall: ✅ GO (with 2 manual verifications pending)

## Manual Verification Checklist
- [ ] Scenario 3: Browser chat widget renders correctly
- [ ] Scenario 5: Reconnection after network drop

## Recommended Actions
1. Complete manual verifications
2. If all pass → merge to integration branch
3. Run: /retro M1 for retrospective
4. Proceed to M2: /next-task
```

### Step 7: Gate Decision

Based on the report:

**GO** (all critical checks pass):
- Suggest merge flow (from execution plan)
- Suggest starting next milestone

**NO-GO** (critical failures):
- List blocking failures
- Suggest fix actions
- Do NOT suggest merging

**CONDITIONAL GO** (warnings only):
- List warnings
- Ask user to decide: proceed or fix first?

## Integration with superpowers

Before declaring GO, apply the following additional layers when the respective
skills are available (non-blocking — skip any layer whose skill is unavailable):

1. **Independent review** — invoke `superpowers:requesting-code-review`. This
   dispatches the `code-reviewer` subagent to audit the milestone's merged
   changes against the plan and coding standards. Process its feedback via
   `superpowers:receiving-code-review` (rigorous verification, not blind
   agreement). Rationale: Green-task closures inside `/continue-task` already
   run a per-task review; the milestone-level review catches cross-task
   integration issues that per-task review cannot see.
2. **Verification discipline** — invoke
   `superpowers:verification-before-completion` as a final check before
   declaring GO. It enforces "evidence before assertions" — every ✅ in the
   gate report must be backed by an observed command output.

All three layers are advisory: if none are available, the gate decision falls
back to the automated-test / artifact / scenario checks above. If they flag
**critical** issues, downgrade the gate decision from GO to CONDITIONAL GO
(or NO-GO) regardless of automated-test results.
