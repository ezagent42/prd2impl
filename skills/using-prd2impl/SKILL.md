---
name: using-prd2impl
description: "PRD-to-Implementation pipeline router. Use when starting a project from a PRD, planning tasks, tracking progress, or executing implementation workflows. Routes to the correct skill based on user intent."
---

# PRD-to-Implementation Pipeline Router

<SUBAGENT-STOP>
If you were dispatched as a subagent to execute a specific task, skip this skill.
</SUBAGENT-STOP>

This plugin provides a complete pipeline from PRD (Product Requirements Document) analysis through task execution, progress tracking, and milestone verification.

## Pipeline Overview

```
Phase 0: Document Ingestion (Entry B — alternative to Entry A)
  skill-0  /ingest-docs     — Ingest human-authored MDs (gaps, specs, plans)
                               produces: prd-structure.yaml + gap-analysis.yaml + task-hints.yaml
                               use instead of /prd-analyze when you already have hand-written docs

Phase 1: Upstream Analysis (PRD → Tasks)  [Entry A — start here if you have a raw PRD]
  skill-1  /prd-analyze     — Structured PRD extraction
  skill-2  /gap-scan        — Codebase vs PRD gap analysis
  skill-3  /task-gen        — Task generation with dependencies
  skill-4  /plan-schedule   — Execution plan & batch scheduling

Phase 2: Task Execution
  skill-5  /start-task      — Launch a task into dev-loop
  skill-6  /continue-task   — Resume task at next checkpoint
  skill-7  /next-task       — Recommend next executable task
  skill-8  /batch-dispatch  — Parallel agent dispatch for a batch

Phase 3: Verification & Review
  skill-9  /task-status     — Progress dashboard with Mermaid charts
  skill-10 /smoke-test      — Milestone gate verification
  skill-11 /retro           — Milestone retrospective analysis
  skill-12 /contract-check  — Contract drift detection

Phase 4: Full Autopilot (optional)
  skill-13 /autorun         — AI picks order, parallelism, and default decisions
```

## Routing Rules

Match the user's intent to the correct skill:

| User Intent | Skill |
|-------------|-------|
| "Ingest my docs", "import gap analysis", "read my markdown files", `/ingest-docs` | skill-0-ingest |
| "Analyze this PRD", "parse requirements", "read the PRD" | skill-1-prd-analyze |
| "What gaps exist", "what's missing", "scan codebase" | skill-2-gap-scan |
| "Generate tasks", "break down into tasks", "create task list" | skill-3-task-gen |
| "Create execution plan", "schedule batches", "plan milestones" | skill-4-plan-schedule |
| "Start task T1A.1", "launch task", "begin working on" | skill-5-start-task |
| "Continue task", "resume", "next step for T1A.1" | skill-6-continue-task |
| "What should I do next", "recommend task", "next task" | skill-7-next-task |
| "Dispatch batch", "launch batch-3", "parallel dispatch" | skill-8-batch-dispatch |
| "Show progress", "task status", "how are we doing" | skill-9-task-status |
| "Run smoke test", "verify milestone", "M1 gate check" | skill-10-smoke-test |
| "Retrospective", "retro for M1", "what went wrong" | skill-11-retro |
| "Check contracts", "contract drift", "schema changed" | skill-12-contract-check |
| "Autorun", "full autopilot", "跑完所有任务", "全托管", "finish everything" | skill-13-autorun |
| "Set up project from PRD" (full pipeline) | Start with skill-1, then chain |

## Quick Start

### Entry A — Starting from a raw PRD document

```
/prd-analyze docs/prd/my-prd.md    → Structured requirements
/gap-scan                           → What exists vs what's needed
/task-gen                           → Task breakdown with dependencies
/plan-schedule                      → Batches, milestones, timeline
```

### Entry B — Starting from existing human-authored Markdown files

Use this when you already have hand-written gap analyses, design specs, or plans.
Entry A and Entry B are **mutually exclusive per project** — run one or the other.

```
/ingest-docs docs/plans/my-gap.md docs/superpowers/specs/my-design.md
                                    → Produces prd-structure.yaml
                                       + gap-analysis.yaml
                                       + task-hints.yaml
/task-gen                           → Task breakdown (uses task-hints.yaml automatically)
/plan-schedule                      → Batches, milestones, timeline
```

Optional `--tag` to force a role when auto-detection is uncertain:
```
/ingest-docs a.md b.md c.md --tag spec=a.md --tag gap=b.md
```

For **daily execution** (after planning is done):
```
/next-task                          → Pick your next task
/start-task T1A.1                   → Enter dev-loop
/continue-task T1A.1                → Resume after review
/task-status                        → Check overall progress
```

For **milestone gates**:
```
/smoke-test M1                      → Verify milestone
/retro M1                           → Retrospective analysis
```

For **full autopilot** (AI drives order, parallelism, and default decisions):
```
/autorun green                      → Auto-run all Green tasks (safe default)
/autorun yellow                     → Green + Yellow (AI self-reviews Yellow via code-reviewer subagent)
/autorun all                        → Green + Yellow + Red (AI picks defaults on design decisions; risky)
/autorun until M1                   → Stop after milestone M1 smoke-test

# Best paired with:
claude --dangerously-skip-permissions    # truly hands-off (no tool prompts)
# OR .claude/settings.json → permissions.defaultMode = "bypassPermissions"
```

## Data Files Convention

This plugin uses **YAML as source of truth** with markdown views. Paths below show the default (`docs/plans/`); if `plans_dir` is configured in `project.yaml` or passed via `--plans-dir`, all these files live under that resolved directory instead (except `project.yaml` itself, which always stays at `docs/plans/`):

| File | Purpose | Format | Source |
|------|---------|--------|--------|
| `docs/plans/project.yaml` | Project config (team, milestones) | YAML | manual |
| `docs/plans/*-prd-structure.yaml` | Structured PRD extraction | YAML | skill-1 or skill-0 |
| `docs/plans/*-gap-analysis.yaml` | Gap scan results | YAML | skill-2 or skill-0 |
| `docs/plans/*-task-hints.yaml` | Human design decisions (file_changes, steps, non_goals) | YAML | skill-0 only |
| `docs/plans/tasks.yaml` | Task definitions + dependencies | YAML | skill-3 |
| `docs/plans/execution-plan.yaml` | Batch schedule + timeline | YAML | skill-4 |
| `docs/plans/task-status.md` | Human-readable progress view | Markdown | auto-generated |

Files from skill-0 carry `source_type: "ingested"` to distinguish them from skill-1/2 outputs.
skill-3 reads `task-hints.yaml` automatically if present; behavior is backward-compatible when absent.

If YAML files don't exist yet, skills will fall back to reading existing markdown files (backward compatible with hand-written task-status.md).

### Design-spec dual output (v0.2.1+)

When `/ingest-docs` processes a file classified as `design-spec` (typical output of
`superpowers:brainstorming`), it now produces **two YAML artifacts** instead of one:

- `{plans_dir}/{date}-task-hints.yaml` — file_changes, implementation_steps, test_strategy (unchanged)
- `{plans_dir}/{date}-prd-structure.yaml` — **partial**: modules (from §Design), nfrs (from §Requirements), constraints (from §Known Limitations)

User stories are intentionally not extracted from design-spec — supply a separate
`user-stories` file if needed. See
`docs/superpowers/specs/2026-04-21-design-spec-ingest-design.md` for full mapping.

## Isolating Multiple Scopes with `plans_dir`

When running multiple milestones/projects in parallel on the same repo
(e.g. finishing M1 while planning M2), set a per-scope `plans_dir` to avoid
artifact collision.

### Quick setup

```yaml
# docs/plans/project.yaml
project:
  # ... other fields ...
  plans_dir: docs/plans/m2   # new scope goes here
```

After this, all prd2impl commands (`/ingest-docs`, `/task-gen`,
`/task-status`, etc.) read/write under `docs/plans/m2/` instead of the root
`docs/plans/` directory.

### Ad-hoc override

Pass `--plans-dir <path>` to any command to override the config for that
invocation:

```bash
/ingest-docs --plans-dir docs/plans/m2 a.md b.md
```

Priority: CLI flag > project.yaml > default (`docs/plans/`).

### Migrating an existing project

```bash
mkdir docs/plans/m1
mv docs/plans/*.yaml docs/plans/*.md docs/plans/m1/
# then in project.yaml:
#   plans_dir: docs/plans/m1
```

### Limitations

- `plans_dir` must be repo-relative; absolute paths and `..` segments rejected
- `.artifacts/` directory is shared across all plans_dir (intentional)
- See `lib/plans-dir-resolver.md` for full spec

## Integration with Other Skills

prd2impl is an **orchestrator** — it owns project-level planning and task
dispatch, and delegates testing/review/debugging nuts-and-bolts to companion
plugins. All integrations are **optional with graceful degradation** — if a
companion skill isn't installed, prd2impl falls back to a simpler path.

### Call matrix

| prd2impl stage | Companion skill invoked | Purpose | Degrades to |
|----------------|-------------------------|---------|-------------|
| skill-1 PRD analysis | `superpowers:brainstorming` | Surface ambiguity before YAML extraction | Direct extraction without interactive clarification |
| skill-4 plan-schedule | `superpowers:writing-plans` | Structured plan authoring | In-skill template-based plan |
| skill-5 start-task (Red) | `superpowers:brainstorming` | Ground design-decision questions in trade-off exploration | Direct question drafting |
| skill-5 start-task (Green/Yellow, impl step) | `superpowers:test-driven-development` | Enforce red/green/refactor rhythm | Ad-hoc implementation ordering |
| skill-5 start-task (Green) | `dev-loop-skills:skill-5-feature-eval` (simulate) | Produce eval-doc | Skill-5 still stops for user review without structured eval |
| skill-6 continue-task (plan→code→run) | `dev-loop-skills:skill-2/3/4` | test-plan → pytest code → regression-aware report | Manual test writing |
| skill-6 continue-task (on test fail) | `superpowers:systematic-debugging` | Hypothesis/evidence-driven diagnosis | Ad-hoc debugging |
| skill-6 continue-task (on close) | `superpowers:requesting-code-review` + `receiving-code-review` | Independent per-task review via code-reviewer subagent | Skip review; rely on milestone-level catch |
| skill-8 batch-dispatch | `superpowers:dispatching-parallel-agents` | Parallel subagent launch with isolation | Sequential launch |
| skill-10 smoke-test | `superpowers:requesting-code-review` + `verification-before-completion` | Independent milestone review + evidence-based GO/NO-GO | Automated-test-only gate |
| skill-13 autorun (yellow/all) | `superpowers:requesting-code-review` | Independent review of Yellow drafts (replaces human STOP) | Yellow tasks fall back to STOP; autorun skips them rather than self-approving |
| skill-13 autorun (yellow, two-stage) | `superpowers:subagent-driven-development` | Two-stage Yellow review pattern (spec-compliance, then code-quality) | Single-stage review (0.3.x) |
| skill-11 retro (Step 6) | `superpowers:writing-skills` | Pressure-test framework patches against baseline failure scenarios | Patches emitted without pressure-test verification — manual confirmation required |
| skill-5/skill-12 preflight | (prd2impl-internal AST) | Resolve every external symbol on real production class before code is written | Skipped with warning; cdcfdb2 bug class can ship |

### Companion plugin summary

- **dev-loop-skills** — owns the **testing pipeline**: eval-doc, test-plan,
  test-code, test-runner (with new-vs-regression classification), and the
  `.artifacts/` registry. Missing → tasks skip automated test pipeline.
- **superpowers** — owns **method and discipline**: brainstorming, plan
  writing, TDD rhythm, systematic debugging, independent code review,
  parallel agent dispatch, verification-before-completion. Missing →
  planning/execution phases are simpler but functional.

### Artifact directory ownership

When both companions are installed, `.artifacts/` subdirectories are split:

| Owner | Subdirectory | Content |
|-------|-------------|---------|
| dev-loop-skills | `test-plans/`, `test-diffs/`, `e2e-reports/`, `eval-docs/` | Per-task testing artifacts |
| prd2impl | `tasks/`, `milestones/`, `retros/`, `contract-checks/` | Project-level artifacts |
| shared | `registry.json` | Cross-skill artifact index (dev-loop writes, prd2impl reads) |
