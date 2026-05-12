# Plan-Passthrough 0.4.1 — Smoke Notes

Generated 2026-05-12 as Task 15 of [`2026-05-12-plan-passthrough.md`](2026-05-12-plan-passthrough.md). Records what was mechanically verified and what was deferred.

## What was verified (mechanical, on the actual modified files)

### 1. Parser idempotence + counts

`_gen_expected.py` was run twice on the admin-v2 p1 fixture and produced byte-identical output (verified via `git diff --quiet`). Output stats:

- 14 tasks (matches the 14 `### Task N:` headings in the fixture)
- 90 total steps (matches the 90 `- [ ] **Step ` checkboxes)
- 25 `files.create` declarations
- 14 `files.modify` declarations

This validates plan-parser.md Rules 1, 3, 4, 5 against a real writing-plans-format plan.

### 2. YAML schema / example / expected-fixture all parse cleanly

```
schema OK; tasks field present: True
example OK; tasks entries: 2
fixture OK; tasks: 14 / steps total: 90
```

### 3. Cross-reference audit between skills

| From | → To | Status |
|---|---|---|
| skill-0 SKILL.md Phase 2b | lib/plan-parser.md | ✅ 3 refs |
| skill-0 SKILL.md | "plan-passthrough" path described | ✅ 4 refs |
| spec-extractor.md Phase 0 | lib/plan-parser.md | ✅ delegates |
| role-detector.md Signal 0 | writing-plans header | ✅ matches the same substring spec-extractor expects |
| skill-5 Step 5' | source_plan_path detection | ✅ 7 refs |
| skill-5 Step 5'.3 | superpowers:subagent-driven-development / executing-plans | ✅ 8 refs |
| skill-8 Step 4a | "Plan-Passthrough Execution" block | ✅ 4 refs |
| skill-9 Step 1.5 | source_plan_path reading | ✅ 3 refs |
| skill-10 Step 2.5 | task_hints.tasks / source_plan_path | ✅ 6 refs |

The detection signature (`REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development` / `... executing-plans`) is used in BOTH role-detector Signal 0 (classification gate) AND spec-extractor Phase 0 (extraction routing). Both checks must stay in sync — they're intentionally redundant + cheap.

### 4. Backward-compatibility traces

- `skill-3 task-gen` Step 2.5 still triggers Behaviors 1/2/3 when `task_hints.tasks[]` is absent (verified by reading the inserted "Branching note" line + the Step 2.5.0 trigger condition).
- `skill-5 start-task` legacy Step 5 type-specific workflow runs unchanged for tasks without `source_plan_path` (verified by Step 1.4 conditional + Step 5'.3 final fallback path).
- `skill-8 batch-dispatch` legacy Type-Specific Workflow lines are REPLACED (not deleted) when `source_plan_path` is present — for legacy tasks the original lines still apply (verified via the Step 4a opening sentence "REPLACE the 'Type-Specific Workflow' portion ... when ...").
- `skill-9 task-status` Step 1.5 silently skips when `source_plan_path` absent (verified via the "for each task with `source_plan_path`" gate).
- `skill-10 smoke-test` Step 2.5 silently skips when no milestone task has `source_plan_path` (Step 2.5.6 graceful degradation).
- `skill-0` legacy plans (no writing-plans header) fall through Signal 0 to the 4-signal heuristic AND fall through spec-extractor Phase 0 to legacy Steps 1-7 (verified by Step 0.3 of spec-extractor + role-detector "if neither substring is present, fall through" wording).

## What was NOT runtime-verified (deferred)

The plan's Task 15 outlined a sandbox `/tmp/prd2impl-passthrough-smoke` workspace and direct invocation of `/ingest-docs`, `/task-gen`, `/start-task`, `/batch-dispatch`, `/smoke-test`. This was deferred because:

1. Invoking prd2impl skills from this session would activate them on whichever repo Claude Code is in (currently AutoService-dev-a, not the sandbox).
2. Without the prd2impl plugin being re-loaded against the modified `feat/plan-passthrough` branch (not just the cached `0.4.0` install), the dispatched skills would run against the OLD version anyway.
3. A proper runtime smoke happens AFTER merge to upstream + a `prd2impl` plugin update, then on a real consumer project. That's the dogfooding path planned for the next time AutoService picks up an admin-v2 plan.

The mechanical verification above (parser idempotence + count match against 14-task / 90-step fixture + schema parsing + cross-reference grep) covers the parts that don't need a live invocation. The remaining runtime gaps are:

- `/ingest-docs` actually emits `task_hints.tasks[]` (not just that the spec says it would) — relies on whoever runs the skill literally reading and following spec-extractor Phase 0.
- `/task-gen` Step 2.5.0 actually produces 1-task-per-plan-file output — relies on the same.
- `/start-task` Step 5' actually invokes the superpowers skill — relies on the same + whichever superpowers version is installed.
- `/smoke-test` Step 2.5 actually computes the four delta sets correctly — same.

These are all "trust the spec authors and the consumer" checks. Until a consumer dogfoods the new release on the admin-v2 plans, the runtime correctness is provisional.

## Open questions exposed during execution

1. **Step bullet format**: the fixture uses `- [ ] **Step N: <description>**` (whole heading bolded) — NOT `- [ ] **Step N:** <description>` (description outside the bold) that my initial plan-parser Rule 4 assumed. Fixed in commit `bc60070` and the corresponding generator update. **All future writing-plans output must keep the heading fully bolded** — `superpowers:writing-plans` already does this, but a downstream variant could drift.

2. **Slug rule**: GitHub's slugger preserves `_` and does NOT collapse consecutive `-`. My initial plan-parser Rule 1 stripped `_` and collapsed `--`, which would break in-browser anchor navigation to plan tasks. Fixed in commit `bc60070`. **The fixed rule matches GitHub byte-for-byte** so anchors computed by plan-parser are guaranteed to deep-link in rendered markdown.

3. **executing-plans signature** (resolved during plan writing, not execution): `superpowers:executing-plans` v5.1.0 takes no CLI args — it loads the plan in context. This drove the Option B (coarse-grained) granularity decision: prd2impl tasks operate at plan-file granularity, not plan-task granularity. Step 5'.3 delegates the WHOLE plan.

## Suggested next steps for a real dogfooding test

1. Merge `feat/plan-passthrough` to upstream (PR to ezagent42/prd2impl).
2. Update the prd2impl plugin install in `~/.claude/plugins/cache/...` to pick up 0.4.1.
3. From AutoService repo, run `/ingest-docs docs/superpowers/plans/2026-05-11-admin-v2-p1-cr-data-layer.md`.
4. Confirm `docs/plans/m3.5/2026-05-12-task-hints.yaml` (or wherever AutoService's plans_dir is) contains a `tasks` array with 14 entries.
5. Run `/task-gen`. Confirm `tasks.yaml` has one entry `T1` with `source_plan_path` populated.
6. Run `/start-task T1`. Confirm Step 5' fires and delegates to `superpowers:subagent-driven-development`.
7. Let it run end-to-end (or stop after the first plan-task to verify the - [x] tick mechanism).
8. Run `/task-status` mid-flight. Confirm "12/30 steps, 3/8 plan-tasks" style progress.

The smallest possible dogfooding cycle is just steps 3-5: it confirms the ingest→task-gen pipeline works without committing to executing anything.

## Files changed in this branch (summary)

```
$ git log --oneline 0.4.0..HEAD
```

15 commits expected. Verify via `git log --oneline ad0d6e3^..HEAD`. The CHANGELOG entry under `[Unreleased] — 0.4.1` documents each one.
