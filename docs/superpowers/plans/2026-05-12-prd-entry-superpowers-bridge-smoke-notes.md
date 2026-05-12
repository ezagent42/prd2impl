# PRD-Entry × Superpowers Bridge 0.5.0 — Smoke Notes

Generated 2026-05-12 as Task 10 of the bridge implementation plan.

## Mechanical verifications

All passed in commit-time review:

- ambiguity_report.yaml parses; 3 user_decisions_pending — A1, A2, A3 — present
- sample plan-md has REQUIRED SUB-SKILL header (plan-passthrough recognizable); count: 1
- sample plan-md headings/steps count: 7 (≥ 6 threshold met)
- both runner libs (brainstorm-runner.md, plans-runner.md) exist on disk
- skill-1 SKILL.md grep for "Phase 0.5|brainstorm-runner": 9 matches
- skill-4 SKILL.md grep for "Step 4.5|plans-runner": 13 matches
- using-prd2impl SKILL.md grep for "Phase 0.5|Step 4.5|brainstorm-runner|plans-runner": 2 matches
- package.json + plugin.json + marketplace.json all at 0.5.0
- CHANGELOG entry under 0.5.0 — 2026-05-12 documents 7 changes (Added block)

## Cross-reference audit

All eight grep checks in the plan's Task 10 Step 2 return ≥ 1 match. The contract files reference their fixtures; the SKILL.md files reference their runners; the canonical warning strings live in the runner libs (SKILL.md defers to them via "Log the warning prescribed in `lib/<runner>.md §Graceful degradation`").

Specific matches confirmed:
- `skill-1/SKILL.md` references `brainstorm-runner` — matched (multiple lines: read, invoke, graceful degradation)
- `brainstorm-runner.md` references `conflict-prd` fixture — matched (acceptance-criteria block)
- `skill-4/SKILL.md` references `plans-runner` — matched (multiple lines: read, stub fallback, skip handling)
- `plans-runner.md` references `conflict-prd` fixture — matched (example task + expected sample path)
- `brainstorm-runner.md` contains `"brainstorming unavailable"` warning string — matched
- `plans-runner.md` contains `writing-plans` reference — matched (title line + graceful degradation)

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
