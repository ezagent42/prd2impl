# prd2impl Skill-Chain Wiring + Framework-Learning Loop

**Status**: design  
**Author**: ezagent42  
**Date**: 2026-05-09  
**Targets release**: 0.4.0  
**Related**: M3 retro (`docs/plans/m3/prd2impl-retro-notes.md` in the AutoService consumer repo), PV2 milestone post-mortem (2026-05-07)

## 1. Background

prd2impl 0.3.1 declares (in `using-prd2impl/SKILL.md`'s capability matrix) that it leverages two companion plugins — `superpowers` and `dev-loop-skills` — for testing discipline, code review, parallel agent dispatch, and milestone verification. A forensic audit of the recently completed Pipeline V2 milestone in the AutoService repo (the largest prd2impl-driven milestone to date) showed the wiring is **shallow**:

- 12+ "should-exist" cross-skill edges are advisory at best (`if available, invoke ...`) or completely missing
- `skill-10-smoke-test` shells out to raw `pytest` instead of calling `dev-loop:skill-4-test-runner`, losing new-vs-regression classification at the milestone gate
- `skill-11-retro` writes a markdown report and stops — there is no `superpowers:writing-skills` callback to patch retro findings back into prd2impl's own SKILL.md templates
- `skill-12-contract-check` is `git diff` text-parsing only; it cannot answer "does this method exist on the real consumer class" — exactly the bug class that bit PV2 (`autoservice/cc_pool.py: AttributeError: 'CCPool' object has no attribute 'acquire_for_session'`, fix commit `cdcfdb2`)
- Neither plugin defines a **mock policy**. A Green task can pass `/continue-task` with a fully-mocked test that proves nothing about real interface compatibility.

The cost of these gaps is concrete: PV2 declared "31/31 GATE PASSED" on 2026-05-07 and shipped 11+ `fix(pv2):` commits within 48 hours, including the deletion of an entire phase (`pipeline_v2/kb_mcp/`) as dead code one day post-gate.

## 2. Goals

Close the wiring gaps so prd2impl meaningfully consumes its declared companion capabilities, with focus on:

1. **Correct implementation + testing** — preflight signature probe before code is written; smoke gate routes through dev-loop's regression-aware runner; mock policy explicitly defined.
2. **Iterative improvement** — retro findings produce concrete patches to the skill templates themselves, not dead-end markdown reports.
3. **Knowledge propagation** — local memory and consumer-repo CLAUDE.md content (env-var class taxonomy, channel parity, hot-reload taxonomy, deferred-scope tombstones) become structured inputs to planning skills, not implicit lore.

## 3. Non-goals

- Renaming or restructuring existing skill files
- Breaking changes to `tasks.yaml` schema (additions only; existing fields stay)
- Replacing the optional-with-graceful-degradation philosophy — companions stay optional; missing companion still leaves prd2impl functional
- Making `dev-loop-skills` or `superpowers` mandatory dependencies

## 4. Audit summary — what's already correct in 0.3.1

These are NOT in scope (already shipped):

- M3 retro R15 — `connector_seam` field in skill-3 (commit `645be4c`)
- M3 retro R11 — Yellow / security tasks force contract re-read in skill-5 (commit `fe9fe01`)
- M3 retro L-B — parallel-line detection at autorun preflight in skill-13 (commit `e0274fb`)
- skill-3's "Pipeline Integration Test Rule" prescribing one integration task per producer/consumer seam

This design extends those without re-doing them.

## 5. Design — ten wiring changes

Organized P0 (highest ROI, ship first) → P2 (still valuable, can defer one release).

### P0-1 · skill-10-smoke-test calls `dev-loop:skill-4-test-runner`

**Motivation**: skill-10 Step 3 today runs `pytest tests/ -k "{phase_keyword}" --tb=short` directly via Bash. dev-loop:skill-4-test-runner already implements:
- New vs regression classification (parsed mechanically from `test-diff` artifact)
- `regression-failure` as a top-level severity that overrides `partial-pass`
- Auto evidence manifest (traceback + last 50 log lines + ps + git log)
- Coverage-matrix update

A milestone gate that doesn't distinguish "new feature broken" from "old feature broken" is structurally weaker than a per-task `/continue-task` run.

**Files touched**:
- `skills/skill-10-smoke-test/SKILL.md` — Step 3 ("Automated Test Verification") rewrites to invoke dev-loop:skill-4-test-runner first; raw `pytest` retained as graceful-degradation fallback only.
- `skills/skill-10-smoke-test/SKILL.md` — Step 5 ("Smoke Test Scenarios") consumes the e2e-report's regression-failure list as a NO-GO trigger, not a footnote.

**Behavior change**:
- When dev-loop is installed: smoke-test invokes `/test-runner` (or equivalent) and reads the resulting `e2e-report` artifact; any `regression-failure` row → automatic NO-GO.
- When dev-loop missing: falls back to raw `pytest` with a logged warning.

**Acceptance**:
- [ ] Running `/smoke-test` in a project with dev-loop installed produces an `e2e-report` artifact with new/regression split.
- [ ] A milestone with one new green test + one regression failure reports NO-GO (not "1 failure, mostly passing").

### P0-2 · skill-12-contract-check AST upgrade + `--preflight` invoked from skill-5

**Motivation**: PV2 commit `cdcfdb2` proved the cost: `runner.prewarm` shipped calling `pool.acquire_for_session(conv_id, tenant_id, role=role)` — a method that **does not exist** on real `CCPool`. The test fake `_FakePool` defined the same fictional method, so 129 unit tests passed for ~14 days while production logged AttributeErrors. A second sibling bug in the same diff (`session_query` `tenant_id` positional-vs-keyword) was caught by yellow review only because `**kw` masked it from the fake.

skill-12 today (Step 2 lines 46–74 of its SKILL.md) parses `git diff` **text** to extract added/removed methods. It does not parse the actual class to enumerate signatures, and it does not parse consumer code to verify that callsite arity matches definition arity.

**Files touched**:
- `skills/skill-12-contract-check/SKILL.md` — replace Step 2's diff-text parser with an AST step (`ast.parse`) that builds a `{Module.Class.method: Signature}` dict for both contract-side and consumer-side files.
- `skills/skill-12-contract-check/SKILL.md` — add Step 2.5 emitting a new `signature_drift` block in the report alongside `affected_files`, listing call-sites where current invocation arity ≠ current definition arity (independent of git diff — this catches drift that already shipped, not just what's changing now).
- `skills/skill-12-contract-check/SKILL.md` — add `--preflight {task_id}` subcommand specification: invoked BEFORE writing code, takes a task ID, AST-parses every symbol named in the task's `must_call_unchanged` list (or, if absent, every external symbol referenced in the task's `affects_files`), reports any non-resolvable symbol or signature mismatch.
- `skills/skill-5-start-task/SKILL.md` — Step 4 ("Load Context") for Yellow tasks AND any task with non-empty `must_call_unchanged` invokes `/contract-check --preflight {task_id}`. Failure → STOP with the unresolved-symbol list, do not allow the implementation step to proceed.
- `skills/skill-3-task-gen/SKILL.md` — task schema gains optional `must_call_unchanged: [Module.Class.method, ...]` field (see P1-4 below for full schema additions).

**Behavior change**:
- `/contract-check` now answers "does this method exist on the real class right now" rather than "did this method appear in the diff text".
- `/contract-check --preflight T4M.3` **before** code-write would have logged: `runner.prewarm calls pool.acquire_for_session — symbol does not exist on autoservice.cc_pool.CCPool. Available methods: acquire, acquire_sticky, acquire_async, ...`. Implementation could not proceed without resolving that.

**Acceptance**:
- [ ] Recreate the cdcfdb2 scenario in a fixture (test repo with a `_FakePool` defining `acquire_for_session` but real `CCPool` defining only `acquire_sticky`). `/contract-check --preflight` flags the call before code is written.
- [ ] Adding a positional-vs-keyword-only mismatch (the T4M.3 sibling bug) is also flagged.
- [ ] Test fixtures live under `skills/skill-12-contract-check/tests/`.

### P0-3 · skill-11-retro closes the framework-learning loop via `superpowers:writing-skills`

**Motivation**: M3 retro produced 13 numbered improvement recommendations (R1–R13). PV2 reproduced nearly identical failure modes a sprint later. The retro is a **dead-end markdown report**: no mechanism exists to translate "yellow review missed contract signature" into a checklist line in `skill-13-autorun/SKILL.md`. The superpowers plugin has `writing-skills` precisely for this — it pressure-tests skill changes against a baseline scenario, ensuring the rule actually triggers.

**Files touched**:
- `skills/skill-11-retro/SKILL.md` — add Step 6 "Framework Learning Loop":
  - For each `improvement_suggestions:` entry, classify by target skill (e.g. "yellow review missed signature" → skill-13).
  - Invoke `superpowers:writing-skills` with the baseline scenario derived from the failure example, the proposed rule text, and the target skill file.
  - Output a `framework-patches/` directory containing one diff per target skill, ready for human review or auto-apply.
- `skills/skill-11-retro/templates/retro-notes.md` (if exists) or new `templates/framework-patch.md` — patch format spec.
- `skills/using-prd2impl/SKILL.md` — capability matrix updates to mention the retro→writing-skills callback.

**Behavior change**:
- Running `/retro M3` now produces both the existing markdown notes AND a `framework-patches/` directory.
- Each patch is an actionable diff with: target skill, baseline failure scenario, proposed rule, and (when writing-skills succeeded) verification that the new rule triggers on the baseline.

**Acceptance**:
- [ ] Running `/retro` on a milestone that had reviewer-missed-signature failure produces a patch targeting `skill-13-autorun/SKILL.md`.
- [ ] Patch includes the baseline scenario in a format the reader can manually replay.

### P1-4 · skill-3-task-gen schema additions + auto color-promote

**Motivation**: The 0.3.1 schema lacks fields that would mechanize lessons already known:
- AutoService memory `feedback_side_channel_strip_parity.md` ("new transport must explicitly call `parse_lead_summary` / `parse_customer_preamble`") cannot be expressed in tasks.yaml today.
- AutoService CLAUDE.md "Environment Variables Class A/B/C" rules: every new env flag has a class, a code default, an ops default. tasks today don't declare any of this.
- AutoService CLAUDE.md "Hot-reload nuance" + the `/admin/cc_pool/recycle_tenant` post-hoc endpoint: tasks today don't declare whether a soul/skill/config change is hot-reload, recycle, or restart.
- M3 retro batch-2 §🟢: "some Green tasks have hidden security surface that should go through review."

**Files touched**:
- `skills/skill-3-task-gen/schemas/task.schema.yaml` — add optional fields:
  - `must_call_unchanged: [Module.Class.method, ...]` — symbols this task must continue to invoke (for skill-12 preflight)
  - `env_var: { name, class: A|B|C, code_default, ops_default, kill_switch_semantics }` — for tasks introducing flags
  - `reload_kind: hot|recycle|restart` — for tasks touching soul/skill/config artifacts
  - `auto_promote_to: yellow` — set automatically when `affects_files` glob matches auth/permission/contract/seam patterns
- `skills/skill-3-task-gen/SKILL.md` — Step 5 "Classification" auto-promotes Green → Yellow when:
  - `affects_files` matches `**/auth*/**`, `**/permission*/**`, `**/*contract*`, `**/*protocol*`, or
  - `must_call_unchanged` is non-empty, or
  - task's `meta.connector_seam: true` (already in 0.3.1 from R15)
- `skills/skill-3-task-gen/templates/tasks.yaml` — example entries showing the new fields.

**Behavior change**:
- A task that touches `gateway/auth/magic_link.py` is auto-classified yellow even if author meant green.
- A task introducing `PIPELINE_V2_DEEPSEEK_TIMEOUT_MS` cannot be generated without declaring its class (B for credentials, C for tunables).
- A task touching `plugins/<tenant>/customer_soul.md` declares `reload_kind: recycle`, and skill-13's closing checklist warns if no recycle command was run before declaring done.

**Acceptance**:
- [ ] task.schema.yaml accepts the new fields, validators reject malformed entries.
- [ ] A fixture task touching auth/* with `type: green` round-trips through skill-3 as `type: yellow auto_promoted: true`.
- [ ] A fixture task introducing an env var without a class is rejected with a clear error.

### P1-5 · skill-9 / skill-11 / skill-12 route through `dev-loop:skill-6-artifact-registry`

**Motivation**: All three skills today read `.artifacts/registry.json` directly with `Read`/`Grep`. dev-loop's skill-6 provides:
- `register.sh`, `query.sh --type --status --summary` (script-level interface)
- `update-status.sh` validating `draft → confirmed → executed → archived` flow (today nothing prevents skipping states)
- Bidirectional `link.sh` for `related_ids` (today links are reconstructed by heuristics each time)

Most importantly: a route through skill-6 lets prd2impl introduce a `task_id` field on artifacts (which skill-6's schema currently allows via `related_ids`) — enabling the reverse query "which tasks have NO executed test-plan", the exact metric the user has been re-discovering manually.

**Files touched**:
- `skills/skill-9-task-status/SKILL.md` — Step 2 "Read registry" replaced with `dev-loop:skill-6-artifact-registry query --task-id {task_id} --status executed`. Fallback to direct file read when dev-loop missing.
- `skills/skill-11-retro/SKILL.md` — Step 4 metrics now include "tasks with no `executed` artifact" derived from registry query.
- `skills/skill-12-contract-check/SKILL.md` — Step 4 "Impact analysis" walks the registry to find tasks whose `deliverables` reference the changed contract file.
- `skills/using-prd2impl/SKILL.md` — capability matrix updated.

**Behavior change**:
- `/task-status` reports "task T2M.3 done; no executed test-plan registered — coverage gap."
- `/retro` final summary table includes "tasks shipped without executed test-plan: N (list)".
- `/contract-check` impact section lists every task whose registered artifacts reference a changed signature.

**Acceptance**:
- [ ] With dev-loop installed, `/task-status` for a milestone with one untested-but-marked-done task surfaces it as a coverage gap.
- [ ] Without dev-loop, behavior matches 0.3.1 (graceful degradation).

### P1-6 · skill-13-autorun yellow review uses `superpowers:subagent-driven-development` two-stage pattern

**Motivation**: superpowers:subagent-driven-development prescribes **two stages** of review per task: spec-compliance reviewer first ("did the task do what was asked, no more"), code-quality reviewer second ("is the code well-structured"). prd2impl 0.3.1 yellow review collapses these into one reviewer pass. The collapse misses the "added unrequested feature" class — exactly what bit PV2 (the entire `pipeline_v2/kb_mcp/` scaffold was over-built per the spec but under-wired in production, deleted as dead code one day post-gate in commit `f82c22e`).

**Files touched**:
- `skills/skill-13-autorun/SKILL.md` — yellow review step (currently lines 124–133) gains an explicit two-stage structure:
  - Stage A: spec-compliance reviewer — input is the task spec + diff, output is "REQUESTED DELIVERED? [Y/N/PARTIAL]" + "EXTRAS NOT REQUESTED: [list]".
  - Stage B: code-quality reviewer — only runs if Stage A returns Y or after PARTIAL is resolved.
  - Both stages dispatch via `superpowers:requesting-code-review` (which already wraps the code-reviewer subagent).
- `skills/skill-8-batch-dispatch/SKILL.md` — closing-checklist text in subagent prompt template (the inlined `cc-prompt-templates.md §6` block) gains the two-stage expectation.
- `skills/skill-5-start-task/SKILL.md` and `skill-6-continue-task/SKILL.md` — Yellow autopilot path mirrors the two-stage flow.

**Behavior change**:
- Yellow tasks receive two reviewer verdicts in commit body, not one.
- A subagent that ships a feature flag, helper, or scaffold not requested by the task spec gets caught at Stage A and asked to drop the extra.

**Acceptance**:
- [ ] Fixture: a yellow task spec asking for "function `foo()` with signature X" — subagent ships `foo()` plus an unrequested `--debug` flag. Stage A flags the extra.
- [ ] Stage B runs only after Stage A clears.

### P2-7 · skill-2-gap-scan emits `conventions.md` cheat-sheet

**Motivation**: AutoService M3 retro batch-2 §🟢 R7 quote: *"contract docs should not invent conventions where project-wide patterns exist. skill-1 / skill-2 should extract 'house conventions' (timestamp format, ID generation, error types) from existing code."* PV2 reproduced this — the kb_mcp scaffold reinvented its own MCP server bootstrap when `cc_pool.py:691` already auto-injects `autoservice_kb`.

**Files touched**:
- `skills/skill-2-gap-scan/SKILL.md` — add Step 3.5 "Conventions extraction":
  - Grep for project-wide patterns: timestamp formats (`datetime.now()` vs `time.time()`), ID generation (`token_urlsafe(N)`, UUID variant), error types, fixture singletons.
  - Emit `{plans_dir}/conventions.md` listing the extracted patterns with file:line citations.
- `skills/skill-3-task-gen/SKILL.md` — Step 4 "Generate tasks" reads `conventions.md` and inlines relevant entries into each task's context block.

**Behavior change**:
- Subagents writing new code see "this project uses `token_urlsafe(36)` for IDs, see `autoservice/customer_manager.py:42`" in their prompt rather than guessing.

**Acceptance**:
- [ ] Running `/gap-scan` on AutoService produces a `conventions.md` listing at least 5 house conventions with file:line.

### P2-8 · using-prd2impl router reads DEFERRED tombstones at start

**Motivation**: AutoService project memory has explicit DEFERRED entries (`project_m3_epic_e2_descoped.md`, `project_m3_4_deferred_to_m3_5.md`, etc.) that say "do not generate tasks for E2.x". Today the router does not consult these — anyone running `/next-task` could be handed a tombstoned story.

**Files touched**:
- `skills/using-prd2impl/SKILL.md` — add Section "Tombstone gate":
  - On any command invocation, glob `{plans_dir}/*.yaml` for entries with `status: DEFERRED_*` or `tombstone: true`.
  - Refuse to dispatch / start / generate against any such entry. Print the tombstone reason and source memory file (if extractable from a comment).
- `skills/skill-3-task-gen/templates/tasks.yaml` — example showing tombstone format.
- `skills/skill-7-next-task/SKILL.md` — explicitly skip tombstoned tasks in candidate ranking.

**Behavior change**:
- `/next-task` cannot recommend a tombstoned story, even if dependencies satisfied.
- `/start-task T-deferred` returns `REFUSED — task is tombstoned (status: DEFERRED_M4 since 2026-04-22, see plans/m3/tasks.yaml#L412)`.

**Acceptance**:
- [ ] Fixture project with one tombstoned + one live task: `/next-task` returns the live one, `/start-task` on the tombstoned one is refused.

### P2-9 · `references/mock-policy.md` — explicit mock policy

**Motivation**: The architectural void identified in the audit. Neither `dev-loop-skills` nor `prd2impl` documents what counts as a correct test. Without a reference rule, subagents in skill-5/skill-6 ship `MagicMock()` without `spec=` and call methods that don't exist on the real class.

**Files touched**:
- `references/mock-policy.md` — new file at plugin root, ~100 lines covering:
  - "What may be mocked" (network/SaaS boundary; subprocess; clock)
  - "What must NOT be mocked" (the system-under-test; modules in the same Python package as the test)
  - "How to mock safely" (`spec=Class` mandatory; `autospec=True` for nested; hand-rolled `_FakeX` requires a paired contract test)
  - "Contract test pattern" (template based on the `test_runner_pool_contract.py` AST-walk shipped retroactively after PV2's cdcfdb2)
- `skills/skill-3-task-gen/SKILL.md` — Step 4 references `references/mock-policy.md` in every task's context block.
- `skills/skill-5-start-task/SKILL.md` — Yellow tasks must read `references/mock-policy.md` before writing tests (similar to the existing R11 contract re-read).
- `skills/skill-6-continue-task/SKILL.md` — test-code phase references the policy.
- `README.md` — link the new reference.

**Behavior change**:
- Subagent prompts now include "before writing a fake, check `references/mock-policy.md`. Bare `MagicMock()` without `spec=` is forbidden in `tests/<production-namespace>/`."
- Reviewer (in skill-13 yellow review Stage A) checks compliance.

**Acceptance**:
- [ ] Reference doc exists and renders correctly.
- [ ] Sample yellow task that ships `MagicMock()` without `spec=` is flagged by reviewer prompt.

### P2-10 · skill-10-smoke-test Layer-3 drift gate via `dev-loop:skill-0-project-builder`

**Motivation**: dev-loop:skill-0 maintains a `baseline_commit` frontmatter on the project's "Skill 1" knowledge file plus a `self-update.sh --check` script returning drift count (new top-level modules, renamed dirs, etc.). prd2impl never invokes it. A milestone can pass `/smoke-test` against a stale module map (which is exactly how the PV2 `kb_mcp/` directory shipped despite duplicating an existing `cc_pool.py:691` mechanism).

**Files touched**:
- `skills/skill-10-smoke-test/SKILL.md` — add Step 0 "Drift Gate":
  - Invoke `dev-loop:skill-0-project-builder self-update --check`
  - If drift count > threshold (configurable, default 50) → emit a `STAGED` warning (not auto NO-GO) prompting the user to run `/bootstrap` re-baseline before gate close.

**Behavior change**:
- Milestones cannot silently pass on a stale baseline.
- Warning rather than block — drift can be intentional.

**Acceptance**:
- [ ] Fixture with intentional drift (new module added since last bootstrap): `/smoke-test` emits the staged warning.
- [ ] When dev-loop missing: skipped with a logged warning, gate proceeds.

## 6. Companion-skill graceful degradation

Every change above respects the optional-with-graceful-degradation philosophy:

| Change | dev-loop missing | superpowers missing |
|---|---|---|
| P0-1 smoke→test-runner | falls back to raw `pytest` | unaffected |
| P0-2 contract-check AST + preflight | unaffected (prd2impl-internal) | unaffected |
| P0-3 retro→writing-skills | unaffected | retro emits patches as plain markdown for manual application |
| P1-4 schema additions | unaffected | unaffected |
| P1-5 artifact-registry | falls back to direct file read | unaffected |
| P1-6 two-stage yellow review | unaffected | falls back to single reviewer (current 0.3.1 behavior) |
| P2-7 conventions extraction | unaffected | unaffected |
| P2-8 tombstone gate | unaffected | unaffected |
| P2-9 mock-policy reference | unaffected | unaffected |
| P2-10 drift gate | warns and skips | unaffected |

## 7. Backward compatibility

- `tasks.yaml` schema additions in P1-4 are all optional fields. Existing tasks without them continue to validate.
- Auto-promote in P1-4 is opt-out: tasks already declaring `type: green` with no auth/permission/contract/seam markers are unchanged.
- All "graceful degradation" paths preserve 0.3.1 behavior bit-for-bit when companions are absent.

## 8. Rollout

- Land all ten changes in a single PR targeting `main`, with one commit per change for reviewability.
- Bump version to `0.4.0` (minor — additive, backward-compatible).
- Tag `v0.4.0` after PR merge.
- Update README "Companion plugins" section to note the deeper integration.

## 9. Risks

- **Risk**: P0-2 AST parsing could be slow on very large repos (10k+ files).  
  **Mitigation**: cache AST parse results keyed on file mtime; preflight only walks files in the task's `must_call_unchanged` or `affects_files`, not the whole repo.

- **Risk**: P0-3 framework patches could land too aggressively, churning skill files every milestone.  
  **Mitigation**: patches go to `framework-patches/` directory for human review by default; auto-apply is a separate opt-in flag.

- **Risk**: P1-6 two-stage review doubles the reviewer LLM cost on yellow tasks.  
  **Mitigation**: stages share context; Stage A is a focused 200-token check; total cost increase ~30%, not 100%. Acceptable given retro shows 14/14 reviewer-caught Critical bugs in M3 — ROI remains overwhelmingly positive.

- **Risk**: P2-9 mock-policy too prescriptive for projects where extensive mocking is genuinely correct.  
  **Mitigation**: policy explicitly lists "may be mocked" categories; project-specific overrides via `{plans_dir}/mock-policy.local.md` extending the reference.

## 10. Open questions

- Should `must_call_unchanged` be auto-derivable from skill-2 gap-scan output (existing import edges in the dependency graph) rather than hand-declared per task? Defer — start with hand-declared, add auto-derivation in 0.5.0 if needed.
- Should retro framework-patches auto-create PRs against the prd2impl repo when run by maintainers? Defer — start with `framework-patches/` as committed artifacts.

## 11. Acceptance criteria (overall)

- [ ] All ten changes implemented with their per-change acceptance lists checked.
- [ ] No regression in 0.3.1 behavior when both companions are absent (`pytest` + manual review still works end-to-end).
- [ ] PV2 cdcfdb2 fixture: `/contract-check --preflight` flags the bug before code is written.
- [ ] PV2 dead-code fixture (kb_mcp scaffold over-built per spec): two-stage yellow review Stage A flags the extra.
- [ ] M3 retro fixture: `/retro` produces a framework patch targeting skill-13 yellow checklist.
