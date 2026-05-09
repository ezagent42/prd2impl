# Changelog

All notable changes to prd2impl are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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
