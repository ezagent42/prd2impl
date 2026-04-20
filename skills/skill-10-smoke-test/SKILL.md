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

### Step 3: Automated Test Verification

Run available automated checks:

1. **Unit/Integration tests**:
   ```bash
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

### Step 6: Generate Gate Report

```
# Milestone M1 Gate Report — {date}

## Summary
| Check | Result | Details |
|-------|--------|---------|
| Task completion | ✅ PASS | 17/17 tasks completed |
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
