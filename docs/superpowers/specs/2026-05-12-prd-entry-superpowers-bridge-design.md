# PRD-Entry × Superpowers Bridge — Design Spec

**Status:** Approved (2026-05-12)
**Target version:** prd2impl 0.5.0
**Related:** [`2026-05-12-plan-passthrough.md`](../plans/2026-05-12-plan-passthrough.md) (the 0.4.1 plan that this spec closes the gap for)

## 1. Motivation

Today's prd2impl `using-prd2impl` Call matrix declares two superpowers integrations:

| Stage | Claimed integration | Actual SKILL.md state (0.4.1) |
|---|---|---|
| skill-1 PRD analysis | `superpowers:brainstorming` | 0 references — **not wired** |
| skill-4 plan-schedule | `superpowers:writing-plans` | 0 references — **not wired** |

The matrix is aspirational. Skill-1 directly extracts YAML; skill-4 produces `execution-plan.yaml` + `execution-plan.md` (batches + Mermaid) but **no writing-plans-format per-task plan markdown**.

Consequences:

1. **Entry A has no "design thinking" stage.** PRDs flow straight to YAML with no ambiguity surfacing.
2. **Entry A tasks miss plan-passthrough.** They don't carry `source_plan_path`, so they enter `/start-task` legacy Step 5 (eval-doc → test-plan → test-code → ...). They never reach the 0.4.1 plan-passthrough path that delegates to `superpowers:subagent-driven-development` / `executing-plans`.
3. **Two divergent worlds.** Entry A tasks behave fundamentally differently from Entry B tasks (which DO carry `source_plan_path`).

The 0.4.1 release built the infrastructure (plan-parser, `task_hints.tasks[]`, `source_plan_path`, Step 5'/Step 4a/Step 1.5/Step 2.5). 0.5.0 connects Entry A to that infrastructure.

## 2. Three locked-in design decisions

| Decision | Value | Rationale |
|---|---|---|
| **Granularity** | One writing-plans-format md per prd2impl task (1:1) | Mirrors 0.4.1 Option B inverted: there 1 plan-file → 1 task; here 1 task → 1 plan-file. Identical artifact shape downstream. |
| **Timing** | Eager: `/plan-schedule` synchronously produces all plan-mds + fills `source_plan_path` on every task | Honors the existing `/plan-schedule` contract ("when this returns, planning is done"). `/batch-dispatch` and `/start-task` work immediately. Skill-9 / Skill-10 see complete data. |
| **Scope** | Both skill-1 brainstorming AND skill-4 writing-plans wired in same release | Half-fixing creates a new asymmetry. Single coherent change. |

## 3. Approach selected — B: self-driven with checkpoint batches

Rejected alternatives:
- **A. Pure interactive** — 30 tasks × full-interactive writing-plans = hours of conversation. Unrealistic.
- **C. Spec-stub + lazy flesh-out** — would mean `/plan-schedule` produces thin plan-mds; eager-generation contract is broken.

**B's shape**: skill-1 and skill-4 each gain a `lib/<skill>-runner.md` adapter that wraps the corresponding superpowers skill in "self-driven mode." The superpowers skill self-drives most of its work; pause-points that genuinely need human input are batched into a single user-interaction pass per skill.

## 4. Architecture

```
skill-1-prd-analyze/
  SKILL.md                      ← + Phase 0.5 "Ambiguity Detection"
  lib/
    brainstorm-runner.md        ← NEW. Wraps superpowers:brainstorming.

skill-4-plan-schedule/
  SKILL.md                      ← + Step 4.5 "Per-task plan generation"
  lib/
    plans-runner.md             ← NEW. Wraps superpowers:writing-plans.

using-prd2impl/SKILL.md         ← Call matrix table updated:
                                  the skill-1 and skill-4 rows go from
                                  aspirational to actual.

docs/superpowers/plans/{date}-{task-id}.md   ← NEW per-task artifacts.
```

The two SKILL.md changes are minimal — each adds one phase/step and references the new lib. The lib files carry the actual contract for how superpowers is invoked.

## 5. Data flow

```
PRD md
  ↓ skill-1 /prd-analyze
  ├── Phase 0: parse PRD
  ├── Phase 0.5 (NEW): brainstorm-runner
  │     ├─ Auto-scan PRD for ambiguity signals
  │     ├─ Auto-resolve obvious cases → ambiguity_resolution_log
  │     └─ Batch genuinely ambiguous questions → single user interaction → apply answers
  └── Phase 1-N: extract prd-structure.yaml (with resolution log summary)

gap-analysis.yaml (skill-2, unchanged)
tasks.yaml (skill-3, unchanged — no source_plan_path yet)

  ↓ skill-4 /plan-schedule
  ├── Steps 1-3: batch / milestone / line assignment (UNCHANGED)
  ├── Step 4.5 (NEW): per-task plan generation
  │     for each task in tasks.yaml:
  │       context = {
  │         task: <task entry>,
  │         prd_modules: <relevant prd-structure modules>,
  │         gaps: <related gap-analysis entries>,
  │         conventions: <project.yaml + conventions.md>,
  │       }
  │       result = plans-runner.invoke(context, mode="self-driven")
  │       if result.plan_md AND not result.pause_points:
  │           write docs/superpowers/plans/{date}-{task_id}.md
  │       else:
  │           accumulate result.pause_points
  │
  ├── Step 4.5b: present batched pause_points to user → collect answers
  ├── Step 4.5c: replay plans-runner for tasks that paused, applying user answers
  │              → write remaining plan-mds, update tasks.yaml with source_plan_path
  └── Steps 5-8: execution-plan.yaml + .md + task-status.md + batch-kickoff (UNCHANGED)

POST-CONDITION:
  ✓ tasks.yaml: every task has source_plan_path
  ✓ docs/superpowers/plans/: N plan-mds, all writing-plans-format

  ↓ /start-task / /batch-dispatch (0.4.1 already wired)
  Step 5' detects source_plan_path → delegates to superpowers
```

## 6. Self-driven mode contracts

### 6.1 brainstorm-runner.md contract

**Inputs**: PRD text + extracted draft of prd-structure (modules, user stories, NFRs).

**Behavior**:
- **Goal**: surface ambiguities that affect downstream task generation, not generate new design.
- **Auto-resolve when**:
  - Same noun written multiple ways (PR / pull-request / pull request → canonicalize)
  - Single user story has clear intent + obvious type inferences (e.g., "user enters email" → string field)
  - Convention applies (e.g., RESTful resource naming from project.yaml)
- **Must escalate to user when**:
  - Two user stories make conflicting claims (e.g., US-3 says "single tenant", US-7 says "multi-tenant")
  - An NFR contradicts a functional requirement (e.g., "low latency" + "every action audited synchronously")
  - A module boundary admits 3+ reasonable interpretations
  - A constraint references an external system that isn't in `external_deps`

**Output**:
```yaml
ambiguity_report:
  auto_resolved:
    - signal: "same noun: PR / pull-request"
      action: "canonicalized to 'pull request'"
    - signal: "..."
  user_decisions_pending:
    - id: A1
      ambiguity: "US-3 declares single-tenant; US-7 declares multi-tenant"
      options:
        - {label: "single-tenant", impact: "drop US-7's tenant_id field"}
        - {label: "multi-tenant", impact: "US-3 must add tenant scoping"}
      recommended: "multi-tenant (US-7 is more detailed)"
```

**User-interaction pass**: skill-1 presents `user_decisions_pending` in ONE message (multi-choice per ambiguity, batched). User answers; skill-1 applies; prd-structure.yaml is extracted with resolutions inlined.

**Interactive batch sizing**: If `len(user_decisions_pending) > 8`, split into rounds of ≤8 questions each, in priority order (cross-story conflicts first, NFR contradictions second, module-boundary ambiguities last). Each round is its own user-interaction pass. Rationale: 30-question dumps overwhelm; iterative resolution lets earlier answers narrow later ambiguities.

### 6.2 plans-runner.md contract

**Inputs**: full task-spec context (see Data flow Step 4.5).

**Behavior**:
- **Goal**: produce a writing-plans-format md that mirrors what a human following `superpowers:writing-plans` would write, given the same context. No genuine design discovery — the design has already been done (PRD → tasks).
- **Self-drive** these aspects without pausing:
  - File Structure (from task.deliverables[] + conventions)
  - Phase / sub-task decomposition within the plan (from task description + step granularity guidance)
  - TDD-rhythm step pairs (write failing test → run → verify FAIL → write impl → run → verify PASS → commit)
  - Code-block content for tests/impl (from task.verification + task.deliverables[].path)
  - Commit cadence (per sub-task)
- **Must pause when**:
  - Two genuinely different approaches exist (e.g., "REST vs gRPC" — pick one)
  - A decision is irreversible (DB schema, public API surface)
  - task.deliverables[] contradicts prd-structure modules
  - A constraint applies that the task entry doesn't fully express (e.g., "must keep backwards compat with v1 cookie format" came from a constraint)
- **Do NOT pause when**:
  - Naming style choices (use project conventions)
  - File path placement within an established directory (use conventions)
  - Test framework selection (use project default from project.yaml)
  - Granularity of step decomposition (use writing-plans guidance directly)

**Output**:
```yaml
result:
  task_id: T1A.3
  status: ok | paused
  plan_md_path: docs/superpowers/plans/2026-05-12-T1A.3.md   # when status=ok
  pause_points:                                               # when status=paused
    - decision_label: "REST vs gRPC for the new sync endpoint"
      options:
        - {label: "REST", impact: "..."}
        - {label: "gRPC", impact: "..."}
      recommended: "REST (matches existing /api/* surface)"
      rationale: "..."
```

When `status: ok`: plan-md is written immediately.
When `status: paused`: skill-4 accumulates pause_points; Step 4.5b batches them; Step 4.5c replays plans-runner for that task with the user's answer applied.

**Interactive batch sizing**: same rule as brainstorm-runner — Step 4.5b splits accumulated pause_points into rounds of ≤8 questions, prioritized by irreversibility (DB schema / API surface decisions first, framework choices second, naming/style last).

### 6.3 Why "runner" lib files and not direct invocation?

The lib files exist to **document the contract**. The actual superpowers skills are loaded and invoked by the calling skill. The runner.md acts as a "wrapper spec" — when skill-1 / skill-4 invoke their superpowers counterpart, they pass the prompt/context the runner.md prescribes. This makes the contract grep-able, reviewable, and version-able alongside prd2impl.

## 7. Error handling

| Scenario | Handling |
|---|---|
| brainstorm-runner finds zero ambiguity | Silent pass. prd-structure.yaml gains `ambiguity_resolution: {auto: 0, asked: 0}`. |
| plans-runner fails to converge for task T (e.g., spec too thin) | Generate stub plan-md (well-formed headers, placeholder step content). Mark task with `plan_status: stub` in tasks.yaml. `source_plan_path` is still set (points to the stub file). The stub's first line is `> **[STUB PLAN — DO NOT EXECUTE]** Regenerate via /generate-plan {task_id}`. Skill-5 Step 5' refuses to delegate when this marker is present. End-of-run summary: "N tasks need interactive plan generation: T1, T7, ..." |
| User refuses to answer a batched decision | Apply "most-reversible default" + insert `[NEEDS_REVIEW: <decision_label>]` marker at the top of the affected plan-md. End-of-run summary lists them. |
| `docs/superpowers/plans/{date}-{task-id}.md` already exists | Use skill-0 ingest's diff-summary pattern: `Overwriting {path} ({old_steps} → {new_steps} steps)`. Insert `superseded_by` head note in the old file before overwrite. |
| `superpowers:brainstorming` not installed | Phase 0.5 silently skips. Log warning: `"superpowers:brainstorming not installed; ambiguity detection unavailable; falling back to 0.4.x extract-direct behavior"`. |
| `superpowers:writing-plans` not installed | Step 4.5 silently skips. tasks.yaml has no `source_plan_path` on any task. Log warning: `"superpowers:writing-plans not installed; per-task plan generation unavailable; tasks fall back to dev-loop Step 5 type-specific workflow."` Backward-compatible with 0.4.x. |

## 8. Testing / verification

| Fixture | Assertion |
|---|---|
| Test PRD with 2 conflicting user stories + 1 vague NFR (`tests/fixtures/prd-bridge/conflict-prd.md`) | skill-1 Phase 0.5 emits 2 ambiguities (not 0, not 3). |
| Same PRD → full pipeline through `/plan-schedule` | Every task in `tasks.yaml` has `source_plan_path`. Every plan-md parses with `lib/plan-parser.md` and returns ≥1 task / ≥3 step. |
| `--skip-plan-gen` flag on `/plan-schedule` | tasks.yaml has no `source_plan_path` (forced legacy behavior). |
| superpowers uninstalled | Full chain runs without errors; behaves byte-for-byte like 0.4.x. |
| Existing prd2impl test fixtures | All pass (backward compatibility). |
| End-to-end smoke: PRD → plan-schedule → start-task T1 | Step 5' detects source_plan_path and routes to superpowers (logged). |

## 9. Out of scope (deferred to follow-up)

- skill-2 gap-scan superpowers integration (mechanical scan; no design discussion needed)
- skill-3 task-gen integration (already handles plan-passthrough in 0.4.1 Step 2.5.0; the gap was upstream, not at skill-3)
- LLM-driven plan generation as a separate dependency (the work is invoked via Claude Code's existing skill-invocation mechanism — no new LLM call layer)
- Rewriting execution-plan.yaml / batch-kickoff.md format (kept backward-compatible)
- skill-13 autorun changes (will naturally benefit from per-task source_plan_path; no edits needed)
- skill-1 brainstorm-runner using the Visual Companion (text-only suffices for ambiguity questions)

## 10. Migration & backward compatibility

- Tasks generated by 0.5.0's `/plan-schedule` will have `source_plan_path`. Tasks generated by 0.4.x and earlier won't.
- `/start-task` falls back gracefully (Step 5' if `source_plan_path` exists; legacy Step 5 if not — already true in 0.4.1).
- Users on 0.4.1 who re-run `/plan-schedule` after upgrading to 0.5.0 get plan-mds generated for existing tasks. (Note: existing in-flight tasks may have already-executed steps; the new plan-md may want to mark those `- [x]` retroactively. **Decision: don't auto-tick. The user can ask `/continue-task` to reconcile.**)
- The plan-md filename convention `{date}-{task_id}.md` differs from Entry B's `{date}-<descriptive-slug>.md`. Both are valid writing-plans-format; both parse identically.

## 11. Release shape (preview, not part of this spec)

The implementation will land as one PR + release `0.5.0`. The CHANGELOG entry will document the seven changes (1 spec, 1 each: brainstorm-runner.md, plans-runner.md, skill-1 SKILL.md edit, skill-4 SKILL.md edit, using-prd2impl SKILL.md edit, fixtures + smoke). Marketplace bump 0.4.1 → 0.5.0.

## 12. Decision log (for posterity)

| # | Decision | Selected | Alternatives | Why |
|---|---|---|---|---|
| 1 | Plan-md granularity | per-task | per-batch, per-milestone, hybrid | Mirrors 0.4.1 Option B; identical downstream artifact shape |
| 2 | Generation timing | eager | lazy, separate-command | Preserves `/plan-schedule` "done means done" contract |
| 3 | Scope | skill-1 + skill-4 together | skill-4 only, skill-1 only | Half-fix creates a new asymmetry |
| 4 | Architecture | B self-driven + checkpoint batches | A pure interactive, C stub + lazy | Bounded interactivity; matches how superpowers actually self-drives |
| 5 | Adapter shape | lib/<skill>-runner.md (spec doc) | direct invocation code | Markdown contract is grep-able, version-able, reviewable |
