# prd2impl

PRD-to-Implementation pipeline for Claude Code. A 14-skill plugin that takes you from a Product Requirements Document (or existing hand-written docs) through gap analysis, task generation, execution planning, parallel batch dispatch, full-autopilot execution, and all the way to milestone verification.

> 🇨🇳 **中文用户**: 完整的中文使用手册（含新项目接入 / 多人协同分工 / 典型工作流 / FAQ）见 [docs/guide-zh.md](docs/guide-zh.md)。

## Installation

### Via marketplace (recommended)

```bash
# 1. Add the ezagent42 marketplace (one-time)
/plugin marketplace add ezagent42/ezagent42

# 2. Install prd2impl
/plugin install prd2impl@ezagent42
```

### Via Claude Code settings (manual)

If you've cloned this repo locally, add to your project's `.claude/settings.json`:

```json
{
  "plugins": [
    "/path/to/prd2impl"
  ]
}
```

### Companion plugins

prd2impl delegates testing and methodology to two optional companions (both available on the same marketplace). Install them for the full pipeline; without them, prd2impl degrades gracefully to simpler paths.

```bash
/plugin install dev-loop-skills@ezagent42   # test pipeline (eval / plan / code / run / registry)
/plugin install superpowers                 # brainstorming, TDD, debugging, code review
```

### Verify installation

After installing, the following skills should appear in `/help`:

```
prd2impl:ingest-docs        — Ingest human-authored MDs (Entry B)
prd2impl:prd-analyze       — Structured PRD extraction (Entry A)
prd2impl:gap-scan           — Codebase vs PRD gap analysis
prd2impl:task-gen           — Task generation with dependencies
prd2impl:plan-schedule      — Execution plan & batch scheduling
prd2impl:start-task         — Launch a task into dev-loop
prd2impl:continue-task      — Resume task at next checkpoint
prd2impl:next-task          — Recommend next executable task
prd2impl:batch-dispatch     — Parallel agent dispatch for a batch
prd2impl:task-status        — Progress dashboard
prd2impl:smoke-test         — Milestone gate verification
prd2impl:retro              — Milestone retrospective
prd2impl:contract-check     — Contract drift detection
prd2impl:autorun            — Full-autopilot orchestrator
```

## Quick Start

### Entry A — New project from a PRD document

```
/prd-analyze docs/prd/my-prd.md    # Step 1: Parse PRD → structured YAML
/gap-scan                           # Step 2: Scan code vs requirements
/task-gen                           # Step 3: Generate task breakdown
/plan-schedule                      # Step 4: Create execution plan
```

### Entry B — Project already has hand-written docs

Use this when you already have gap analyses, design specs, or plans in Markdown.
Entry A and Entry B are **mutually exclusive** — pick one per project.

```
/ingest-docs gap.md design-spec.md plan.md
                                    # Step 1: Classify + extract → 3 YAMLs
                                    #   prd-structure.yaml
                                    #   gap-analysis.yaml
                                    #   task-hints.yaml  (preserves file-change granularity)
/task-gen                           # Step 2: Generate tasks (reads task-hints.yaml automatically)
/plan-schedule                      # Step 3: Create execution plan
```

Force a role when auto-detection is uncertain:
```
/ingest-docs a.md b.md --tag spec=a.md --tag gap=b.md
```

Each step has a **human review checkpoint** — the pipeline pauses and waits for your approval before advancing.

### Daily development

```
/next-task                          # What should I work on?
/start-task T1A.1                   # Start a specific task
/continue-task T1A.1                # Resume after review
/task-status                        # Overall progress dashboard
```

### Batch operations

```
/batch-dispatch batch-3             # Launch batch in parallel
/batch-dispatch T1A.3,T1A.6,T1A.7  # Launch specific tasks
```

### Milestone gates

```
/smoke-test M1                      # Verify milestone
/retro M1                           # Retrospective analysis
/contract-check                     # Check interface drift
```

## Pipeline Overview

```
Entry B: Document Ingestion (alternative to Entry A)
┌─────────────────────────────────────────────────────┐
│ /ingest-docs gap.md spec.md plan.md                  │
│ Skill 0 · role-detect → extract → cross-validate     │
│ → prd-structure.yaml + gap-analysis.yaml             │
│ → task-hints.yaml  (new: preserves file granularity) │
└─────────────────────────────────────────────────────┘
       ↓ review (3 checkpoints)              ↘
                                              ↓ (merge at skill-3)
Entry A: Upstream Analysis (PRD → Tasks)      ↓
┌─────────────┐    ┌──────────┐    ┌──────────┐    ┌──────────────┐
│ /prd-analyze │ →  │ /gap-scan │ →  │ /task-gen │ →  │/plan-schedule│
│ Skill 1      │    │ Skill 2   │    │ Skill 3   │    │ Skill 4      │
│ PRD → YAML   │    │ Code scan │    │ Tasks+deps│    │ Batches+time │
└─────────────┘    └──────────┘    └──────────┘    └──────────────┘
       ↓ review         ↓ review        ↓ review        ↓ review

Phase 2: Task Execution
┌─────────────┐    ┌───────────────┐    ┌───────────┐    ┌────────────────┐
│ /start-task  │ →  │ /continue-task │ →  │ /next-task │    │ /batch-dispatch │
│ Skill 5      │    │ Skill 6        │    │ Skill 7    │    │ Skill 8         │
│ Launch task  │    │ Resume dev-loop│    │ Recommend  │    │ Parallel launch │
└─────────────┘    └───────────────┘    └───────────┘    └────────────────┘

Phase 3: Verification & Review
┌──────────────┐    ┌─────────────┐    ┌────────┐    ┌─────────────────┐
│ /task-status  │    │ /smoke-test  │    │ /retro  │    │ /contract-check  │
│ Skill 9       │    │ Skill 10     │    │ Skill 11│    │ Skill 12         │
│ Dashboard     │    │ Gate verify  │    │ Retro   │    │ Drift detection  │
└──────────────┘    └─────────────┘    └────────┘    └─────────────────┘
```

## Data Flow

This plugin uses **YAML as source of truth** with markdown as human-readable views:

```
Entry A (PRD document):
  → prd-structure.yaml     (Skill 1)
  → gap-analysis.yaml      (Skill 2)
  → [no task-hints.yaml]
  → tasks.yaml             (Skill 3)

Entry B (hand-written MDs):
  → prd-structure.yaml     (Skill 0, source_type: "ingested")
  → gap-analysis.yaml      (Skill 0, source_type: "ingested")
  → task-hints.yaml        (Skill 0 — NEW: preserves file_changes + steps + non_goals)
  → tasks.yaml             (Skill 3 — uses task-hints.yaml when present)

Both entries converge at Skill 3:
  → tasks.yaml             (Skill 3, source of truth for all tasks)
  → execution-plan.yaml    (Skill 4)
  → task-status.md         (auto-generated view from tasks.yaml)
  → prompt-templates.md    (auto-generated CC instruction library)
  → collaboration-playbook.md (auto-generated team coordination)
  → batch-*-kickoff.md     (auto-generated per-batch runbooks)
```

## Task Types

| Type | Symbol | Description | Workflow |
|------|--------|-------------|----------|
| Green | `green` | AI can implement independently | Full dev-loop: eval → test-plan → test-code → implement → test-run |
| Yellow | `yellow` | AI drafts, human reviews | Draft → review checklist → approval/rejection |
| Red | `red` | Human-driven decisions | Draft + decision questions → human decides → commit |

## Team Configuration

The plugin supports **any team size** — solo, pair, or squad. Team lines are defined in `project.yaml` during `/plan-schedule`:

- **Solo** (1 line): All tasks assigned to one person, sequential execution
- **Pair** (2 lines): e.g. backend + frontend, parallel execution
- **Squad** (3+ lines): e.g. backend + frontend + infra, max parallelism

The plugin asks for your team structure during setup. No hardcoded assumptions.

## Integration

prd2impl is the **orchestrator layer**. It leans on two companion plugins for
execution-layer capabilities. Both are **optional with graceful degradation**.

### Companion plugins

| Plugin | Owns | Used by prd2impl for | Missing → degrades to |
|--------|------|----------------------|------------------------|
| **dev-loop-skills** | Testing pipeline + `.artifacts/` | eval-doc, test-plan, test-code, test-runner (new-vs-regression reports) | Manual test writing, no regression classification |
| **superpowers** | Method & discipline | Brainstorming, plan writing, TDD rhythm, systematic debugging, independent code review, parallel subagent dispatch, verification-before-completion | Simpler planning; ad-hoc impl/debug; milestone-only review |

### Capability matrix (what prd2impl gains from each)

| Capability | Native | Via superpowers | Via dev-loop |
|------------|--------|-----------------|--------------|
| PRD → tasks → milestones | ✅ | — | — |
| Requirement clarification (brainstorm) | — | ✅ skill-1, skill-5 (Red) | — |
| Plan authoring | partial | ✅ skill-4 | — |
| TDD discipline (rhythm) | — | ✅ skill-5, skill-6 | — |
| Test plan generation | — | — | ✅ skill-6 |
| Test code generation (pytest) | — | — | ✅ skill-6 |
| Test execution + regression detection | — | — | ✅ skill-6 |
| Systematic debugging on test fail | — | ✅ skill-6 | — |
| Independent code review (subagent) | — | ✅ skill-6, skill-10 | — |
| Parallel subagent dispatch | — | ✅ skill-8 | — |
| Evidence-based gate decision | — | ✅ skill-10 | — |
| Artifact registry (`.artifacts/`) | — | — | ✅ cross-cutting |

### Installation recommendation

- **Minimum (PRD + tasks only)**: prd2impl alone
- **Recommended (test-driven delivery)**: prd2impl + dev-loop-skills + superpowers
- **Lite (small team, no formal tests)**: prd2impl + superpowers

### Shared `.artifacts/` layout

When all three plugins are installed, directory ownership:

```
.artifacts/
├── registry.json           # dev-loop writes, prd2impl reads
├── eval-docs/              # dev-loop
├── test-plans/             # dev-loop
├── test-diffs/             # dev-loop
├── e2e-reports/            # dev-loop
├── tasks/                  # prd2impl
├── milestones/             # prd2impl
├── retros/                 # prd2impl
└── contract-checks/        # prd2impl
```

## Backward Compatibility

If your project already has hand-written `task-status.md` or `prompt-templates.md`, the execution skills (5-12) will read those directly. You don't need to run the upstream analysis skills (1-4) to use the execution skills.

## Directory Structure

```
prd2impl/
├── .claude-plugin/
│   ├── plugin.json              # Plugin metadata
│   └── marketplace.json         # Marketplace descriptor
├── package.json                 # NPM metadata
├── skills/
│   ├── using-prd2impl/          # Router skill (entry point)
│   ├── skill-0-ingest/          # Heterogeneous MD ingestion (Entry B)
│   │   ├── SKILL.md             #   4-phase orchestration
│   │   ├── lib/                 #   role-detector, gap/spec/prd-extractor, cross-validator
│   │   ├── schemas/             #   task-hints.schema.yaml + examples
│   │   ├── templates/           #   role-confirmation.md
│   │   └── tests/               #   fixtures + expected outputs
│   ├── skill-1-prd-analyze/     # PRD structured extraction (Entry A)
│   │   ├── SKILL.md
│   │   ├── templates/
│   │   └── references/
│   ├── skill-2-gap-scan/        # Codebase gap analysis
│   ├── skill-3-task-gen/        # Task generation (reads task-hints.yaml when present)
│   │   ├── SKILL.md
│   │   ├── templates/
│   │   └── schemas/
│   ├── skill-4-plan-schedule/   # Execution planning
│   │   └── templates/           # Project, status, playbook templates
│   ├── skill-5-start-task/      # Task launcher
│   ├── skill-6-continue-task/   # Task resumer
│   ├── skill-7-next-task/       # Task recommender
│   ├── skill-8-batch-dispatch/  # Parallel dispatcher
│   ├── skill-9-task-status/     # Progress dashboard
│   ├── skill-10-smoke-test/     # Milestone verification
│   ├── skill-11-retro/          # Retrospective analysis
│   └── skill-12-contract-check/ # Contract drift detection
├── README.md                    # This file
└── .gitignore
```

## License

MIT
