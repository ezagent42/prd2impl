---
name: retro
description: "Milestone retrospective analysis — analyze cycle times, blockers, failure patterns, and generate improvement suggestions. Use when the user says 'retrospective', 'retro for M1', 'what went wrong', or runs /retro."
---

# Skill 11: Retrospective

<SUBAGENT-STOP>
If you were dispatched as a subagent to execute a specific task, skip this skill.
</SUBAGENT-STOP>

Analyze a completed milestone's execution data to identify patterns, bottlenecks, and improvement opportunities.

## Trigger

- User runs `/retro {milestone}` (e.g., `/retro M1`)
- User says "retrospective", "retro for M1", "what went well/wrong"
- After a milestone gate passes

## Input

- **Required**: Milestone ID
- **Data sources**:
  1. `{plans_dir}/tasks.yaml` or `{plans_dir}/task-status.md`
  2. Git log (commit history with timestamps)
  3. `.artifacts/registry.json` (artifact creation times)
  4. `{plans_dir}/*-execution-plan.yaml` (planned timeline)

## Execution Flow

> **Path resolution**: Before constructing any output path, resolve `{plans_dir}` per `lib/plans-dir-resolver.md`. All `docs/plans/` references below (except `docs/plans/project.yaml`, which stays at repo root) are relative to that resolved directory. `.artifacts/` paths are NOT scoped — they remain shared across plans_dir (see design spec §8 Limitation 1).

### Step 1: Gather Data

1. **Task data**: For each task in this milestone's phase, collect:
   - Start time (first `→ in_progress` commit)
   - End time (first `→ completed` commit)
   - Cycle time = end - start
   - Status changes (any blocked/failed transitions)

2. **Git data**:
   ```bash
   git log --oneline --since="{milestone_start}" --until="{milestone_end}" --grep="task:"
   ```

3. **Artifact data**: Creation timestamps from registry.json

### Step 2: Compute Metrics

```yaml
metrics:
  milestone: M1
  planned_duration: "4 hours"
  actual_duration: "5.5 hours"
  slippage: "+37%"
  
  tasks:
    total: 17
    completed_on_time: 14
    completed_late: 2
    blocked_during: 1
    failed_and_redone: 0
    
  cycle_times:
    median: "45 min"
    mean: "52 min"
    p90: "2h 10min"
    fastest: "T1A.7 — 15 min"
    slowest: "T1A.4 — 3h 20min (Yellow, review wait)"
    
  by_type:
    green:
      count: 13
      median_cycle: "35 min"
      total_time: "7h 30min"
    yellow:
      count: 3
      median_cycle: "1h 45min"
      total_time: "5h 15min"
      review_wait_avg: "40 min"
    red:
      count: 1
      median_cycle: "2h"
      decision_wait: "30 min"
      
  blockers:
    count: 1
    total_blocked_time: "45 min"
    reasons:
      - task: T1A.5
        reason: "Waiting for T1A.4 review"
        duration: "45 min"
```

### Step 3: Pattern Analysis

Identify recurring patterns:

**Bottlenecks**:
- Tasks that caused the most downstream waiting
- Review wait times (Yellow tasks)
- Decision wait times (Red tasks)
- External dependency waits

**Velocity trends**:
- Did tasks get faster or slower as the milestone progressed?
- Any correlation between task type and cycle time?
- Cross-line velocity comparison (if multiple lines)

**Quality signals**:
- How many tasks had to be redone?
- How many had test failures?
- How many contracts needed amendment?

### Step 4: Generate Retrospective Report

```markdown
# Retrospective: Milestone M1 — {date}

## Timeline
Planned: Wed 04-15 PM (4 hours)
Actual: Wed 04-15 13:00 - 18:30 (5.5 hours, +37%)

## What Went Well
- All 13 Green tasks completed efficiently (median 35 min)
- No tasks failed and needed redo
- All lines worked in parallel without conflicts
- Contract tests caught 2 issues early

## What Didn't Go Well
- Yellow tasks took 3x longer than Green (review wait bottleneck)
- T1A.4 (soul.md) took 3h 20min — largest single task
- Milestone slipped by 1.5 hours from plan

## Metrics Summary
| Metric | Value |
|--------|-------|
| Tasks completed | 17/17 |
| Median cycle time | 45 min |
| Slowest task | T1A.4 (3h 20min) |
| Blocked time | 45 min total |
| Review wait (avg) | 40 min |

## Root Causes
1. **Yellow review bottleneck**: Reviews took 40 min avg because reviewer
   was busy with own tasks. Consider: dedicated review windows.
2. **T1A.4 scope**: soul.md for 4 roles was too large for one task.
   Should have been split into 4 tasks.

## Improvement Suggestions
1. **Split large Yellow tasks**: Any task >2h should be subdivided
2. **Review windows**: Schedule 15-min review blocks between batches
3. **Parallel reviews**: Both devs review each other's Yellow tasks
   simultaneously instead of sequentially
4. **Red task preemption**: Start Red tasks earlier (this worked well 
   for T3A.4-6, apply same pattern)

## Carry-Forward Items
- [ ] Apply task splitting rule to M2 Yellow tasks
- [ ] Schedule review windows in M2 kickoff
```

### Step 5: Save & Share

1. Write report to `{plans_dir}/retro-{milestone}-{date}.md`
2. Commit: `retro: M1 retrospective`
3. Print summary to terminal
4. Suggest updating execution plan if patterns warrant schedule changes

### Step 6: Framework Learning Loop

> **Why this exists**: M3 retro produced 13 numbered improvement
> recommendations (R1–R13) in
> `docs/plans/m3/prd2impl-retro-notes.md`. Most never propagated into
> prd2impl skill templates. PV2 reproduced nearly identical failure
> modes a sprint later. Step 6 closes the dead-end-report problem by
> turning each suggestion into a concrete skill patch.

#### Inputs

- `improvement_suggestions:` block from Step 4 / Step 5 output
- The current skill files at `skills/*/SKILL.md` in this plugin

#### Procedure

1. **Classify each suggestion by target skill.** Use these heuristics:

   | Suggestion shape | Target skill |
   |---|---|
   | "yellow review missed contract X" | `skill-13-autorun/SKILL.md` yellow checklist |
   | "task generated for tombstoned story" | `skills/using-prd2impl/SKILL.md` tombstone gate |
   | "test passed but missed prod bug" | `references/mock-policy.md` or `skill-3-task-gen/SKILL.md` connector_seam |
   | "dead code shipped per spec" | `skill-13-autorun/SKILL.md` two-stage yellow review |
   | "subagent invented an API method name" | `skill-12-contract-check/SKILL.md` --preflight wiring |
   | "estimate was N× off" | `skill-3-task-gen/SKILL.md` similarity_hint guidance |
   | "operational default differs from code default" | `skill-3-task-gen/SKILL.md` env_var.class declaration rule |

   For suggestions that don't match any heuristic, surface them in a
   `## Unclassified` section of the patch directory's index. These
   need maintainer judgment before they can become skill rules.

2. **For each classified suggestion**, derive:
   - **Baseline scenario** — a runnable description of the failure
     (e.g. "Yellow task whose diff calls `pool.acquire_for_session`
     which does not exist on real `CCPool`; current skill-13 review
     approves it; expected after patch: review fails")
   - **Proposed rule text** — concrete sentence(s) to insert into the
     target SKILL.md
   - **Insertion point** — section heading or line number where the
     rule belongs

3. **Invoke `superpowers:writing-skills`** with the baseline scenario,
   proposed rule, and target file. The writing-skills skill
   pressure-tests the rule against the baseline:
   - Without rule → baseline fails (the bug ships)
   - With rule → baseline passes (the bug is caught)
   - If pressure test fails → revise the rule until it does

4. **Emit one patch per suggestion** under
   `{plans_dir}/framework-patches/{slug}.md` using
   `templates/framework-patch.md` format.

#### Output

`{plans_dir}/framework-patches/` directory containing N patches, each
ready for human review or auto-apply by a maintainer. Auto-apply is
out of scope for 0.4.0 — patches are committed artifacts the
maintainer copies into the prd2impl repo as a separate PR.

#### Graceful degradation

If `superpowers:writing-skills` is not installed, retro emits the
markdown patch without the pressure-test step. The patch file
documents that pressure testing was skipped — maintainer must
manually verify the rule catches the baseline before merging into
the skill.

## Limitations

- Cycle time accuracy depends on consistent commit message formatting (`task: T1A.1 → in_progress/completed`)
- Cannot measure "thinking time" vs "active work time"
- Review wait time is estimated from git timestamps, not exact
- External blocker durations are approximated
