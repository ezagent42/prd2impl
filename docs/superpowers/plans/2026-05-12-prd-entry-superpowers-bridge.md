# PRD-Entry × Superpowers Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire `superpowers:brainstorming` into skill-1 PRD analysis (Phase 0.5 ambiguity detection) and `superpowers:writing-plans` into skill-4 plan-schedule (Step 4.5 per-task plan generation), so that Entry A tasks gain `source_plan_path` at planning time and automatically flow through 0.4.1's plan-passthrough infrastructure.

**Architecture:** Add two `lib/<skill>-runner.md` contract documents (one per skill) that prescribe how the corresponding superpowers skill is invoked in "self-driven mode" — with batched user-interaction passes capped at ≤8 questions per round. Patch skill-1 SKILL.md to insert Phase 0.5 between PRD parse and YAML extraction. Patch skill-4 SKILL.md to insert Step 4.5 between batch assignment and execution-plan output. The post-condition of `/plan-schedule` becomes "every task in `tasks.yaml` carries `source_plan_path`, and a matching writing-plans-format md exists at `docs/superpowers/plans/{date}-{task_id}.md`." Step 5' / Step 4a / Step 1.5 / Step 2.5 from 0.4.1 then operate on Entry A tasks identically to Entry B tasks. Backward-compatible: when superpowers is not installed, both new phases silently skip with logged warnings — 0.4.x behavior preserved.

**Tech Stack:**
- Markdown-based skill specs (no compiled code in prd2impl — skills are read by Claude Code)
- YAML schemas (JSON-Schema flavored, existing)
- Test fixtures: input PRD md + expected ambiguity report + expected plan-md sample, manually verified by reading skill behavior
- Reuses 0.4.1 infrastructure: [`skills/skill-0-ingest/lib/plan-parser.md`](../../../skills/skill-0-ingest/lib/plan-parser.md), [`skills/skill-3-task-gen/SKILL.md`](../../../skills/skill-3-task-gen/SKILL.md) Step 2.5.0, [`skills/skill-5-start-task/SKILL.md`](../../../skills/skill-5-start-task/SKILL.md) Step 5'

**File Structure:**

```
# New
skills/skill-1-prd-analyze/lib/
  brainstorm-runner.md                                     ← self-driven mode contract for brainstorming
skills/skill-4-plan-schedule/lib/
  plans-runner.md                                          ← self-driven mode contract for writing-plans
skills/skill-1-prd-analyze/tests/fixtures/prd-bridge/
  conflict-prd.md                                          ← test PRD with 2 conflicts + 1 vague NFR
skills/skill-1-prd-analyze/tests/expected/
  conflict-prd.ambiguity-report.yaml                       ← expected output of brainstorm-runner
skills/skill-4-plan-schedule/tests/expected/
  conflict-prd.sample-plan-md.md                           ← example plan-md from plans-runner

# Modified
skills/skill-1-prd-analyze/SKILL.md                        ← + Phase 0.5
skills/skill-4-plan-schedule/SKILL.md                      ← + Step 4.5
skills/using-prd2impl/SKILL.md                             ← Call matrix becomes truth
CHANGELOG.md                                                ← 0.5.0 entry
package.json                                                ← 0.4.1 → 0.5.0
.claude-plugin/plugin.json                                  ← 0.4.1 → 0.5.0
.claude-plugin/marketplace.json                             ← 0.4.1 → 0.5.0
```

**Discipline:** Because prd2impl skill files are markdown specs (not compiled code), the conventional red-green-refactor TDD rhythm becomes "fixture-first, expected-output-second, contract-third, smoke-fourth, commit-fifth." Every contract change must point at a fixture; every fixture must have an expected-output sibling. Commits are per-task.

---

## Phase A — Foundation fixtures + lib contracts

### Task 1: Test fixture — conflict-prd.md

**Files:**
- Create: `skills/skill-1-prd-analyze/tests/fixtures/prd-bridge/conflict-prd.md`

- [ ] **Step 1: Create the fixture directory and file**

Create `skills/skill-1-prd-analyze/tests/fixtures/prd-bridge/conflict-prd.md` with this content:

````markdown
# Order Sync Service — Product Requirements Document

## 1. Background

A small SaaS that lets merchants sync orders between their store backend and a downstream fulfillment system. Internal tool, not customer-facing.

## 2. Goals

- Reduce sync latency from 15 min (current cron) to under 60s
- Support both single-tenant deployments (own infra) and multi-tenant SaaS

## 3. User stories

### US-1: Single-tenant deployment
As an on-prem merchant, I deploy one instance and it serves only my store.
- No tenant_id field anywhere
- All config in a single env file

### US-2: Multi-tenant SaaS
As the SaaS operator, I run one instance serving multiple merchant stores.
- Every API request carries tenant_id
- Per-tenant config in a database table

### US-3: Sync triggered by order webhook
As a merchant, when my store creates an order, fulfillment is notified within 60s.

### US-4: Manual resync
As an operator, I can trigger a full resync of all unsynced orders for a tenant.
- Endpoint: POST /api/resync
- Returns 202 with a job id

## 4. Non-functional requirements

- **NFR-1**: P95 sync latency under 60 seconds
- **NFR-2**: Every state-changing action must be audited synchronously to an append-only audit log before returning success
- **NFR-3**: Operates on networks with up to 5% packet loss

## 5. Constraints

- Audit log lives in a Postgres table the security team owns; we cannot change its schema.
- The downstream fulfillment system has rate limits we don't fully document.

## 6. Out of scope

- Customer-facing UI
- Order modification (sync only, no edit)
````

This fixture intentionally embeds:
- **Cross-story conflict**: US-1 says "no tenant_id field anywhere" but US-2 says "every API request carries tenant_id." Genuine ambiguity — must surface.
- **NFR vs functional conflict**: NFR-1 demands P95 < 60s; NFR-2 demands synchronous audit before returning. Synchronous audit on every sync = latency budget tension. Real ambiguity.
- **Vague module boundary**: "downstream fulfillment system" appears in US-3 + Constraints but has no module declaration. Vague — must flag.

These three ambiguities are what brainstorm-runner is expected to surface (see Task 2).

- [ ] **Step 2: Verify fixture line count and structure**

Run: `wc -l skills/skill-1-prd-analyze/tests/fixtures/prd-bridge/conflict-prd.md`
Expected: line count ≥ 35 (35-50 typical).

Run: `grep -c "^## \|^### US-\|^- \*\*NFR-" skills/skill-1-prd-analyze/tests/fixtures/prd-bridge/conflict-prd.md`
Expected: count ≥ 10 (sections + user stories + NFR bullets).

- [ ] **Step 3: Commit**

```bash
git add skills/skill-1-prd-analyze/tests/fixtures/prd-bridge/conflict-prd.md
git commit -m "test(skill-1): add conflict-prd fixture (2 conflicts + 1 vague boundary)"
```

---

### Task 2: Expected ambiguity report — conflict-prd.ambiguity-report.yaml

**Files:**
- Create: `skills/skill-1-prd-analyze/tests/expected/conflict-prd.ambiguity-report.yaml`

- [ ] **Step 1: Create the expected-output file**

Create `skills/skill-1-prd-analyze/tests/expected/conflict-prd.ambiguity-report.yaml` with this content:

```yaml
# Expected output of brainstorm-runner applied to
# tests/fixtures/prd-bridge/conflict-prd.md.
#
# Used as the canonical assertion when skill-1 Phase 0.5 runs.
# Three ambiguities expected: 2 conflicts (forced escalation) +
# 1 vague boundary (forced escalation).

ambiguity_report:
  source_files:
    - "tests/fixtures/prd-bridge/conflict-prd.md"

  auto_resolved: []

  user_decisions_pending:
    - id: A1
      category: cross_story_conflict
      ambiguity: |
        US-1 declares single-tenant ('no tenant_id field anywhere').
        US-2 declares multi-tenant ('every API request carries tenant_id').
        These are mutually exclusive at the data-model level.
      options:
        - label: "single-tenant only"
          impact: "Drop US-2; remove tenant_id from API contract; per-tenant config table becomes per-instance env"
        - label: "multi-tenant only"
          impact: "Drop US-1's 'no tenant_id' guarantee; require tenant scoping on every endpoint"
        - label: "both modes, switched by deployment flag"
          impact: "Add SINGLE_TENANT_MODE env; tenant_id required in multi-tenant mode, ignored in single-tenant"
      recommended: "both modes, switched by deployment flag"
      rationale: "US-1 and US-2 are equally detailed; PRD Goals lists both as in-scope. A deployment flag preserves both stories."

    - id: A2
      category: nfr_vs_functional_conflict
      ambiguity: |
        NFR-1 requires P95 sync latency under 60s.
        NFR-2 requires synchronous audit before any state-change response.
        Audit row write + commit on each sync could push latency over 60s under load.
      options:
        - label: "Relax NFR-1 to P95 < 120s when audit required"
          impact: "Latency goal weakened; documentation update only"
        - label: "Make audit asynchronous (post-response queue)"
          impact: "NFR-2 weakened; audit may lag by seconds; ordering not guaranteed"
        - label: "Optimize audit path (separate connection pool, batch commits)"
          impact: "Both NFRs preserved; harder implementation; risk of complexity creep"
      recommended: "Optimize audit path (separate connection pool, batch commits)"
      rationale: "PRD §2 Goals lists latency reduction as the primary value driver, and Constraints prohibit changing the audit table schema (so async with reorder would require a queue we don't own). Optimization keeps both contracts honest."

    - id: A3
      category: module_boundary_undefined
      ambiguity: |
        'Downstream fulfillment system' is referenced in US-3 ('fulfillment is notified within 60s')
        and Constraints ('rate limits we don't fully document') but no module / external_dep declaration exists.
        Cannot determine whether it's an HTTP API, a queue, or a vendor SDK without further input.
      options:
        - label: "HTTP REST API (most common; assume polling on rate limit)"
          impact: "Sync via HTTPS POST; retry loop on 429"
        - label: "Queue (SQS / RabbitMQ / similar)"
          impact: "Publish to queue; fulfillment system consumes; no inline rate limit handling"
        - label: "Vendor SDK (proprietary)"
          impact: "Bind to vendor library; rate limits handled by SDK; lock-in"
      recommended: "HTTP REST API (most common; assume polling on rate limit)"
      rationale: "PRD provides no signal that an MQ or SDK is in play; HTTP is the lowest-assumption fallback. The rate-limit reference (US-3 / Constraints) is consistent with HTTP 429 semantics."

  summary:
    total_signals_scanned: 8     # nominal — depends on the PRD section depth
    auto_resolved_count: 0
    user_pending_count: 3
    batches_required: 1          # 3 ≤ 8 → one round
```

The exact `total_signals_scanned` is implementation-defined (brainstorm-runner may detect 5-12 signals depending on how deeply it scans); the count is informational only. The three `user_decisions_pending` entries are the hard assertions: they must appear with these IDs (A1, A2, A3), these categories, and recommendations that match the rationale text.

- [ ] **Step 2: Validate YAML parses**

Run: `python3 -c "import yaml; d = yaml.safe_load(open('skills/skill-1-prd-analyze/tests/expected/conflict-prd.ambiguity-report.yaml', encoding='utf-8')); print('OK; pending:', len(d['ambiguity_report']['user_decisions_pending']))"`
Expected: `OK; pending: 3`

- [ ] **Step 3: Commit**

```bash
git add skills/skill-1-prd-analyze/tests/expected/conflict-prd.ambiguity-report.yaml
git commit -m "test(skill-1): expected ambiguity report for conflict-prd fixture"
```

---

### Task 3: Create `lib/brainstorm-runner.md`

**Files:**
- Create: `skills/skill-1-prd-analyze/lib/brainstorm-runner.md`

- [ ] **Step 1: Write the contract spec**

Create `skills/skill-1-prd-analyze/lib/brainstorm-runner.md` with this content:

````markdown
# brainstorm-runner — Self-driven invocation contract for superpowers:brainstorming

Used by: `skills/skill-1-prd-analyze/SKILL.md` Phase 0.5 (ambiguity detection).

When skill-1 invokes `superpowers:brainstorming`, it does NOT do so in the skill's default "design a new feature interactively" mode. Instead, it invokes brainstorming in a constrained mode optimized for ambiguity surfacing in an EXISTING PRD. This file specifies that constraint.

## Why a runner contract

`superpowers:brainstorming` is general-purpose. It asks questions to discover what the user wants to build. But in skill-1's context, the user has ALREADY written a PRD — we're not designing, we're surfacing problems in what's already written. Without this contract, brainstorming would ask "what are you trying to build?" and overwhelm the user with discovery questions.

The runner contract gives brainstorming a tighter brief: "find ambiguities, propose resolutions, only escalate the ones the user must decide."

## Inputs

- `prd_text`: The full text of the PRD markdown file(s) skill-1 received.
- `draft_prd_structure`: Skill-1's preliminary extraction (modules, user stories, NFRs, constraints, external_deps). This is what brainstorming will sanity-check against.

## Brainstorming framing prompt

When skill-1 invokes brainstorming, pass this framing (a "system-prompt-like" preamble) to anchor the skill's behavior:

```
You are running in PRD-AMBIGUITY-DETECTION mode for prd2impl skill-1.

Your goal is NOT to design a new feature. The PRD has already been written.
Your goal is to surface ambiguities that, if left unresolved, would cause downstream
task generation (skill-3) to produce wrong or under-specified tasks.

ONLY surface ambiguities that fall into these four categories:

  1. cross_story_conflict — Two or more user stories make incompatible claims
     (e.g., "single-tenant" vs "multi-tenant", "synchronous" vs "eventually consistent").
  2. nfr_vs_functional_conflict — An NFR contradicts a functional requirement
     (e.g., "P95 < 60s" + "every action audited synchronously" + audit-table constraint).
  3. module_boundary_undefined — A noun is referenced in 2+ places but never declared as
     a module / external_dep / data type. Cannot infer its shape without input.
  4. constraint_implicit_external — A constraint references an external system that isn't
     in `external_deps[]`.

DO NOT surface:
  - Stylistic choices (naming, file paths, framework selection)
  - Future-feature questions ("should we also add X?")
  - Implementation-detail questions ("should the cache be in-memory or Redis?")
  - Anything that downstream skills (skill-3 task-gen, skill-4 plan-schedule) can decide on their own

For each ambiguity:
  - Propose 2-3 concrete options
  - State the impact of each option in 1-2 lines
  - Recommend one and give a one-sentence rationale
  - Assign a category from the four listed above

For each obvious resolution (terminology drift, type inference, convention application):
  - Auto-resolve and log to `auto_resolved[]`. Do NOT ask the user about these.

Output schema (YAML):

ambiguity_report:
  source_files: [...]
  auto_resolved:
    - signal: "<what was detected>"
      action: "<what you did>"
  user_decisions_pending:
    - id: A1
      category: cross_story_conflict | nfr_vs_functional_conflict | module_boundary_undefined | constraint_implicit_external
      ambiguity: |
        <2-4 line description of the conflict>
      options:
        - {label: "...", impact: "..."}
      recommended: "<one of the labels>"
      rationale: "<one sentence>"
  summary:
    total_signals_scanned: <int>
    auto_resolved_count: <int>
    user_pending_count: <int>
    batches_required: <int>  # ceil(user_pending_count / 8)
```

## Interactive batch sizing

If `len(user_decisions_pending) > 8`, split into rounds of ≤8, prioritized by:

1. `cross_story_conflict` (highest — these affect data model)
2. `nfr_vs_functional_conflict` (system-level contract)
3. `constraint_implicit_external` (integration boundary)
4. `module_boundary_undefined` (lowest — usually has obvious defaults)

Each round is its own user-interaction pass. Apply round-1 answers before computing round-2 (later rounds may collapse if earlier answers resolve cascading ambiguities).

## Acceptance criteria

The contract holds when, applied to a PRD known to contain N ambiguities:
- `len(user_decisions_pending) == N` (no false positives, no false negatives)
- Each entry's `category` is one of the four allowed values
- Each entry's `options` has 2-3 entries
- Each entry's `recommended` is one of its own `options[*].label`
- `summary.batches_required == ceil(N / 8)`

## Verification fixture

Apply this contract to `tests/fixtures/prd-bridge/conflict-prd.md`. The expected output is `tests/expected/conflict-prd.ambiguity-report.yaml`. The output must match it on:
- The 3 `user_decisions_pending` IDs (A1, A2, A3)
- Each one's `category`
- Each one's `recommended` matches one of its own options
- `summary.user_pending_count == 3`
- `summary.batches_required == 1`

`total_signals_scanned` and `auto_resolved_count` may vary by implementation — they're informational, not asserted.

## What happens after

`brainstorm-runner` does NOT apply resolutions itself. It returns the report to skill-1's Phase 0.5, which:
1. Presents `user_decisions_pending` to the user (in rounds if needed)
2. Collects answers
3. Applies them by amending the draft `prd_structure` (e.g., dropping conflicting fields, adding `external_deps[]` entries, narrowing constraints)
4. Inlines a summary in the final `prd-structure.yaml` under `extraction.ambiguity_resolution`

## Graceful degradation

If `superpowers:brainstorming` is not installed:
- Skill-1 Phase 0.5 logs: `"brainstorming unavailable — ambiguity detection skipped; PRD extracted as-written"`
- `prd-structure.yaml.extraction.ambiguity_resolution` is set to `{auto: 0, asked: 0, skipped_reason: "brainstorming-not-installed"}`
- skill-1 proceeds to Phase 1 immediately

This preserves 0.4.x behavior when superpowers is missing.
````

- [ ] **Step 2: Verify the file is well-formed**

Run: `wc -l skills/skill-1-prd-analyze/lib/brainstorm-runner.md`
Expected: line count ≥ 100.

Run: `grep -c "^## " skills/skill-1-prd-analyze/lib/brainstorm-runner.md`
Expected: ≥ 7 (sections: Why a runner contract, Inputs, Brainstorming framing prompt, Interactive batch sizing, Acceptance criteria, Verification fixture, What happens after, Graceful degradation).

- [ ] **Step 3: Commit**

```bash
git add skills/skill-1-prd-analyze/lib/brainstorm-runner.md
git commit -m "feat(skill-1): brainstorm-runner.md — self-driven invocation contract"
```

---

### Task 4: Create `lib/plans-runner.md`

**Files:**
- Create: `skills/skill-4-plan-schedule/lib/plans-runner.md`

- [ ] **Step 1: Create the lib directory if it doesn't exist**

Run: `mkdir -p skills/skill-4-plan-schedule/lib`

- [ ] **Step 2: Write the contract spec**

Create `skills/skill-4-plan-schedule/lib/plans-runner.md` with this content:

````markdown
# plans-runner — Self-driven invocation contract for superpowers:writing-plans

Used by: `skills/skill-4-plan-schedule/SKILL.md` Step 4.5 (per-task plan generation).

When skill-4 invokes `superpowers:writing-plans` for each task in `tasks.yaml`, it does NOT do so in the skill's default "design a multi-step task from scratch" mode. The design has already been done by the upstream chain (skill-1 → skill-3). Skill-4's job here is to crystallize each task's existing spec into a writing-plans-format md without re-asking design questions that have already been settled.

## Why a runner contract

`superpowers:writing-plans` is designed to assume a developer with full context will follow its output. When invoked freshly per-task by skill-4, it lacks that context. Without this contract, it would ask "what are you building?" for every task — 30 tasks × discovery = unusable.

The runner contract gives writing-plans a complete spec package PER task, defines exactly which questions still warrant user input, and bounds interactivity.

## Inputs

For each task being planned, skill-4 assembles a spec package:

```yaml
spec_package:
  task:
    id: T1A.3
    name: "EventBus subscriber registration"
    type: green
    phase: P1
    module: "engine"
    deliverables:
      - {path: "autoservice/engine/eventbus.py", change_type: create}
      - {path: "tests/engine/test_eventbus.py", change_type: create}
    verification:
      - "subscribers can register; messages route to all subscribers; unregister works"
    story_refs: [US-3]
    depends_on: [T1A.2]
  prd_modules:
    # The full module entries from prd-structure.yaml that this task touches
    - id: MOD-engine
      description: "..."
  gap_refs:
    # The gap-analysis entries this task addresses
    - id: GAP-007
      severity: P0
      description: "..."
  conventions:
    # From project.yaml + conventions.md
    test_framework: pytest
    naming_id: "secrets.token_urlsafe(36)"
    timestamps: "datetime.utcnow().isoformat()"
  ambiguity_resolutions:
    # From skill-1 Phase 0.5; only the resolutions that affect THIS task
    - "Multi-tenant mode is enabled via SINGLE_TENANT_MODE=0 env (A1 decision)"
```

## Writing-plans framing prompt

When skill-4 invokes writing-plans, pass this framing as preamble:

```
You are running in PER-TASK-PLAN-GENERATION mode for prd2impl skill-4.

Your goal is to produce one writing-plans-format markdown plan for the task in
the spec_package below. The design has ALREADY been done by upstream skills
(skill-1 PRD analysis, skill-2 gap-scan, skill-3 task-gen). Do NOT re-ask design
questions that the spec already answers.

You MUST self-drive these aspects without pausing:

  - File Structure section (from task.deliverables + conventions)
  - Phase / sub-task decomposition WITHIN this plan (split task into 3-8
    plan-tasks by natural boundaries: setup, core, integration, tests, docs)
  - TDD-rhythm step pairs (failing test → run → verify FAIL → impl → run → verify
    PASS → commit) — use writing-plans' standard 5-step rhythm
  - Code-block content for tests and impl (derive from task.verification +
    task.deliverables[].path)
  - Commit cadence (one commit per plan-task, at the close)

You MUST PAUSE and surface a pause_point when:

  - 2+ genuinely different approaches exist and the spec doesn't pick one
    (e.g., "REST vs gRPC", "Postgres vs SQLite")
  - A decision is irreversible (DB schema shape, public API contract,
    serialization format on the wire)
  - task.deliverables[] contradicts a prd_modules constraint
  - A constraint applies that the task entry doesn't fully express, and
    applying it changes the plan shape

You MUST NOT pause for:

  - Naming style choices — defer to conventions.naming_id, conventions.timestamps,
    or the file/directory style already present in the codebase.
  - File path placement within an established directory — use conventions.
  - Test framework selection — use conventions.test_framework.
  - Granularity of step decomposition — use writing-plans' own guidance.
  - Whether to add error handling — only add what's tested; don't speculate.

When you self-drive a plan to completion:

  Output schema:
    result:
      task_id: <task.id>
      status: ok
      plan_md_path: "docs/superpowers/plans/{date}-{task_id}.md"
      plan_md_content: |
        <full writing-plans-format markdown — the file's contents>
      pause_points: []

When you must pause:

  Output schema:
    result:
      task_id: <task.id>
      status: paused
      plan_md_path: null
      plan_md_content: null
      pause_points:
        - decision_label: "<short label, e.g., 'sync transport: REST vs gRPC'>"
          options:
            - {label: "...", impact: "..."}
          recommended: "<one of the labels>"
          rationale: "<one sentence>"
          reversibility: low | medium | high
```

## Interactive batch sizing

Skill-4 accumulates `pause_points` across all tasks before invoking the user. If `total_pause_points > 8`, split into rounds of ≤8, prioritized by `reversibility: low` first (irreversible decisions need careful review), then `medium`, then `high`.

Each round is its own user-interaction pass. After the user answers a round, skill-4 replays `plans-runner.invoke()` for each affected task with the answer applied to its `spec_package.ambiguity_resolutions` — the second call should return `status: ok`.

## Acceptance criteria

The contract holds when, applied to a `spec_package` of typical complexity:
- `status: ok` produces a plan_md that parses cleanly via `skill-0-ingest/lib/plan-parser.md` (returns `error: null`, `tasks` non-empty, `steps` per task non-empty).
- The plan_md's H1 ends with "Implementation Plan" (so role-detector Signal 0 recognizes it as plan-passthrough).
- The plan_md's File Structure section enumerates exactly the deliverables from `spec_package.task.deliverables[]` (no extras, no omissions).
- Each plan-task within the plan_md has 4-8 steps.
- The plan_md's first step is "Write the failing test" or similar TDD-first action.

`status: paused` is acceptable only when the spec_package genuinely fails the "must NOT pause for" list.

## Verification fixture

For task `T-CONFLICT.1` derived from the conflict-prd fixture (Task 1), the expected plan_md is at `tests/expected/conflict-prd.sample-plan-md.md`. The sample shows the canonical shape: H1, agentic-workers blockquote, File Structure, Phase A, Task 1 with 4-6 steps, Task 2 with 4-6 steps.

## What happens after

`plans-runner` returns `result` to skill-4 Step 4.5. Skill-4:
1. If `status: ok`: writes `plan_md_content` to `plan_md_path`; updates the task entry in `tasks.yaml` with `source_plan_path: <plan_md_path>` and `plan_status: ok`.
2. If `status: paused`: stores pause_points in an in-memory queue; does NOT yet write a plan_md for this task.
3. After all tasks are processed: if any tasks paused, run Step 4.5b (batched user-interaction) → Step 4.5c (replay paused tasks with answers).
4. End of Step 4.5: `tasks.yaml` is updated; all plan_mds are on disk.

## Graceful degradation

If `superpowers:writing-plans` is not installed:
- Skill-4 Step 4.5 logs: `"writing-plans unavailable — per-task plan generation skipped; tasks will use legacy Step 5 type-specific workflow"`
- No `source_plan_path` is set on any task
- Skill-4 continues to Step 5 (execution-plan.yaml output) — backward-compatible with 0.4.x
- End-of-run banner: `"Phase A/B/C completed; 0 tasks have source_plan_path (superpowers:writing-plans missing). Install it and re-run /plan-schedule to enable plan-passthrough."`

## Stub fallback (per spec § 7)

If `plans-runner.invoke()` returns an error or fails to produce a parseable plan_md for a task (e.g., spec_package is too thin), skill-4 generates a stub plan_md:

```markdown
# {task.name} Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

> **[STUB PLAN — DO NOT EXECUTE]** This plan was auto-generated as a placeholder because the task spec was insufficient for plans-runner to produce a full plan. Regenerate via `/generate-plan {task_id}` after enriching the task entry in tasks.yaml.

**Goal:** {task.verification[0]}

---

## Phase A — placeholder

### Task 1: {task.name}

**Files:**
{for each deliverable: "- {Create|Modify}: `{path}`"}

- [ ] **Step 1: TODO — fill in steps via /generate-plan**
```

The stub IS written to disk and `source_plan_path` IS set, but `plan_status: stub` is set in tasks.yaml. Skill-5 Step 5' refuses to delegate when it reads the `[STUB PLAN — DO NOT EXECUTE]` marker.
````

- [ ] **Step 3: Verify the file is well-formed**

Run: `wc -l skills/skill-4-plan-schedule/lib/plans-runner.md`
Expected: line count ≥ 120.

Run: `grep -c "^## " skills/skill-4-plan-schedule/lib/plans-runner.md`
Expected: ≥ 8.

- [ ] **Step 4: Commit**

```bash
git add skills/skill-4-plan-schedule/lib/plans-runner.md
git commit -m "feat(skill-4): plans-runner.md — self-driven invocation contract"
```

---

### Task 5: Expected sample plan-md — conflict-prd.sample-plan-md.md

**Files:**
- Create: `skills/skill-4-plan-schedule/tests/expected/conflict-prd.sample-plan-md.md`

- [ ] **Step 1: Create the expected sample**

Create `skills/skill-4-plan-schedule/tests/expected/conflict-prd.sample-plan-md.md` with this content:

````markdown
# Order Sync Service — T-CONFLICT.1: order webhook receiver Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the HTTP endpoint that receives order-created webhooks from the merchant's store and queues a sync job for the downstream fulfillment system, honoring the multi-tenant deployment mode resolved during PRD ambiguity detection.

**Architecture:** A FastAPI route at `POST /api/webhook/order_created` validates the webhook signature, extracts `tenant_id` (when `SINGLE_TENANT_MODE=0`) or uses the singleton-tenant config (when `SINGLE_TENANT_MODE=1`), persists a sync_job row, and returns 202 with the job id. The actual sync to the fulfillment HTTP API is owned by T-CONFLICT.2 (downstream sync worker).

**Tech Stack:**
- Python 3.13+
- FastAPI + pydantic
- Postgres via SQLAlchemy 2.x (existing in repo)
- pytest + pytest-asyncio + httpx (for FastAPI TestClient)

**File Structure:**

```
# New
ordersvc/webhook/order_created.py
tests/webhook/test_order_created.py

# Modified
ordersvc/api_routes.py    ← mount the new route
```

---

## Phase A — Endpoint + handler

### Task 1: Failing webhook receiver test

**Files:**
- Create: `tests/webhook/test_order_created.py`
- Modify: `ordersvc/api_routes.py:1-30` (router init only)

- [ ] **Step 1: Write the failing test**

```python
# tests/webhook/test_order_created.py
from fastapi.testclient import TestClient
from ordersvc.api_routes import app

client = TestClient(app)


def test_order_created_webhook_returns_202_with_job_id():
    payload = {"order_id": "ord_123", "tenant_id": "tnt_a", "items": []}
    headers = {"X-Webhook-Signature": "valid-sig-for-test"}
    r = client.post("/api/webhook/order_created", json=payload, headers=headers)
    assert r.status_code == 202
    body = r.json()
    assert "job_id" in body
    assert body["job_id"].startswith("job_")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/webhook/test_order_created.py::test_order_created_webhook_returns_202_with_job_id -v`
Expected: FAIL with `404 Not Found` (route doesn't exist yet).

- [ ] **Step 3: Write the route handler**

```python
# ordersvc/webhook/order_created.py
import secrets
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

router = APIRouter()


class OrderCreatedPayload(BaseModel):
    order_id: str
    tenant_id: str
    items: list


@router.post("/api/webhook/order_created", status_code=202)
async def order_created(payload: OrderCreatedPayload, x_webhook_signature: str = Header(None)):
    if not x_webhook_signature:
        raise HTTPException(status_code=401, detail="missing signature")
    job_id = "job_" + secrets.token_urlsafe(16)
    # TODO Task 2: persist sync_job row with tenant scoping
    return {"job_id": job_id}
```

And wire it into the existing app:

```python
# ordersvc/api_routes.py (modified head)
from fastapi import FastAPI
from ordersvc.webhook.order_created import router as order_created_router

app = FastAPI()
app.include_router(order_created_router)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/webhook/test_order_created.py::test_order_created_webhook_returns_202_with_job_id -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/webhook/test_order_created.py ordersvc/webhook/order_created.py ordersvc/api_routes.py
git commit -m "feat(webhook): order_created receiver returns 202 with job_id"
```

---

### Task 2: Persist sync_job row with tenant scoping

(Plan continues for the second plan-task; structure mirrors Task 1.)

````

This sample is illustrative — it shows the canonical SHAPE that plans-runner is expected to produce. It is NOT a verbatim assertion (the actual generated plan may differ in code variable names, comment style, etc.). It's used in Task 9's smoke as a reference for "does the output look about right?"

- [ ] **Step 2: Verify it parses as writing-plans format**

Run: `grep -c "^### Task \|^- \[ \] \*\*Step " skills/skill-4-plan-schedule/tests/expected/conflict-prd.sample-plan-md.md`
Expected: ≥ 6 (at least 1 task heading + 5 step bullets).

Run: `grep -c "Implementation Plan\|REQUIRED SUB-SKILL" skills/skill-4-plan-schedule/tests/expected/conflict-prd.sample-plan-md.md`
Expected: ≥ 2 (H1 + agentic-workers blockquote).

- [ ] **Step 3: Commit**

```bash
git add skills/skill-4-plan-schedule/tests/expected/conflict-prd.sample-plan-md.md
git commit -m "test(skill-4): expected sample plan-md from plans-runner"
```

---

## Phase B — Skill-1 wiring

### Task 6: Update `skill-1-prd-analyze/SKILL.md` with Phase 0.5

**Files:**
- Modify: `skills/skill-1-prd-analyze/SKILL.md`

- [ ] **Step 1: Read the current SKILL.md structure**

Run: `grep -n "^## \|^### " skills/skill-1-prd-analyze/SKILL.md | head -20`

Identify where Phase 0 ends and Phase 1 begins. Phase 0.5 goes between them.

- [ ] **Step 2: Locate the section header transition for Phase 1**

Use Grep to find the line: `^## Phase 1` or `^### Phase 1` or `^## Step 1` (whichever the file uses for its first extraction step). Note the exact heading text.

- [ ] **Step 3: Insert Phase 0.5 ambiguity detection**

Use Edit to insert immediately BEFORE the Phase 1 heading found in Step 2. Insert this content:

````markdown
## Phase 0.5 — Ambiguity Detection (0.5.0+)

**Triggers when**: `superpowers:brainstorming` is installed AND the input PRD is non-empty.

**Read**: `lib/brainstorm-runner.md` — follow it exactly for this phase.

Steps:

1. Parse the PRD into a draft `prd_structure` dict (modules, user stories, NFRs, constraints, external_deps) using the same regex/scan heuristics as Phase 1 — this is a preliminary pass; the real extraction happens in Phase 1 after Phase 0.5 resolutions are applied.

2. Invoke `superpowers:brainstorming` with the framing prompt from `lib/brainstorm-runner.md`. Pass the PRD text and the draft prd_structure as inputs.

3. Brainstorming returns an `ambiguity_report` (schema in brainstorm-runner.md). Capture:
   - `auto_resolved[]` — log to a `ambiguity_resolution_log.md` for posterity; no user interaction needed
   - `user_decisions_pending[]` — surface to the user

4. **[HUMAN REVIEW CHECKPOINT 0.5]** — if `user_decisions_pending` is non-empty:

   Present in batches of ≤8 per round (priority order: cross_story_conflict → nfr_vs_functional_conflict → constraint_implicit_external → module_boundary_undefined).

   Each question is multi-choice with the brainstorm-runner-provided options.

5. Apply the user's resolutions:
   - For cross_story_conflict: amend `draft_prd_structure.user_stories` per the chosen option (drop fields, add tenant scoping, etc.)
   - For nfr_vs_functional_conflict: amend `draft_prd_structure.nfrs` and/or insert a new `constraints[]` entry capturing the chosen trade-off
   - For module_boundary_undefined: add a stub `modules[]` entry with the chosen interpretation
   - For constraint_implicit_external: add the system to `external_deps[]`

6. Write a summary into the (final) prd_structure:

   ```yaml
   extraction:
     ambiguity_resolution:
       auto: <auto_resolved_count>
       asked: <user_pending_count>
       rounds: <batches_required>
       resolutions:
         - id: A1
           chosen: "<label>"
         # ...
   ```

7. Proceed to Phase 1 with the amended `draft_prd_structure` as the starting point.

**Graceful degradation**: if `superpowers:brainstorming` is not installed, skip this phase entirely. Log a warning at startup: `"superpowers:brainstorming not installed; PRD ambiguity detection unavailable; extracting as-written"`. Phase 1 proceeds with the unamended PRD.

**Verification**: applying this phase to `tests/fixtures/prd-bridge/conflict-prd.md` must produce an `ambiguity_report` matching `tests/expected/conflict-prd.ambiguity-report.yaml` on the 3 user-pending entries (IDs A1, A2, A3).

````

- [ ] **Step 4: Update the Component library / lib table at the bottom of SKILL.md (if present)**

Search for a "Component library" or "lib reference" table at the bottom of SKILL.md. If present, add this row:

```markdown
| 0.5 | `lib/brainstorm-runner.md` (used when superpowers:brainstorming is installed) |
```

If no such table exists, skip this step.

- [ ] **Step 5: Verify the insertion**

Run: `grep -c "Phase 0.5\|brainstorm-runner.md" skills/skill-1-prd-analyze/SKILL.md`
Expected: ≥ 3.

- [ ] **Step 6: Commit**

```bash
git add skills/skill-1-prd-analyze/SKILL.md
git commit -m "feat(skill-1): Phase 0.5 ambiguity detection via brainstorm-runner"
```

---

## Phase C — Skill-4 wiring

### Task 7: Update `skill-4-plan-schedule/SKILL.md` with Step 4.5

**Files:**
- Modify: `skills/skill-4-plan-schedule/SKILL.md`

- [ ] **Step 1: Locate Step 5 in the current SKILL.md**

Run: `grep -n "^### Step 5" skills/skill-4-plan-schedule/SKILL.md`

Identify the line number. Step 4.5 goes immediately before Step 5.

- [ ] **Step 2: Insert Step 4.5 per-task plan generation**

Use Edit to insert immediately BEFORE the `### Step 5` heading found in Step 1. Insert this content:

````markdown
### Step 4.5 — Per-Task Plan Generation (0.5.0+)

**Triggers when**: `superpowers:writing-plans` is installed AND `tasks.yaml` has at least one task.

**Read**: `lib/plans-runner.md` — follow it exactly for this step.

Steps:

#### Step 4.5a — Generate plans (self-drive pass)

```
paused_tasks = []
for task in tasks.yaml.tasks:
    spec_package = assemble_spec_package(
        task=task,
        prd_modules=prd_structure.modules filtered by task.module,
        gap_refs=gap_analysis.gaps filtered by task.story_refs,
        conventions=project.yaml + conventions.md (if exists),
        ambiguity_resolutions=prd_structure.extraction.ambiguity_resolution.resolutions
                              filtered to those affecting task.module / task.story_refs,
    )
    result = plans_runner.invoke(spec_package)
    if result.status == "ok":
        write result.plan_md_content to result.plan_md_path
        update task entry in tasks.yaml: source_plan_path = result.plan_md_path, plan_status = "ok"
    elif result.status == "paused":
        paused_tasks.append((task.id, result.pause_points))
    else:
        # error / spec too thin
        write stub plan-md per plans-runner.md § Stub fallback
        update task entry: source_plan_path = stub_path, plan_status = "stub"
```

#### Step 4.5b — Batched user interaction (only if any tasks paused)

Surface accumulated `pause_points` in batches of ≤8, prioritized by `reversibility: low` (most irreversible first).

```
all_pauses = flatten([(tid, pp) for tid, pps in paused_tasks for pp in pps])
sort by pp.reversibility (low < medium < high)
for batch in chunks(all_pauses, size=8):
    present batch to user as multi-choice questions
    collect user's choices
    apply choices to relevant task spec_packages
```

After each batch, replay `plans_runner.invoke()` for affected tasks; expect `status: ok` second time around. If a task still pauses after answer applied, surface as an error: `"task {tid} cannot be planned even after pause-point resolution; manual intervention required"`.

**When user refuses to answer a question (clicks "Skip" or equivalent)**: apply the most-reversible default option (the one with `reversibility: high`; tie-break by the `recommended` label). Replay plans-runner with that default. After replay, the generated plan_md must include a `[NEEDS_REVIEW: <decision_label>]` marker at the top of the affected plan-task body. Set the task's `plan_status: needs_review` in tasks.yaml.

#### Step 4.5c — Final state

Post-conditions of Step 4.5:
- Every task in `tasks.yaml` has `source_plan_path` set (either to a real plan_md or to a stub).
- Every plan_md is on disk at `docs/superpowers/plans/{date}-{task_id}.md`.
- `tasks.yaml` carries `plan_status: ok | stub | needs_review` per task.
- A `Step 4.5 — Plan Generation Summary` block is appended to the eventual `execution-plan.md` (Step 6):

  ```
  ## Plan Generation Summary (Step 4.5)

  - {N_ok} tasks: full plans generated
  - {N_stub} tasks: stub plans (need /generate-plan rerun): T1A.5, T2B.3
  - {N_review} tasks: full plans with [NEEDS_REVIEW] markers: T3B.1
  - Total user-interaction rounds: {R}
  - Total pause_points resolved: {P}
  ```

**Graceful degradation**: if `superpowers:writing-plans` is not installed, skip this step entirely. Log a warning: `"superpowers:writing-plans not installed; per-task plan generation unavailable. Tasks fall back to legacy Step 5 type-specific workflow."` Step 5 proceeds with `tasks.yaml` as-is — no `source_plan_path` on any task.

**Verification**: applying Step 4.5 to a tasks.yaml derived from `tests/fixtures/prd-bridge/conflict-prd.md` must:
- Produce at least one plan_md whose shape matches `tests/expected/conflict-prd.sample-plan-md.md` (H1 with "Implementation Plan", REQUIRED SUB-SKILL blockquote, ### Task N: headings, - [ ] **Step N:** bullets).
- Update tasks.yaml so every task has `source_plan_path`.
- Produce a Plan Generation Summary block in execution-plan.md.

````

- [ ] **Step 3: Update Step 5 to mention the new prerequisite**

Find the existing `### Step 5` heading. Add this note immediately under it (before the existing content):

```markdown
> **Step 4.5 may have run before this** (when `superpowers:writing-plans` is installed). If so, every task in `tasks.yaml` already has `source_plan_path` set. Step 5 below produces execution-plan.yaml + execution-plan.md as usual, and the resulting tasks flow through plan-passthrough at /start-task time (skill-5 Step 5').
```

- [ ] **Step 4: Update the Component library / lib table at the bottom of SKILL.md (if present)**

Search for a "Component library" or "lib reference" table at the bottom of SKILL.md. If present, add this row:

```markdown
| 4.5 | `lib/plans-runner.md` (used when superpowers:writing-plans is installed) |
```

If no such table exists, skip this step.

- [ ] **Step 5: Verify the insertion**

Run: `grep -c "Step 4.5\|plans-runner.md" skills/skill-4-plan-schedule/SKILL.md`
Expected: ≥ 4.

- [ ] **Step 6: Commit**

```bash
git add skills/skill-4-plan-schedule/SKILL.md
git commit -m "feat(skill-4): Step 4.5 per-task plan generation via plans-runner"
```

---

## Phase D — Router truth update

### Task 8: Update `using-prd2impl/SKILL.md` Call matrix

**Files:**
- Modify: `skills/using-prd2impl/SKILL.md`

- [ ] **Step 1: Locate the Call matrix table**

Run: `grep -n "Call matrix\|skill-1 PRD analysis\|skill-4 plan-schedule" skills/using-prd2impl/SKILL.md`

Identify the exact rows for skill-1 PRD analysis and skill-4 plan-schedule.

- [ ] **Step 2: Update the skill-1 PRD analysis row**

Find the row that currently reads:

```markdown
| skill-1 PRD analysis | `superpowers:brainstorming` | Surface ambiguity before YAML extraction | Direct extraction without interactive clarification |
```

Use Edit to replace with:

```markdown
| skill-1 PRD analysis (Phase 0.5, 0.5.0+) | `superpowers:brainstorming` via `lib/brainstorm-runner.md` | Surface ambiguity before YAML extraction; batched ≤8/round | Direct extraction without interactive clarification |
```

- [ ] **Step 3: Update the skill-4 plan-schedule row**

Find the row that currently reads:

```markdown
| skill-4 plan-schedule | `superpowers:writing-plans` | Structured plan authoring | In-skill template-based plan |
```

Use Edit to replace with:

```markdown
| skill-4 plan-schedule (Step 4.5, 0.5.0+) | `superpowers:writing-plans` via `lib/plans-runner.md` | Per-task plan generation; output is writing-plans-format md per task with `source_plan_path` recorded back to tasks.yaml | In-skill no-plan-md generation (0.4.x); tasks fall back to legacy Step 5 |
```

- [ ] **Step 4: Verify the updates**

Run: `grep -c "Phase 0.5\|Step 4.5\|brainstorm-runner\|plans-runner" skills/using-prd2impl/SKILL.md`
Expected: ≥ 4.

- [ ] **Step 5: Commit**

```bash
git add skills/using-prd2impl/SKILL.md
git commit -m "docs(using-prd2impl): Call matrix becomes truth for skill-1/skill-4 (0.5.0)"
```

---

## Phase E — Release + smoke

### Task 9: CHANGELOG entry + version bumps

**Files:**
- Modify: `CHANGELOG.md`
- Modify: `package.json`
- Modify: `.claude-plugin/plugin.json`
- Modify: `.claude-plugin/marketplace.json`

- [ ] **Step 1: Bump package.json**

Use Edit. Find:
```
  "version": "0.4.1",
```
Replace with:
```
  "version": "0.5.0",
```

- [ ] **Step 2: Bump plugin.json**

Use Edit on `.claude-plugin/plugin.json`. Find:
```
  "version": "0.4.1",
```
Replace with:
```
  "version": "0.5.0",
```

- [ ] **Step 3: Bump marketplace.json + refresh prd2impl description**

Use Edit on `.claude-plugin/marketplace.json`. Find the prd2impl entry. Update:
- `"version": "0.4.1"` → `"version": "0.5.0"`
- Description: prepend or replace the v0.4.1 sentence with: `"v0.5.0: PRD-entry × superpowers bridge — skill-1 Phase 0.5 ambiguity detection via superpowers:brainstorming; skill-4 Step 4.5 per-task plan generation via superpowers:writing-plans, every task gains source_plan_path → Entry A tasks auto-flow through plan-passthrough."`

- [ ] **Step 4: Add CHANGELOG entry**

Open `CHANGELOG.md`. Locate the top (above `## 0.4.1 — 2026-05-12`). Insert this new section:

```markdown
## 0.5.0 — 2026-05-12

PRD-entry × superpowers bridge. Wires `superpowers:brainstorming` into skill-1 PRD analysis (Phase 0.5) and `superpowers:writing-plans` into skill-4 plan-schedule (Step 4.5). After this release, Entry A tasks (PRD-driven) gain `source_plan_path` at planning time and automatically flow through 0.4.1 plan-passthrough.

Spec: [`docs/superpowers/specs/2026-05-12-prd-entry-superpowers-bridge-design.md`](docs/superpowers/specs/2026-05-12-prd-entry-superpowers-bridge-design.md)
Plan: [`docs/superpowers/plans/2026-05-12-prd-entry-superpowers-bridge.md`](docs/superpowers/plans/2026-05-12-prd-entry-superpowers-bridge.md)

### Added

- **skill-1 Phase 0.5** — ambiguity detection via `superpowers:brainstorming`. Surfaces cross-story conflicts, NFR-vs-functional contradictions, undefined module boundaries, and implicit external dependencies. Auto-resolves obvious cases; batches genuine ambiguities into rounds of ≤8 questions for user resolution.
- **skill-1 `lib/brainstorm-runner.md`** — self-driven invocation contract for brainstorming. Defines the framing prompt, the four ambiguity categories, batch sizing, and acceptance criteria.
- **skill-4 Step 4.5** — per-task plan generation via `superpowers:writing-plans`. For each task in `tasks.yaml`, assembles a spec package (task + relevant prd modules + gap refs + conventions + ambiguity resolutions) and self-drives a writing-plans-format md. Pause-points across all tasks are batched into rounds of ≤8 for user resolution.
- **skill-4 `lib/plans-runner.md`** — self-driven invocation contract for writing-plans. Defines what's self-driven (file structure, TDD rhythm, code blocks) vs what must pause (irreversible decisions, contradictions, multi-approach choices).
- **Post-condition contract upgrade**: after `/plan-schedule` returns, every task in `tasks.yaml` has `source_plan_path` set. Entry A tasks now auto-flow through 0.4.1 plan-passthrough (Step 5' delegation, Step 4a subagent prompts, Step 1.5 progress, Step 2.5 plan-vs-actual smoke).
- **Router truth update**: `using-prd2impl` Call matrix's skill-1 and skill-4 rows now describe actual wiring (via the runner libs), not aspirations.

### Added — Tests / fixtures

- `skills/skill-1-prd-analyze/tests/fixtures/prd-bridge/conflict-prd.md` — test PRD with 2 conflicts + 1 vague module boundary.
- `skills/skill-1-prd-analyze/tests/expected/conflict-prd.ambiguity-report.yaml` — expected brainstorm-runner output (3 user_decisions_pending).
- `skills/skill-4-plan-schedule/tests/expected/conflict-prd.sample-plan-md.md` — illustrative sample of plans-runner output.

### Backward compatibility

All changes are graceful. When `superpowers:brainstorming` is not installed, Phase 0.5 is silently skipped. When `superpowers:writing-plans` is not installed, Step 4.5 is silently skipped; tasks fall back to legacy Step 5 type-specific workflow (0.4.x behavior preserved byte-for-byte). Existing `/plan-schedule` outputs (execution-plan.yaml, .md, task-status.md, batch-kickoff.md) remain unchanged in shape.

### Out of scope (deferred)

- skill-2 gap-scan superpowers integration (mechanical scan; no design discussion needed)
- skill-3 task-gen integration (already handles plan-passthrough in 0.4.1 Step 2.5.0)
- LLM-driven plan generation as a separate dependency layer
- Rewriting `execution-plan.yaml` / `batch-kickoff.md` formats
- skill-13 autorun changes (naturally benefits from per-task source_plan_path)
```

- [ ] **Step 5: Verify all four files**

Run:
```bash
grep -c '"version": "0.5.0"' package.json .claude-plugin/plugin.json .claude-plugin/marketplace.json
grep -c "## 0.5.0" CHANGELOG.md
```

Expected: three `1`s for the version files, `1` for CHANGELOG.

- [ ] **Step 6: Commit**

```bash
git add CHANGELOG.md package.json .claude-plugin/plugin.json .claude-plugin/marketplace.json
git commit -m "chore(release): 0.5.0 — PRD-entry × superpowers bridge + marketplace sync"
```

---

### Task 10: End-to-end smoke notes

**Files:**
- Create: `docs/superpowers/plans/2026-05-12-prd-entry-superpowers-bridge-smoke-notes.md`

- [ ] **Step 1: Mechanical re-verification**

Run:
```bash
# Fixtures parse
python3 -c "import yaml; d = yaml.safe_load(open('skills/skill-1-prd-analyze/tests/expected/conflict-prd.ambiguity-report.yaml', encoding='utf-8')); print('OK; pending:', len(d['ambiguity_report']['user_decisions_pending']))"

# Sample plan-md is plan-passthrough recognizable
grep -c "REQUIRED SUB-SKILL: Use superpowers:" skills/skill-4-plan-schedule/tests/expected/conflict-prd.sample-plan-md.md
grep -c "^### Task \|^- \[ \] \*\*Step " skills/skill-4-plan-schedule/tests/expected/conflict-prd.sample-plan-md.md

# Both runner libs are in place
test -f skills/skill-1-prd-analyze/lib/brainstorm-runner.md && echo "brainstorm-runner OK"
test -f skills/skill-4-plan-schedule/lib/plans-runner.md && echo "plans-runner OK"

# SKILL.md edits landed
grep -c "Phase 0.5\|brainstorm-runner" skills/skill-1-prd-analyze/SKILL.md
grep -c "Step 4.5\|plans-runner" skills/skill-4-plan-schedule/SKILL.md
grep -c "Phase 0.5\|Step 4.5\|brainstorm-runner\|plans-runner" skills/using-prd2impl/SKILL.md

# Version bumps consistent
grep '"version"' package.json .claude-plugin/plugin.json .claude-plugin/marketplace.json | grep -c '0.5.0'
```

Expected outputs:
- ambiguity_report yaml: `OK; pending: 3`
- sample plan-md REQUIRED SUB-SKILL count: 1
- sample plan-md headings/steps: ≥ 6
- both runner libs exist
- skill-1 grep ≥ 3; skill-4 grep ≥ 4; using-prd2impl grep ≥ 4
- version bumps: 3

- [ ] **Step 2: Cross-reference audit**

Run:
```bash
# skill-1 references brainstorm-runner
grep "brainstorm-runner" skills/skill-1-prd-analyze/SKILL.md

# brainstorm-runner references its fixture
grep "conflict-prd" skills/skill-1-prd-analyze/lib/brainstorm-runner.md

# skill-4 references plans-runner
grep "plans-runner" skills/skill-4-plan-schedule/SKILL.md

# plans-runner references its sample
grep "conflict-prd" skills/skill-4-plan-schedule/lib/plans-runner.md

# Backward-compat warning strings exist (so the engineer can grep them in logs)
grep "superpowers:brainstorming not installed" skills/skill-1-prd-analyze/lib/brainstorm-runner.md
grep "superpowers:writing-plans not installed" skills/skill-4-plan-schedule/lib/plans-runner.md
```

All commands must return ≥ 1 match. Any zero-match indicates a missing cross-reference — fix before commit.

- [ ] **Step 3: Write smoke notes**

Create `docs/superpowers/plans/2026-05-12-prd-entry-superpowers-bridge-smoke-notes.md` with this content:

```markdown
# PRD-Entry × Superpowers Bridge 0.5.0 — Smoke Notes

Generated 2026-05-12 as Task 10 of the bridge implementation plan.

## Mechanical verifications

- ambiguity_report.yaml parses; 3 user_decisions_pending — A1, A2, A3 — present
- sample plan-md has REQUIRED SUB-SKILL header (plan-passthrough recognizable)
- both runner libs (brainstorm-runner.md, plans-runner.md) exist on disk
- skill-1 SKILL.md references Phase 0.5 + brainstorm-runner
- skill-4 SKILL.md references Step 4.5 + plans-runner
- using-prd2impl Call matrix references both
- package.json + plugin.json + marketplace.json all at 0.5.0
- CHANGELOG entry under 0.5.0 — 2026-05-12 documents 7 changes

## Cross-reference audit

All eight grep checks in the plan's Task 10 Step 2 return ≥ 1 match. The contract files reference their fixtures; the SKILL.md files reference their runners; the backward-compat warning strings exist where the engineer would search for them.

## What is NOT runtime-verified

Same caveat as 0.4.1: the actual `/prd-analyze` and `/plan-schedule` invocations on the conflict-prd fixture require a Claude Code session with both superpowers and prd2impl installed at 0.5.0. Until that session runs (the next dogfooding cycle on a real PRD), the runtime correctness is provisional.

What CAN be promised based on the mechanical work above:
- The contract specs (brainstorm-runner.md, plans-runner.md) are internally consistent and reference their fixtures correctly.
- The SKILL.md edits are syntactically clean and reference the runner libs.
- The post-condition contract upgrade (every task gets `source_plan_path`) is correctly described and integrates with 0.4.1's plan-passthrough (Step 5' detection check is unchanged; new flow just populates the field upstream).

## Suggested dogfooding cycle

1. Merge feat/skill-1-4-superpowers-bridge → main; tag v0.5.0; refresh local plugin cache.
2. On AutoService dev-a or similar PRD-bearing project: run `/prd-analyze <prd.md>` and confirm Phase 0.5 fires.
3. Verify the user receives a batched ambiguity prompt (≤ 8 questions per round).
4. After Phase 1-N completes, run `/gap-scan` and `/task-gen` as normal.
5. Run `/plan-schedule` — confirm Step 4.5 fires; observe per-task plan-md generation; resolve any batched pause-points.
6. Verify tasks.yaml: every task should now have `source_plan_path` populated.
7. Run `/start-task T1A.1` (or any first task) — confirm Step 5' detects source_plan_path and delegates to subagent-driven-development.

A negative test: temporarily uninstall superpowers; rerun `/prd-analyze` + `/plan-schedule`. Confirm both skip with logged warnings; no task gets source_plan_path; `/start-task` falls back to legacy Step 5.
```

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/plans/2026-05-12-prd-entry-superpowers-bridge-smoke-notes.md
git commit -m "docs: smoke notes for 0.5.0 PRD-entry × superpowers bridge"
```

---

## Acceptance criteria for this whole plan

- [ ] All 10 tasks above have their checkboxes ticked.
- [ ] `git log --oneline 0.4.1..HEAD` shows ~11 commits (1 spec + 10 implementation tasks), all under conventional-commit prefixes.
- [ ] `lib/brainstorm-runner.md` defines: 4 ambiguity categories, framing prompt, batch sizing, acceptance criteria, verification fixture pointer, graceful degradation.
- [ ] `lib/plans-runner.md` defines: spec_package shape, framing prompt, self-drive vs pause rules, output schema (ok / paused), batch sizing, acceptance criteria, verification fixture pointer, graceful degradation, stub fallback.
- [ ] `skill-1-prd-analyze/SKILL.md` contains Phase 0.5 with steps 1-7 plus graceful degradation.
- [ ] `skill-4-plan-schedule/SKILL.md` contains Step 4.5 (4.5a self-drive, 4.5b batched interaction, 4.5c final state) plus graceful degradation.
- [ ] `using-prd2impl/SKILL.md` Call matrix's skill-1 and skill-4 rows reference the runner libs and explicitly tag (0.5.0+).
- [ ] CHANGELOG entry under `## 0.5.0 — 2026-05-12` documents 7+ changes.
- [ ] Version files all at 0.5.0.
- [ ] Smoke notes file landed at `docs/superpowers/plans/2026-05-12-prd-entry-superpowers-bridge-smoke-notes.md`.

## Out of scope (for this plan; tracked separately)

- Real runtime dogfooding on a non-trivial PRD (next milestone).
- LLM-side improvements to brainstorming (e.g., better ambiguity-signal heuristics) — this plan ships the CONTRACT; LLM quality improves via superpowers releases.
- skill-2 / skill-3 integration with superpowers (out of scope per spec § 9).
