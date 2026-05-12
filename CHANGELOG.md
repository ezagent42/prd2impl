# Changelog

All notable changes to prd2impl are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## 0.4.1 — 2026-05-12

Plan-passthrough (Option B coarse-grained) × Plan-grounded smoke-test.
Makes writing-plans-format markdown plans first-class prd2impl input,
without YAML round-trip information loss. The 8 admin-v2 plans at
`AutoService/docs/superpowers/plans/2026-05-11-admin-v2-*.md` (and any
other writing-plans-format md) can now be ingested → task-genned → started
→ smoke-tested end-to-end. Execution delegates to
`superpowers:subagent-driven-development` / `executing-plans`, which
consume the plan natively — prd2impl does NOT re-encode plan steps.

Plan: [`docs/superpowers/plans/2026-05-12-plan-passthrough.md`](docs/superpowers/plans/2026-05-12-plan-passthrough.md)

### Granularity choice — Option B (coarse-grained)

This release implements **1 prd2impl task = 1 plan file**. A finer-grained
mapping (1 plan-task = 1 prd2impl task, with plan-slicing at execution
time) was considered and deferred — `superpowers:executing-plans` v5.1.0
takes no CLI args, so slicing would require either a plan-slicer (write
a temp md) or an upstream PR. Revisit if intra-plan parallel dispatch
becomes a real need.

### Added

- **skill-0 role-detector**: Signal 0 — writing-plans header override
  (`REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development` or
  `... executing-plans` in first 30 lines → role=plan, confidence=100,
  short-circuits the 4-signal heuristic).
- **skill-0 lib/plan-parser.md** (new): shared library that extracts
  `{Task N → Files{Create,Modify,Test,Delete} → Steps[]}` hierarchy from
  writing-plans-format markdown. Six parsing rules cover discovery,
  body boundaries, Files block, Steps, idempotence, refusal on malformed
  input. Used by skill-0, skill-8, skill-9, skill-10.
- **skill-0 spec-extractor.md**: Phase 0 (new) delegates writing-plans
  md to plan-parser; legacy file_changes/steps extraction skipped on
  this path. Legacy plans without the writing-plans header still flow
  through Steps 1-7 unchanged.
- **schema task-hints.yaml**: gains a `tasks[]` property carrying
  per-plan-task hierarchy (`task_index`, `name`, `source_plan_path`,
  `source_plan_anchor`, `files`, `steps`). Optional — absent for
  design-spec / prd / gap / user-stories roles.
- **schema task-hints.example.yaml**: refreshed with `tasks[]` example
  derived from admin-v2 p1.
- **skill-3 task-gen Step 2.5.0** (new): plan-passthrough plan-file
  mapping. When `task_hints.tasks[]` is present, emits ONE prd2impl
  task per unique `source_plan_path`, aggregating
  `files{create,modify,test}` across all plan-tasks in the file.
  Task ID follows the plan-letter pattern (T1, T4A, T6B, ...).
  Legacy Behaviors 1/2/3 still run for ingest without `tasks[]`.
- **skill-5 start-task Step 5'** (new): plan-passthrough execution.
  Detects `source_plan_path` on the task and delegates the WHOLE plan
  to `superpowers:subagent-driven-development` (preferred) or
  `superpowers:executing-plans` (fallback). No CLI flags, no slicing.
  Forwards `--autopilot={level}` to the delegated skill.
- **skill-8 batch-dispatch Step 4a** (new): plan-passthrough prompt
  block REPLACES the legacy Type-Specific Workflow lines when the
  dispatched task has `source_plan_path`. The subagent invokes
  `superpowers:subagent-driven-development` on the source plan inside
  its worktree; prd2impl does NOT inline verbatim plan steps into the
  prompt (the writing-plans format is purpose-built for the superpowers
  skills to consume directly — re-encoding would duplicate the contract).
  Pre-flight: plan-parser sanity-checks the plan before dispatch.
- **skill-9 task-status Step 1.5** (new): per-plan step progress.
  Reads `source_plan_path` and counts `- [ ]`/`- [x]` across the whole
  plan file to derive `step_progress = {checked}/{total}` and
  `plan_task_progress = {done}/{total}`. Surfaced in the Active Tasks
  table's Duration column.
- **skill-10 smoke-test Step 2.5** (new): plan-vs-actual file structure
  check. For any milestone with plan-passthrough tasks, cross-checks
  per-plan-task `files{create,modify}` (from task-hints.yaml) against
  `git diff` vs base branch. `missing_create` and
  `declared_modify_not_modified` contribute NO-GO; `unexpected_create`
  and `unexpected_modify` contribute CONDITIONAL GO. Report breaks down
  per plan-task (`T1 / plan-task-1`, `T1 / plan-task-2`, …) for
  granularity.

### Added — Tests / fixtures

- `skills/skill-0-ingest/tests/fixtures/plan-passthrough/admin-v2-p1-cr-data-layer.md` —
  canonical 14-task / 90-step writing-plans-format fixture (copy of the
  AutoService admin-v2 p1 plan).
- `skills/skill-0-ingest/tests/expected/admin-v2-p1.task-hints.yaml` —
  expected plan-parser output (14 tasks, 90 steps, 25 create + 14
  modify file declarations).
- `skills/skill-0-ingest/tests/fixtures/plan-passthrough/_gen_expected.py` —
  one-shot generator that embeds the parsing rules in Python and
  produces the expected fixture. Regen via
  `python3 skills/skill-0-ingest/tests/fixtures/plan-passthrough/_gen_expected.py`.

### Designed for

The 8 admin-v2 plans at `AutoService/docs/superpowers/plans/2026-05-11-admin-v2-*.md`
become 8 prd2impl tasks (T1, T2, T3, T4A, T4B, T5, T6A, T6B). Run
`/ingest-docs <plans>` → `/task-gen` → `/start-task T1` (or
`/batch-dispatch T1,T2,...`) → `/smoke-test` end-to-end without
information loss between stages.

### Backward compatibility

All changes are additive. Tasks without `source_plan_path` behave
byte-for-byte identical to 0.4.0. Plans that don't use the writing-plans
header are still parsed by the legacy step-extraction flow.

### Out of scope (deferred follow-ups)

- Option A (fine-grained 1 plan-task → 1 prd2impl task) — would require
  a plan-slicer at start-task time or an upstream PR to
  `superpowers:executing-plans` adding a `--task-anchor` arg. Schema and
  parser already carry the per-plan-task hierarchy needed.
- `/next-task` parallel-sibling suggester (improvement #4 from the
  evaluation that produced this plan).
- skill-12 `/contract-check` cross-plan symbol graph (improvement #6).

## 0.4.0 — 2026-05-09

Skill-chain wiring + framework-learning loop. Connects prd2impl's
declared `superpowers` and `dev-loop-skills` capabilities to actual
invocation paths. Closes architectural voids identified in the
AutoService PV2 milestone audit (May 2026).

Design: [`docs/superpowers/specs/2026-05-09-skill-chain-wiring-design.md`](docs/superpowers/specs/2026-05-09-skill-chain-wiring-design.md)
Plan: [`docs/superpowers/plans/2026-05-09-skill-chain-wiring.md`](docs/superpowers/plans/2026-05-09-skill-chain-wiring.md)

### Added

- **skill-12** AST-based contract snapshot + `signature_drift` detection block (replaces 0.3.x diff-text parser)
- **skill-12** `/contract-check --preflight {task_id}` subcommand (the cdcfdb2 prevention path)
- **skill-12** `references/ast-walk-template.md` — reusable contract-test generator
- **skill-5** Step 4.5 Yellow / `must_call_unchanged` preflight gate
- **skill-11** Step 6 framework-learning loop via `superpowers:writing-skills`
- **skill-11** `templates/framework-patch.md` — patch format spec
- **skill-3** schema fields: `must_call_unchanged`, `env_var.{name,class,code_default,ops_default,kill_switch_semantics}`, `reload_kind`, `auto_promoted`, `tombstone`
- **skill-3** auto color-promotion: Green → Yellow when affects auth / permission / contract / seam, or `must_call_unchanged` non-empty, or `connector_seam: true`, or `env_var.class: A`
- **skill-13** two-stage Yellow review (Stage A spec-compliance, Stage B code-quality) per `superpowers:subagent-driven-development`
- **skill-2** Step 3.5 house-conventions extraction → `{plans_dir}/conventions.md`
- **skill-3** Step 2.6 reads `conventions.md` and inlines into each task's `context_block`
- **using-prd2impl** tombstone gate (refuses dispatch of `tombstone: true` / `status: DEFERRED_*` / `# TOMBSTONE:` tasks)
- **skill-7-next-task** explicit tombstone filter
- **`references/mock-policy.md`** at plugin root — explicit mock policy with contract-test pattern, consumed by skill-3/5/6/8
- **skill-10** Step 0 Layer-3 drift gate via `dev-loop:skill-0-project-builder`

### Changed

- **skill-10** Step 3 routes through `dev-loop:skill-4-test-runner` (raw `pytest` retained as fallback). Regression failures auto-trigger NO-GO; ends the "env-blocked, structurally identical" footnote pattern.
- **skill-9 / skill-11 / skill-12** read artifacts via `dev-loop:skill-6-artifact-registry` (direct file read retained as fallback). Enables "tasks shipped without executed test-plan" coverage-gap signal in retro reports.
- **using-prd2impl** call matrix updated with three new rows (`subagent-driven-development` two-stage yellow review, `writing-skills` retro callback, AST preflight).

### Backward compatibility

All changes are additive. `tasks.yaml` schema additions are optional
fields — existing tasks continue to validate without modification.
When companion plugins are absent:

- `dev-loop-skills` missing → smoke-test falls back to raw `pytest`;
  artifact reads fall back to direct file; drift gate skips with warning.
- `superpowers` missing → Yellow tasks fall back to single-stage review
  or human STOP (matches 0.3.x); retro emits patches without pressure-test.

In short: 0.4.0 with neither companion installed behaves identically
to 0.3.1, with logged warnings noting which capabilities are degraded.

## 0.3.1 — 2026-04-22

M3 retro improvements (PR #5):

- skill-13 parallel-line detection at autorun preflight (L-B)
- skill-3 pipeline-integration-test rule for connector seams (R15)
- skill-5 force contract re-read for Yellow / security tasks (R11)

## 0.3.0 — 2026-04-22

design-spec bridge phase 2 + B2 task-gen degradation.

## 0.2.x and earlier

See git log.
