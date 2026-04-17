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
Phase 1: Upstream Analysis (PRD → Tasks)
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
```

## Routing Rules

Match the user's intent to the correct skill:

| User Intent | Skill |
|-------------|-------|
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
| "Set up project from PRD" (full pipeline) | Start with skill-1, then chain |

## Quick Start

For a **new project** starting from a PRD:
```
/prd-analyze docs/prd/my-prd.md    → Structured requirements
/gap-scan                           → What exists vs what's needed
/task-gen                           → Task breakdown with dependencies
/plan-schedule                      → Batches, milestones, timeline
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

## Data Files Convention

This plugin uses **YAML as source of truth** with markdown views:

| File | Purpose | Format |
|------|---------|--------|
| `docs/plans/project.yaml` | Project config (team, milestones) | YAML |
| `docs/plans/prd-structure.yaml` | Structured PRD extraction | YAML |
| `docs/plans/gap-analysis.yaml` | Gap scan results | YAML |
| `docs/plans/tasks.yaml` | Task definitions + dependencies | YAML |
| `docs/plans/execution-plan.yaml` | Batch schedule + timeline | YAML |
| `docs/plans/task-status.md` | Human-readable progress view | Markdown (auto-generated from tasks.yaml) |

If YAML files don't exist yet, skills will fall back to reading existing markdown files (backward compatible with hand-written task-status.md).

## Integration with Other Skills

This plugin integrates with:
- **dev-loop-skills** (skill-5-feature-eval, skill-2-test-plan-generator, etc.) — called during task execution
- **superpowers:brainstorming** — called during PRD analysis and Red/Yellow tasks
- **superpowers:writing-plans** — called during execution plan generation
- **superpowers:dispatching-parallel-agents** — called during batch dispatch
- **superpowers:verification-before-completion** — called during smoke tests
