# prd2impl

PRD-to-Implementation pipeline for Claude Code. A 12-skill plugin that takes you from a Product Requirements Document through gap analysis, task generation, execution planning, and all the way to milestone verification.

## Installation

### Via Claude Code settings

Add to your project's `.claude/settings.json`:

```json
{
  "plugins": [
    "/path/to/prd2impl"
  ]
}
```

Or if published to a marketplace:

```json
{
  "enabledPlugins": {
    "prd2impl@your-marketplace": true
  }
}
```

### Verify installation

After installing, the following skills should appear in `/help`:

```
prd2impl:prd-analyze       — Structured PRD extraction
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
```

## Quick Start

### New project from PRD

```
/prd-analyze docs/prd/my-prd.md    # Step 1: Parse PRD → structured YAML
/gap-scan                           # Step 2: Scan code vs requirements
/task-gen                           # Step 3: Generate task breakdown
/plan-schedule                      # Step 4: Create execution plan
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
Phase 1: Upstream Analysis (PRD → Tasks)
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
PRD document
  → prd-structure.yaml     (Skill 1)
  → gap-analysis.yaml      (Skill 2)
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

Works best with these companion plugins:

- **dev-loop-skills** — Provides eval-doc, test-plan, test-code, test-runner pipeline
- **superpowers** — Provides brainstorming, writing-plans, parallel dispatch, verification

Both are optional. Without dev-loop-skills, tasks skip the automated test pipeline. Without superpowers, the planning phase is simpler but still functional.

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
│   ├── skill-1-prd-analyze/     # PRD structured extraction
│   │   ├── SKILL.md
│   │   ├── templates/
│   │   └── references/
│   ├── skill-2-gap-scan/        # Codebase gap analysis
│   ├── skill-3-task-gen/        # Task generation
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
