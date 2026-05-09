# prd2impl Skill-Chain Wiring + Framework-Learning Loop — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect prd2impl's declared companion-skill capabilities to actual invocation paths, so that `superpowers` and `dev-loop-skills` are consumed beyond name-dropping.

**Architecture:** Ten additive changes across `skills/` SKILL.md files, schema, and a new `references/mock-policy.md`. All changes preserve 0.3.1 behavior when companions are absent (graceful degradation). One PR with one commit per change.

**Tech Stack:** Markdown SKILL.md files; YAML schemas; bash-style invocation for cross-skill calls; Python AST examples in skill-12 documentation. No source-code language change required (prd2impl is a documentation-driven plugin).

**Spec:** See `docs/superpowers/specs/2026-05-09-skill-chain-wiring-design.md` for design rationale, motivation citations, and per-change acceptance criteria.

---

## Pre-flight

- [ ] **Step 0.1: Confirm clean working tree on `main`**

```bash
git -C D:/Work/h2os.cloud/prd2impl status
```
Expected: `On branch main`, `nothing to commit, working tree clean`.

- [ ] **Step 0.2: Create feature branch**

```bash
git -C D:/Work/h2os.cloud/prd2impl checkout -b feat/skill-chain-wiring
```

- [ ] **Step 0.3: Verify version in `package.json`**

```bash
grep '"version"' D:/Work/h2os.cloud/prd2impl/package.json
```
Expected: `"version": "0.3.1"`. Will bump to `0.4.0` at the end (Task 11).

---

## Task 1 (P0-1): skill-10-smoke-test invokes dev-loop:skill-4-test-runner

**Files:**
- Modify: `skills/skill-10-smoke-test/SKILL.md` — Step 3 ("Automated Test Verification") and Step 5 ("Smoke Test Scenarios").

- [ ] **Step 1.1: Locate Step 3 in skill-10**

```bash
grep -n "Automated Test Verification\|pytest tests" D:/Work/h2os.cloud/prd2impl/skills/skill-10-smoke-test/SKILL.md
```
Capture the line range for Step 3.

- [ ] **Step 1.2: Replace Step 3 with dev-loop-first invocation**

Replace the `pytest`-shells block with the following (keep surrounding context — only swap the verification body):

```markdown
### Step 3: Automated Test Verification

**Primary path (when dev-loop-skills installed):**

Invoke `dev-loop-skills:skill-4-test-runner` and consume its `e2e-report` artifact:

1. Run the test runner scoped to this milestone's phase keyword:
   ```
   /test-runner --phase {phase_keyword} --emit-report
   ```
2. Read the resulting artifact from `.artifacts/e2e-report-{milestone}-*.yaml`.
3. Parse three signal classes:
   - `new_failure: count` — failures in tests added during this milestone
   - `regression_failure: count` — failures in tests that previously passed (auto-escalates to NO-GO regardless of new-test status)
   - `pass_count`, `skip_count`
4. **Gate rule**: any `regression_failure > 0` → NO-GO. `new_failure > 0` → STAGED (review with the user before declaring GO).

**Fallback path (when dev-loop-skills missing):**

Fall back to raw pytest with a logged warning:

```bash
echo "WARN: dev-loop-skills not detected; smoke-test cannot distinguish new vs regression failures. Install dev-loop-skills for milestone-grade reporting."
pytest tests/ -k "{phase_keyword}" --tb=short
```
Treat any failure as ambiguous. Prompt the user to triage manually.
```

- [ ] **Step 1.3: Update Step 5 to consume regression list**

Find Step 5 ("Smoke Test Scenarios") and add at the end:

```markdown
### Step 5.x: Regression list as NO-GO trigger

If Step 3's `e2e-report` listed any `regression_failure`, copy each row into the gate report's `## Blocking failures` section verbatim. Do NOT downgrade these to "1 env-blocked, structurally identical" — that footnote pattern is what the design spec §1 explicitly forbids.
```

- [ ] **Step 1.4: Commit**

```bash
git add skills/skill-10-smoke-test/SKILL.md
git commit -m "feat(skill-10): route smoke-test through dev-loop:skill-4-test-runner

Step 3 now invokes dev-loop's regression-aware runner; raw pytest
retained as graceful-degradation fallback. Regression failures are
auto-NO-GO, ending the 'env-blocked, structurally identical' footnote
pattern that masked PV2 gate issues.

Spec: docs/superpowers/specs/2026-05-09-skill-chain-wiring-design.md §5 P0-1"
```

---

## Task 2 (P0-2 part 1): skill-12-contract-check AST upgrade

**Files:**
- Modify: `skills/skill-12-contract-check/SKILL.md` — replace Step 2 diff-text parser with AST step; add Step 2.5 signature_drift; add `--preflight` subcommand spec.
- Create: `skills/skill-12-contract-check/references/ast-walk-template.md` — reusable AST template based on `tests/pipeline_v2/test_runner_pool_contract.py` from AutoService.

- [ ] **Step 2.1: Read current Step 2 of skill-12 to understand the structure to replace**

```bash
grep -n "^### Step \|^## Step " D:/Work/h2os.cloud/prd2impl/skills/skill-12-contract-check/SKILL.md
```

- [ ] **Step 2.2: Replace Step 2 body with AST-based contract enumeration**

Replace the diff-text parsing block with:

```markdown
### Step 2: Build signature dictionary via AST

For each contract-side file from Step 1, parse its AST to enumerate `{Module.Class.method: Signature}`:

```python
import ast
import inspect

def enumerate_contract(path):
    """Returns {qualified_name: signature_string} for every public method in path."""
    tree = ast.parse(open(path).read())
    out = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and not item.name.startswith('_'):
                    qual = f"{path}::{node.name}.{item.name}"
                    args = [a.arg for a in item.args.args]
                    kwonly = [a.arg for a in item.args.kwonlyargs]
                    out[qual] = {
                        'positional': args,
                        'keyword_only': kwonly,
                        'has_varargs': item.args.vararg is not None,
                        'has_varkw': item.args.kwarg is not None,
                    }
    return out
```

Store the resulting dict as the **canonical contract snapshot** for this run.

For TypeScript / JS contracts, use a parallel `tree-sitter-typescript` walk; if unavailable, fall back to the 0.3.1 grep-based extraction with a logged warning.
```

- [ ] **Step 2.3: Add Step 2.5 signature_drift block**

After Step 2, insert:

```markdown
### Step 2.5: Detect signature drift in consumer code

For each consumer file found in Step 3 (existing logic), AST-walk it and find every `Call` node:

```python
def find_calls(consumer_path, contract_snapshot):
    """Yield (callsite, qualified_name, actual_signature) for every call to a tracked method."""
    tree = ast.parse(open(consumer_path).read())
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            target = resolve_callee(node, tree)  # via local symbol table
            if target in contract_snapshot:
                actual = {
                    'positional_count': len(node.args),
                    'keyword_names': [kw.arg for kw in node.keywords if kw.arg],
                }
                yield (node.lineno, target, actual)

def signature_drift(actual, definition):
    """Return list of mismatches."""
    drifts = []
    if actual['positional_count'] > len(definition['positional']) and not definition['has_varargs']:
        drifts.append(f"too many positional args: {actual['positional_count']} > {len(definition['positional'])}")
    for kw in actual['keyword_names']:
        if kw not in definition['positional'] and kw not in definition['keyword_only'] and not definition['has_varkw']:
            drifts.append(f"unknown keyword: {kw}")
    # Detect positional passing of a keyword-only arg (the T4M.3 pattern)
    for i, pos_name in enumerate(definition['positional'][:actual['positional_count']]):
        if pos_name in definition['keyword_only']:
            drifts.append(f"keyword-only arg '{pos_name}' passed positionally")
    return drifts
```

Emit a `signature_drift` block in the report:

```yaml
signature_drift:
  - file: autoservice/pipeline_v2/main_agent/runner.py
    line: 142
    target: autoservice.cc_pool.CCPool.acquire_for_session
    issue: symbol does not exist on real class
    available_methods: [acquire, acquire_sticky, acquire_async]
  - file: autoservice/pipeline_v2/main_agent/runner.py
    line: 218
    target: autoservice.cc_pool.CCPool.session_query
    issue: keyword-only arg 'tenant_id' passed positionally
```

This catches drift that already shipped (independent of git diff) — the cdcfdb2 bug class.
```

- [ ] **Step 2.4: Create AST walk template file**

```bash
mkdir -p D:/Work/h2os.cloud/prd2impl/skills/skill-12-contract-check/references
```

Write `skills/skill-12-contract-check/references/ast-walk-template.md` with content adapted from AutoService's `tests/pipeline_v2/test_runner_pool_contract.py` (the cdcfdb2 retroactive contract test). Content:

```markdown
# AST Walk Template — Contract Test Generator

This template generates a pytest contract test that AST-walks a consumer
file and asserts every external call resolves to a real method on the
target class with a compatible signature. Adapted from the
`test_runner_pool_contract.py` pattern shipped after AutoService PV2
commit cdcfdb2.

## Template

```python
"""Auto-generated contract test for {consumer_module} -> {target_class}.
Verifies every method called on {target_class_short} exists with a
compatible signature. Regenerate by running /contract-check --preflight.
"""
import ast
import inspect
import pytest
from {target_module} import {target_class_short}

CONSUMER_PATH = "{consumer_relative_path}"

def _calls_to_pool(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            attr = node.func
            if isinstance(attr, ast.Attribute) and isinstance(attr.value, ast.Name):
                if attr.value.id in {{ "pool", "self.pool", "_pool" }}:
                    yield node, attr.attr

def test_consumer_calls_resolve_on_real_class():
    src = open(CONSUMER_PATH).read()
    tree = ast.parse(src)
    real_methods = {{
        name: inspect.signature(getattr({target_class_short}, name))
        for name in dir({target_class_short})
        if callable(getattr({target_class_short}, name)) and not name.startswith("_")
    }}
    unresolved = []
    for call_node, method_name in _calls_to_pool(tree):
        if method_name not in real_methods:
            unresolved.append((call_node.lineno, method_name))
    assert not unresolved, (
        f"Consumer {{CONSUMER_PATH}} calls non-existent methods on "
        f"{target_class_short}: {{unresolved}}"
    )

def test_consumer_callsites_match_signatures():
    # ... (see full implementation in design spec §5 P0-2)
    pass
```

## Where to use

- Drop this template into the project's `tests/contract/` directory
  per consumer/target pair flagged by `/contract-check --preflight`.
- Run on CI; failure prevents the cdcfdb2 bug class from shipping.
```

- [ ] **Step 2.5: Verify AST template renders**

```bash
cat D:/Work/h2os.cloud/prd2impl/skills/skill-12-contract-check/references/ast-walk-template.md | head -20
```
Expected: title and template start visible.

- [ ] **Step 2.6: Commit Task 2 (without --preflight wiring yet)**

```bash
git add skills/skill-12-contract-check/SKILL.md skills/skill-12-contract-check/references/
git commit -m "feat(skill-12): AST-based contract snapshot + signature_drift detection

Replaces git-diff text parsing (0.3.1) with ast.parse() over both
contract-side and consumer-side files. New Step 2.5 emits
signature_drift block catching call-arity mismatches independent of
git changes — i.e. drift that already shipped, the cdcfdb2 bug class.

New references/ast-walk-template.md provides reusable contract test
generator based on AutoService PV2 retro fix (test_runner_pool_contract.py).

Spec: docs/superpowers/specs/2026-05-09-skill-chain-wiring-design.md §5 P0-2"
```

---

## Task 3 (P0-2 part 2): `/contract-check --preflight` subcommand + skill-5 wiring

**Files:**
- Modify: `skills/skill-12-contract-check/SKILL.md` — add `--preflight {task_id}` subcommand.
- Modify: `skills/skill-5-start-task/SKILL.md` — Step 4 ("Load Context") for Yellow tasks invokes `/contract-check --preflight`.

- [ ] **Step 3.1: Append `--preflight` section to skill-12**

Append at the end of `skills/skill-12-contract-check/SKILL.md`:

```markdown
## Preflight subcommand: `/contract-check --preflight {task_id}`

Invoked BEFORE writing code, by `skill-5-start-task` Step 4 for any task
that satisfies one of:
- `type: yellow` (always)
- `must_call_unchanged: [...]` is non-empty
- `affects_files` glob matches `**/*contract*` or `**/*protocol*`

### Inputs
- `{task_id}` — looked up in `{plans_dir}/tasks.yaml`

### Behavior
1. Load the task definition. Extract `must_call_unchanged` (preferred) or compute it from `affects_files` by AST-walking each file's external imports.
2. For each `Module.Class.method` symbol:
   - Resolve via `inspect`/`ast` against HEAD.
   - If unresolvable → emit `unresolved_symbols: [...]`.
   - If resolvable but signature differs from what the task spec implies → emit `signature_concerns: [...]`.
3. Output: short YAML report at `{plans_dir}/preflight/{task_id}.yaml`.
4. Exit code: `0` if clean, `1` if any unresolved or concerning entries.

### Example output (PV2 cdcfdb2 fixture)

```yaml
task_id: T4M.3
unresolved_symbols:
  - target: autoservice.cc_pool.CCPool.acquire_for_session
    referenced_in_spec: docs/superpowers/specs/2026-05-07-pipeline-v2-three-color-design.md §6
    available_on_target: [acquire, acquire_sticky, acquire_async]
    suggested_action: confirm with user — did you mean acquire_sticky?
signature_concerns:
  - target: autoservice.cc_pool.CCPool.session_query
    spec_implies: positional (conv_id, prompt, tenant_id, ...)
    real_signature: (conv_id, prompt, *, tenant_id=None, ...)
    issue: tenant_id is keyword-only after *
verdict: STOP — implementation must not proceed until unresolved_symbols is empty
```

### Failure path

When `--preflight` returns non-zero, skill-5-start-task halts the task
with the report content displayed to the user. The user resolves by
either updating the task spec or correcting the underlying assumption.
```

- [ ] **Step 3.2: Locate Step 4 in skill-5**

```bash
grep -n "Step 4\|Load Context" D:/Work/h2os.cloud/prd2impl/skills/skill-5-start-task/SKILL.md
```

- [ ] **Step 3.3: Add preflight invocation to skill-5 Step 4**

Insert after the existing "Yellow Step 4 — Re-read contract" block (added in commit fe9fe01):

```markdown
### Step 4.5: Preflight signature probe (Yellow + must_call_unchanged tasks)

**Trigger condition**: task `type: yellow` OR `must_call_unchanged` non-empty
OR `affects_files` matches `**/*contract*` / `**/*protocol*`.

Invoke:
```
/contract-check --preflight {task_id}
```

Read the resulting `{plans_dir}/preflight/{task_id}.yaml`.

**If `verdict: STOP`** — display the report to the user, halt the task.
Do NOT proceed to test-plan or implementation. Possible resolutions:
- Update task spec to use the correct symbol name.
- Update task spec to acknowledge the signature change.
- If symbol is genuinely missing because the contract file is being
  introduced in this task, mark the preflight skipped with a comment.

**If `verdict: PROCEED`** — continue to Step 5 (test-plan generation)
with the preflight report attached to the task's context block.

Without the preflight, the cdcfdb2 bug class (subagent invents a method
name; fake test double mirrors the invention; CI green; production
AttributeError) ships routinely. See spec §5 P0-2.

**Graceful degradation**: if `/contract-check` is not registered (older
prd2impl install), emit a logged warning and proceed. Document this
risk to the user once per session.
```

- [ ] **Step 3.4: Commit Task 3**

```bash
git add skills/skill-12-contract-check/SKILL.md skills/skill-5-start-task/SKILL.md
git commit -m "feat(skill-12,skill-5): /contract-check --preflight subcommand + Yellow gate

Adds preflight signature probe invoked from skill-5-start-task Step 4.5
for any Yellow task or task declaring must_call_unchanged. Halts
implementation when target symbols are unresolvable on real classes
(the cdcfdb2 bug class).

Spec: docs/superpowers/specs/2026-05-09-skill-chain-wiring-design.md §5 P0-2"
```

---

## Task 4 (P0-3): skill-11-retro framework-learning loop

**Files:**
- Modify: `skills/skill-11-retro/SKILL.md` — add Step 6 "Framework Learning Loop".
- Create: `skills/skill-11-retro/templates/framework-patch.md` — patch format spec.
- Modify: `skills/using-prd2impl/SKILL.md` — capability matrix mentions retro→writing-skills callback.

- [ ] **Step 4.1: Append Step 6 to skill-11**

```bash
grep -n "^## Step\|^### Step" D:/Work/h2os.cloud/prd2impl/skills/skill-11-retro/SKILL.md
```

Append at the end of skill-11/SKILL.md, before any closing/final-notes section:

```markdown
## Step 6: Framework Learning Loop

Closes the dead-end-report problem identified in design spec §5 P0-3:
retro findings must produce concrete patches to prd2impl skill files,
not just markdown observations.

### Inputs
- `improvement_suggestions:` block from the retro report (Step 5 output)
- The current skill files at `skills/*/SKILL.md` in this plugin

### Procedure

1. **Classify each suggestion by target skill.** Heuristics:
   - "yellow review missed contract X" → `skill-13-autorun/SKILL.md` yellow checklist
   - "task generated for tombstoned story" → `skills/using-prd2impl/SKILL.md` tombstone gate
   - "test passed but missed prod bug" → `references/mock-policy.md` (P2-9) or `skill-3-task-gen/SKILL.md` connector_seam expansion
   - "dead code shipped per spec" → `skill-13-autorun/SKILL.md` two-stage yellow review (P1-6)

2. **For each classified suggestion**, derive:
   - **Baseline scenario** — a runnable description of the failure (e.g. "Yellow task whose diff calls `pool.acquire_for_session` which does not exist on real `CCPool`; current skill-13 review approves it; expected after patch: review fails")
   - **Proposed rule text** — concrete sentence(s) to insert into the target SKILL.md
   - **Insertion point** — the section heading or line number where the rule belongs

3. **Invoke `superpowers:writing-skills`** with the baseline scenario,
   proposed rule, and target file. The writing-skills skill pressure-tests
   the rule against the baseline:
   - Without rule → baseline fails (the bug ships)
   - With rule → baseline passes (the bug is caught)
   - If pressure test fails → revise the rule until it does

4. **Emit one patch per suggestion** under
   `{plans_dir}/framework-patches/{slug}.md` using
   `templates/framework-patch.md` format.

### Output

`{plans_dir}/framework-patches/` directory containing N patches, each
ready for human review or auto-apply via a separate `/apply-framework-patches`
flow (out of scope for 0.4.0; manual application by maintainer).

### Graceful degradation

If `superpowers:writing-skills` is not installed, retro emits the
markdown patch without the pressure-test step. Patch file documents
that pressure testing was skipped.

### Why this matters

M3 retro produced 13 numbered recommendations (R1–R13) in
`docs/plans/m3/prd2impl-retro-notes.md`. Most were never propagated
into prd2impl skill templates. PV2 reproduced nearly identical failure
modes a sprint later. This loop changes retros from dead-end reports
into framework-update sources.
```

- [ ] **Step 4.2: Create framework-patch template**

Write `skills/skill-11-retro/templates/framework-patch.md`:

```markdown
# Framework Patch — {slug}

**Source retro**: {plans_dir}/retro-notes.md (suggestion {N})
**Target skill file**: skills/{target}/SKILL.md
**Insertion section**: {section_heading_or_line}
**Pressure-tested via writing-skills**: yes / no / skipped

## Baseline scenario (runnable failure)

{1-3 sentence description, including a concrete commit/file reference
when available, that an engineer can manually replay to confirm the
bug ships under current rules}

## Proposed rule

{Concrete markdown to insert into target SKILL.md, ready to copy-paste}

## Pressure test result

{If superpowers:writing-skills was invoked: report whether the new rule
caught the baseline. If skipped: note "skipped — superpowers not installed"}

## How to apply

1. Open `skills/{target}/SKILL.md`
2. Find {section_heading} (or insert after line {N})
3. Paste the "Proposed rule" block
4. Replay the baseline scenario; confirm the rule fires.
5. Commit with message: `feat({target}): {short rule description} (retro {milestone})`
```

- [ ] **Step 4.3: Update using-prd2impl capability matrix**

```bash
grep -n "writing-skills\|capability matrix" D:/Work/h2os.cloud/prd2impl/skills/using-prd2impl/SKILL.md
```

Find the superpowers row in the capability matrix; add `writing-skills` as a consumed capability with note "retro Step 6 invokes writing-skills to pressure-test framework patches".

- [ ] **Step 4.4: Commit Task 4**

```bash
git add skills/skill-11-retro/SKILL.md skills/skill-11-retro/templates/ skills/using-prd2impl/SKILL.md
git commit -m "feat(skill-11): framework-learning loop via superpowers:writing-skills

Retro Step 6 classifies each improvement_suggestion by target skill,
derives a baseline failure scenario, invokes writing-skills to
pressure-test the proposed rule, and emits framework-patches/{slug}.md.
Closes the dead-end-report problem: M3 retro produced 13
recommendations and PV2 reproduced nearly identical failures a sprint
later; this loop turns retros into actual skill updates.

Spec: docs/superpowers/specs/2026-05-09-skill-chain-wiring-design.md §5 P0-3"
```

---

## Task 5 (P1-4): skill-3 schema additions + auto color-promote

**Files:**
- Modify: `skills/skill-3-task-gen/schemas/task.schema.yaml` — add four optional fields.
- Modify: `skills/skill-3-task-gen/SKILL.md` — Step 5 auto-promote logic.
- Modify: `skills/skill-3-task-gen/templates/tasks.yaml` — example with new fields.

- [ ] **Step 5.1: Read current schema**

```bash
cat D:/Work/h2os.cloud/prd2impl/skills/skill-3-task-gen/schemas/task.schema.yaml
```

- [ ] **Step 5.2: Add fields to task.schema.yaml**

After the existing optional-fields section, add:

```yaml
  # P1-4 (0.4.0) — see spec 2026-05-09-skill-chain-wiring-design.md §5
  must_call_unchanged:
    type: array
    description: |
      Symbols (Module.Class.method or function) this task must continue
      to invoke unchanged. Consumed by skill-12-contract-check --preflight
      to verify each symbol resolves on real production classes before
      code is written. Prevents the cdcfdb2 bug class.
    items:
      type: string
      pattern: "^[A-Za-z_][A-Za-z0-9_.]*$"
    default: []

  env_var:
    type: object
    description: |
      For tasks introducing a new feature flag / env var, declare its
      class and operational profile. Class A = security boundary
      (Makefile-pinned, never in .env); Class B = credential (.env
      REQUIRED block); Class C = feature flag / tunable. Mirrors the
      AutoService CLAUDE.md "Environment Variables" taxonomy.
    properties:
      name:
        type: string
        pattern: "^[A-Z][A-Z0-9_]*$"
      class:
        type: string
        enum: [A, B, C]
      code_default:
        type: string
        description: "Default the code uses if env unset."
      ops_default:
        type: string
        description: "Default operations actually runs with. May differ from code_default — when so, the gap must land in CLAUDE.md OVERRIDES block."
      kill_switch_semantics:
        type: string
        description: "What happens when set to 0 / unset / non-default."
    required: [name, class]

  reload_kind:
    type: string
    description: |
      Whether changes from this task take effect via hot-reload
      (no process action), tenant recycle (recycle_tenant API), or
      full restart (make stop && make start). Required when task
      affects soul/skill/config artifacts.
    enum: [hot, recycle, restart]

  auto_promoted:
    type: boolean
    description: |
      Set by skill-3 Step 5 when a task originally typed Green is
      auto-promoted to Yellow because it touches auth/permission/
      contract/seam patterns. Auditable signal for reviewer-routing
      decisions.
    default: false
```

- [ ] **Step 5.3: Add auto-promote logic to skill-3 SKILL.md Step 5**

Locate Step 5 ("Classification" / Green-Yellow-Red rules) and append:

```markdown
### Step 5.x: Auto color-promotion (0.4.0+)

After applying the standard Green/Yellow/Red rules, run the
auto-promote check. A task originally typed Green is promoted to
Yellow when ANY of:

1. `affects_files` glob matches `**/auth*/**`, `**/permission*/**`,
   `**/login*`, `**/token*`, `**/credential*`
2. `affects_files` matches `**/*contract*`, `**/*protocol*`,
   `**/*schema*` (excluding test files)
3. `must_call_unchanged` list is non-empty
4. `meta.connector_seam: true` (already present from R15 / 0.3.1)
5. `env_var.class: A` (security boundary)

When auto-promotion fires, set `type: yellow` and `auto_promoted: true`
on the generated task. Yellow handling proceeds as normal (review,
preflight, contract re-read).

Rationale: M3 retro batch-2 §🟢 finding "some Green tasks have hidden
security surface that should go through review." The 14/14 reviewer-
caught Critical bug rate in M3 confirms this is high ROI.
```

- [ ] **Step 5.4: Update example tasks.yaml template**

Add a fully-populated example to `skills/skill-3-task-gen/templates/tasks.yaml` showing all new fields together:

```yaml
- id: T-EXAMPLE.1
  name: "Wire pre-flight contract probe to dispatch path"
  type: yellow
  effort: medium
  phase: P1
  depends_on: []
  affects_files:
    - autoservice/cc_pool.py
  must_call_unchanged:
    - autoservice.cc_pool.CCPool.acquire_sticky
    - autoservice.cc_pool.CCPool.session_query
  env_var:
    name: PIPELINE_V2_PREFLIGHT_ENABLED
    class: C
    code_default: "1"
    ops_default: "1"
    kill_switch_semantics: "0 = skip preflight, fall back to 0.3.1 behavior"
  reload_kind: restart
  deliverables:
    - { type: code, path: autoservice/pipeline_v2/main_agent/runner.py }
    - { type: test, path: tests/pipeline_v2/test_runner_pool_contract.py }
  verification: "pytest tests/pipeline_v2/test_runner_pool_contract.py -v"
```

- [ ] **Step 5.5: Commit Task 5**

```bash
git add skills/skill-3-task-gen/
git commit -m "feat(skill-3): task schema must_call_unchanged + env_var + reload_kind + auto-promote

Four optional schema additions + auto color-promotion rules. Tasks
touching auth/permission/contract/seam patterns or carrying non-empty
must_call_unchanged are auto-promoted Green->Yellow. env_var requires
class A/B/C declaration and code-vs-ops default acknowledgement.
reload_kind makes soul/skill/config recycle policy explicit.

All fields are optional; existing tasks continue to validate.

Spec: docs/superpowers/specs/2026-05-09-skill-chain-wiring-design.md §5 P1-4"
```

---

## Task 6 (P1-5): skill-9 / skill-11 / skill-12 route through dev-loop:skill-6-artifact-registry

**Files:**
- Modify: `skills/skill-9-task-status/SKILL.md` — Step 2 reads via dev-loop registry.
- Modify: `skills/skill-11-retro/SKILL.md` — Step 4 metrics include "tasks with no executed test-plan".
- Modify: `skills/skill-12-contract-check/SKILL.md` — Step 4 impact analysis walks registry.

- [ ] **Step 6.1: Update skill-9 Step 2**

Find skill-9-task-status Step 2 and replace direct `Read .artifacts/registry.json` with:

```markdown
### Step 2: Read registry (via dev-loop:skill-6-artifact-registry)

**Primary path** (dev-loop installed):
```
/artifact-registry query --task-id {task_id} --status executed
```
Consume the returned list as the task's artifact set.

**Fallback** (dev-loop missing):
Fall back to direct read of `.artifacts/registry.json`. Document this
as a coverage-gap risk (no schema validation, no link integrity check).
```

- [ ] **Step 6.2: Update skill-11 Step 4 metrics**

Append to skill-11 Step 4 ("Quality signals"):

```markdown
### Step 4.x: Coverage-gap signal

Query the registry for tasks marked `done` in `task-status.md` but
lacking any artifact with `status: executed`:

```
/artifact-registry query --status-not executed --linked-task-status done
```

Each row is a coverage gap — a task that shipped without observed
test execution. Surface in retro report as "Tasks shipped without
executed test-plan: N". This is the metric the user has been
re-discovering manually after every milestone.
```

- [ ] **Step 6.3: Update skill-12 Step 4 impact analysis**

Append to skill-12 Step 4:

```markdown
### Step 4.x: Registry-driven impact propagation

For each contract symbol that drifted, walk the registry to find
every task whose `deliverables[].path` references the changed file:

```
/artifact-registry query --references {changed_file_path}
```

Emit `impacted_tasks: [...]` in the report. For each impacted task,
flag whether it has an executed test-plan covering the drifted symbol;
if not, recommend a re-test action.
```

- [ ] **Step 6.4: Commit Task 6**

```bash
git add skills/skill-9-task-status/SKILL.md skills/skill-11-retro/SKILL.md skills/skill-12-contract-check/SKILL.md
git commit -m "feat(skill-9,11,12): route artifact reads via dev-loop:skill-6-artifact-registry

Three skills previously read .artifacts/registry.json directly with
Read/Grep, missing dev-loop's status-validation, link integrity, and
query interface. Now route through skill-6 with graceful fallback.

Enables the 'tasks shipped without executed test-plan' metric in
retro reports — the coverage gap the user has been manually
re-discovering after every milestone.

Spec: docs/superpowers/specs/2026-05-09-skill-chain-wiring-design.md §5 P1-5"
```

---

## Task 7 (P1-6): skill-13-autorun yellow review two-stage pattern

**Files:**
- Modify: `skills/skill-13-autorun/SKILL.md` — yellow review block becomes two-stage.
- Modify: `skills/skill-8-batch-dispatch/SKILL.md` — closing-checklist block in subagent prompt template.
- Modify: `skills/skill-5-start-task/SKILL.md` and `skill-6-continue-task/SKILL.md` — yellow autopilot mirrors.

- [ ] **Step 7.1: Locate yellow review block in skill-13**

```bash
grep -n "Yellow\|yellow" D:/Work/h2os.cloud/prd2impl/skills/skill-13-autorun/SKILL.md | head -20
```

- [ ] **Step 7.2: Replace single-stage yellow review with two-stage**

Find the yellow self-review block (currently lines ~124–133) and replace with:

```markdown
### Yellow review (two-stage, 0.4.0+)

Yellow tasks receive two reviewer subagent passes per
superpowers:subagent-driven-development. The single-stage review
that 0.3.1 ran missed the "added unrequested feature" class — exactly
what produced the AutoService PV2 dead-code phenomenon (entire
`pipeline_v2/kb_mcp/` directory shipped per spec, deleted as dead
code one day post-gate in commit f82c22e).

#### Stage A — Spec compliance reviewer

Invoke `superpowers:requesting-code-review` with prompt focused on:
- "Did the diff deliver every item in the task spec? List any missing."
- "Did the diff add ANY code, files, helpers, flags, or tests not
  requested by the task spec? List every extra."
- Output verdict: REQUESTED_DELIVERED [Y/N/PARTIAL] + EXTRAS [list].

If verdict is N or extras non-empty → revise the diff to either match
spec or update spec (with user confirmation) before Stage B.

#### Stage B — Code quality reviewer

Only after Stage A clears, invoke `superpowers:requesting-code-review`
again with prompt focused on:
- Code quality (naming, structure, error handling, tests, docs)
- Standard 0.3.1 yellow review checklist
- Returns ≥1 blocking → revise once, then accept.

#### Cost note

Stage A is a focused 200-token check. Total reviewer cost increase
~30% over 0.3.1, not 100%. Justified by retro evidence that Stage A
catches a class of bugs single-stage review misses (over-building
per spec but under-wiring in production).
```

- [ ] **Step 7.3: Mirror in skill-5 (Yellow autopilot path)**

Find skill-5 Yellow autopilot section and add a reference:

```markdown
### Yellow autopilot — review stages

Per skill-13 §Yellow review (two-stage), Yellow tasks reaching close
in autopilot mode receive Stage A spec-compliance review FIRST, then
Stage B code-quality review. Both stages dispatch via
`superpowers:requesting-code-review`. See skill-13 for full
specification.

**Graceful degradation**: when superpowers missing, fall back to
single-stage review (0.3.1 behavior).
```

- [ ] **Step 7.4: Mirror in skill-6 (continue-task close path)**

Same insertion in skill-6's close section.

- [ ] **Step 7.5: Update skill-8 dispatch closing checklist**

Locate the inlined closing-checklist block in skill-8's subagent
prompt template; add a line:

```markdown
- For Yellow tasks: expect two reviewer passes. Stage A checks "did
  you deliver only what was asked"; Stage B checks code quality.
  Do NOT bundle extras; spec wins.
```

- [ ] **Step 7.6: Commit Task 7**

```bash
git add skills/skill-13-autorun/SKILL.md skills/skill-5-start-task/SKILL.md skills/skill-6-continue-task/SKILL.md skills/skill-8-batch-dispatch/SKILL.md
git commit -m "feat(skill-13,5,6,8): two-stage yellow review (spec-compliance then code-quality)

Per superpowers:subagent-driven-development, yellow tasks now receive
two reviewer passes: Stage A asks 'did you deliver only what was
asked' (catches over-building); Stage B is the existing 0.3.1
code-quality review. Both via superpowers:requesting-code-review.

Targets the AutoService PV2 dead-code phenomenon (entire kb_mcp/
phase shipped per spec, deleted next day) where single-stage review
approves spec-fidelity-without-questioning-spec-fidelity-itself.

Graceful degradation: superpowers missing -> single-stage (0.3.1).

Spec: docs/superpowers/specs/2026-05-09-skill-chain-wiring-design.md §5 P1-6"
```

---

## Task 8 (P2-7): skill-2 conventions extraction

**Files:**
- Modify: `skills/skill-2-gap-scan/SKILL.md` — add Step 3.5 conventions extraction.
- Modify: `skills/skill-3-task-gen/SKILL.md` — Step 4 reads conventions.md into task context.

- [ ] **Step 8.1: Locate Step 3 in skill-2**

```bash
grep -n "^### Step\|^## Step" D:/Work/h2os.cloud/prd2impl/skills/skill-2-gap-scan/SKILL.md
```

- [ ] **Step 8.2: Add Step 3.5 to skill-2**

After existing Step 3 (gap detection), insert:

```markdown
### Step 3.5: House conventions extraction

Subagents writing new code should follow project-wide patterns rather
than reinventing them. Extract recurring patterns into a cheat-sheet
that skill-3 inlines into every task's context.

Patterns to extract via Grep:

1. **Timestamp format** — `datetime.utcnow()` vs `time.time()` vs ISO
   string. Capture the dominant pattern + 2 example file:line.
2. **ID generation** — `uuid.uuid4()`, `secrets.token_urlsafe(N)`,
   custom prefix scheme. Capture pattern + N + example.
3. **Error types** — project-defined exception classes, common
   inheritance (e.g. `class FooError(BaseError)`). List top 5 by
   reference count.
4. **Test fixture singletons** — `_reset_*_db_for_tests` patterns,
   conftest scope conventions.
5. **Logging** — logger name pattern, structured log helper if any.

Emit `{plans_dir}/conventions.md` with:

```markdown
# Project conventions (extracted by skill-2-gap-scan)

## Timestamps
- Format: ISO 8601 strings (`datetime.utcnow().isoformat()`)
- Source: autoservice/customer_manager.py:42, autoservice/crm.py:118
- Avoid: epoch ints, naive datetimes

## ID generation
- Pattern: `secrets.token_urlsafe(36)`
- Source: autoservice/customer_manager.py:42

(... continued for each pattern ...)
```

This file becomes a stable input to skill-3-task-gen Step 4.

Rationale: AutoService M3 retro batch-2 §🟢 R7 quote: *"contract docs
should not invent conventions where project-wide patterns exist. skill-1
/ skill-2 should extract 'house conventions'..."* PV2 reproduced
this — the kb_mcp scaffold reinvented MCP server bootstrap when
`cc_pool.py:691` already did the same job.
```

- [ ] **Step 8.3: Update skill-3 Step 4 to read conventions**

In skill-3-task-gen SKILL.md, find Step 4 ("Generate tasks"); add:

```markdown
### Step 4.x: Inline conventions into task context

Before emitting each task, read `{plans_dir}/conventions.md` (if
exists, written by skill-2 Step 3.5). For each task whose
`affects_files` glob matches a file referenced by the conventions
cheat-sheet, inline the relevant conventions into the task's
`context_block` field.

Example task context after inlining:

```yaml
- id: T-EXAMPLE.2
  context_block: |
    Project conventions for files touched here:
    - IDs: secrets.token_urlsafe(36) (see autoservice/customer_manager.py:42)
    - Timestamps: ISO 8601 (`datetime.utcnow().isoformat()`)
    - Logger: `logger = logging.getLogger(__name__)` per module
```

Subagents in skill-8 see this in their dispatch prompt, eliminating
the "reinvented ID format" and "reinvented MCP bootstrap" failure
modes.
```

- [ ] **Step 8.4: Commit Task 8**

```bash
git add skills/skill-2-gap-scan/SKILL.md skills/skill-3-task-gen/SKILL.md
git commit -m "feat(skill-2,3): extract house conventions, inline into task context

skill-2 Step 3.5 now greps for project-wide patterns (timestamps, ID
generation, error types, fixtures, logging) and emits conventions.md.
skill-3 Step 4 reads it and inlines relevant entries into each task's
context_block, so subagents see the project's conventions without
guessing.

Targets M3 retro R7 (unimplemented in 0.3.1) and PV2 'reinvented MCP
bootstrap' failure mode.

Spec: docs/superpowers/specs/2026-05-09-skill-chain-wiring-design.md §5 P2-7"
```

---

## Task 9 (P2-8): using-prd2impl tombstone gate

**Files:**
- Modify: `skills/using-prd2impl/SKILL.md` — add tombstone gate section.
- Modify: `skills/skill-7-next-task/SKILL.md` — explicit skip for tombstoned tasks.
- Modify: `skills/skill-3-task-gen/templates/tasks.yaml` — example tombstone.

- [ ] **Step 9.1: Add tombstone gate to using-prd2impl router**

Find a sensible location in `using-prd2impl/SKILL.md` (after the routing
table); append:

```markdown
## Tombstone gate

Some user stories / epics get descoped during a milestone (typical
reasons: out-of-scope per source PRD revision, deferred for capacity,
moved to a later milestone). The router refuses to dispatch against
these.

### Detection

On any prd2impl command invocation, glob `{plans_dir}/*.yaml` for
entries matching ANY of:
- `status: DEFERRED_*` (e.g. `DEFERRED_M4`)
- `tombstone: true`
- A leading YAML comment `# TOMBSTONE: <reason>`

### Behavior

- `/next-task` ranking skips tombstoned candidates entirely.
- `/start-task <id>` on a tombstoned task returns:
  ```
  REFUSED — task is tombstoned
  Status: DEFERRED_M4 (since 2026-04-22)
  Source: plans/m3/tasks.yaml#L412
  Reason: Out-of-scope per v1.1 §8 (whitelabel not in scope)
  To revive: update task status and re-run /task-gen.
  ```
- `/batch-dispatch` excludes tombstoned tasks from any batch.
- `/task-status` lists tombstones in a separate "Deferred" section,
  not in the active task table.

### Rationale

AutoService project memory has explicit DEFERRED entries
(`project_m3_epic_e2_descoped.md`, `project_m3_4_deferred_to_m3_5.md`)
that current router ignores. PV2 milestone setup almost re-pulled
descoped E2 stories before maintainer caught it manually. This gate
makes the discipline mechanical.
```

- [ ] **Step 9.2: Update skill-7-next-task to honor tombstones**

In skill-7-next-task/SKILL.md, find candidate ranking step; add early
filter:

```markdown
### Step 1.x: Skip tombstoned candidates

Before any dependency / priority ranking, drop candidates matching
the tombstone detection rules in `using-prd2impl §Tombstone gate`.
If after filtering the candidate set is empty, return:

> "No active candidates. N tasks are tombstoned (deferred to future
> milestones); run `/task-status` for details."
```

- [ ] **Step 9.3: Add tombstone example to template**

Append to `skills/skill-3-task-gen/templates/tasks.yaml`:

```yaml
# Example tombstoned task — router refuses to dispatch
- id: E2.1
  name: "Subtenant onboarding flow"
  type: yellow
  status: DEFERRED_M4
  tombstone: true
  # TOMBSTONE: Out-of-scope per v1.1 §8 errata (whitelabel not in scope).
  #            Original M3 spec line 412. To revive, update PRD and
  #            re-run /prd-analyze + /task-gen.
  depends_on: []
  affects_files: []
  deliverables: []
```

- [ ] **Step 9.4: Commit Task 9**

```bash
git add skills/using-prd2impl/SKILL.md skills/skill-7-next-task/SKILL.md skills/skill-3-task-gen/templates/tasks.yaml
git commit -m "feat(using-prd2impl,skill-7): tombstone gate for deferred/descoped tasks

Router and skill-7-next-task now refuse to dispatch any task with
status: DEFERRED_*, tombstone: true, or a leading TOMBSTONE comment.
Listed separately in /task-status as 'Deferred' section.

Targets the AutoService project memory pattern (project_m3_epic_e2_descoped.md
et al) where descoped epics could be silently re-pulled into a new
milestone's planning.

Spec: docs/superpowers/specs/2026-05-09-skill-chain-wiring-design.md §5 P2-8"
```

---

## Task 10 (P2-9): references/mock-policy.md

**Files:**
- Create: `references/mock-policy.md` at plugin root.
- Modify: `skills/skill-3-task-gen/SKILL.md` — task context block references the policy.
- Modify: `skills/skill-5-start-task/SKILL.md` — Yellow tasks must read mock-policy.
- Modify: `skills/skill-6-continue-task/SKILL.md` — test-code phase references the policy.
- Modify: `README.md` — link the new reference.

- [ ] **Step 10.1: Create references directory and mock-policy.md**

```bash
mkdir -p D:/Work/h2os.cloud/prd2impl/references
```

Write `references/mock-policy.md`:

```markdown
# prd2impl Mock Policy

This reference is consumed by skill-3-task-gen, skill-5-start-task,
skill-6-continue-task. It defines what counts as a correct test under
the prd2impl pipeline. Without an explicit policy, subagents ship
`MagicMock()` calling methods that don't exist on real classes (the
cdcfdb2 bug class).

## What MAY be mocked

1. **External SaaS / network boundaries** — Anthropic API, Doubao,
   third-party REST/gRPC services. Stub at the HTTP layer, not at the
   client wrapper class.
2. **Subprocess / CLI invocations** — `claude` CLI, `git`, `pytest`
   when test is meta-testing the pipeline itself.
3. **Clock / time** — `datetime.utcnow`, `time.time` for deterministic
   tests. Use `freezegun` or `monkeypatch.setattr`.
4. **Filesystem at platform boundary** — disk I/O for path-format
   tests where the actual content doesn't matter.

## What MUST NOT be mocked

1. **The system under test (SUT) itself** — if a test mocks the class
   it claims to test, the test proves nothing.
2. **Modules in the same Python package as the test** — internal
   collaborators should be real instances. Use dependency injection
   or fixtures to construct them, not mocks.
3. **Database** — prefer an ephemeral real instance (sqlite for tests,
   testcontainers, etc.) over an in-memory mock that diverges from
   real driver behavior.
4. **The contract under negotiation** — a Yellow task whose contract
   is `Module.Class.method(...)` must not test by mocking
   `Module.Class`. Test by AST-walking the consumer code (see
   contract test pattern below) and asserting it resolves on the
   real class.

## How to mock safely

1. **`spec=Class` is mandatory** when using `MagicMock` or `Mock` for
   any production class. Bare `MagicMock()` lets you call any method,
   including ones that don't exist (the cdcfdb2 enabler).

   ```python
   # WRONG — bare MagicMock
   pool = MagicMock()
   pool.acquire_for_session(...)  # silently returns another MagicMock

   # RIGHT — spec'd
   from autoservice.cc_pool import CCPool
   pool = MagicMock(spec=CCPool)
   pool.acquire_for_session(...)  # AttributeError immediately
   ```

2. **`autospec=True`** for `patch()` decorators on methods of
   production classes. Catches signature mismatches at test time.

3. **Hand-rolled `_FakeX`** classes are acceptable when `MagicMock`
   semantics don't fit, but MUST be paired with a contract test:
   - The fake class declares the same method names as the real class.
   - A contract test AST-walks both and asserts method names + signatures
     match. See template at
     `skills/skill-12-contract-check/references/ast-walk-template.md`.
   - Drift in either side fails the contract test before it ships.

## Contract test pattern

For every fake-class boundary in `tests/<production-namespace>/`,
ship a paired contract test. Template:

```python
"""Contract test — verifies _FakePool tracks the real CCPool API.
Auto-generated; regenerate via /contract-check --preflight.
"""
import inspect
from autoservice.cc_pool import CCPool
from tests.pipeline_v2.test_runner import _FakePool

def test_fake_pool_methods_match_real():
    real_methods = {n for n in dir(CCPool) if not n.startswith('_')}
    fake_methods = {n for n in dir(_FakePool) if not n.startswith('_')}
    extras = fake_methods - real_methods
    missing = real_methods - fake_methods
    # Fake having extra methods is the cdcfdb2 anti-pattern.
    assert not extras, f"_FakePool defines methods not on real CCPool: {extras}"

def test_fake_pool_signatures_match_real():
    for name in dir(_FakePool):
        if name.startswith('_'): continue
        if not callable(getattr(_FakePool, name)): continue
        if not hasattr(CCPool, name): continue
        fake_sig = inspect.signature(getattr(_FakePool, name))
        real_sig = inspect.signature(getattr(CCPool, name))
        # Allow fake to accept **kwargs as drift catcher; otherwise must match.
        assert (
            fake_sig.parameters.keys() == real_sig.parameters.keys()
            or any(p.kind == p.VAR_KEYWORD for p in fake_sig.parameters.values())
        ), f"_FakePool.{name} signature differs from real: {fake_sig} vs {real_sig}"
```

## Project-specific overrides

Projects with genuinely different testing constraints (e.g. extensive
external-SaaS reliance) can override this policy by writing
`{plans_dir}/mock-policy.local.md` extending or relaxing rules.
skill-3-task-gen reads the local override if present.

## Why this exists

Audit of AutoService PV2 milestone (commit cdcfdb2 et al, May 2026)
found 229 instances of unspec'd `MagicMock()` / `AsyncMock()` across
33 test files. Three contract tests existed in the entire codebase.
A method that did not exist on the real class shipped to production
for 14 days because the test fake mirrored the fictional API. This
policy + contract test pattern + skill-12 preflight close the gap.
```

- [ ] **Step 10.2: Reference mock-policy from skill-3 task context**

In skill-3 Step 4 (already touched in Task 8), add:

```markdown
Inline `references/mock-policy.md` rules into every task's
`context_block` for tasks that produce test deliverables. Subagents
in skill-8 see the policy in their dispatch prompt.
```

- [ ] **Step 10.3: Reference from skill-5 Yellow path**

In skill-5 Yellow context-load step (already extended in Task 3 with
preflight); add:

```markdown
- Read `references/mock-policy.md` before writing tests. Bare
  `MagicMock()` without `spec=` is forbidden in
  `tests/<production-namespace>/`. Hand-rolled fakes require a paired
  contract test per the policy.
```

- [ ] **Step 10.4: Reference from skill-6 test-code phase**

In skill-6 test-code phase, append a similar reference.

- [ ] **Step 10.5: Update README**

Add a line to `README.md` under "Companion plugins" or in a new
"References" section:

```markdown
### References

- [`references/mock-policy.md`](references/mock-policy.md) — Mock
  policy consumed by task-gen and start-task. Defines what may /
  must-not be mocked, with contract test patterns.
```

- [ ] **Step 10.6: Commit Task 10**

```bash
git add references/mock-policy.md README.md skills/skill-3-task-gen/SKILL.md skills/skill-5-start-task/SKILL.md skills/skill-6-continue-task/SKILL.md
git commit -m "feat: references/mock-policy.md + skill wiring (P2-9)

New plugin-root reference doc defining what may / must-not be mocked,
with safe-mock patterns (spec= mandatory) and the contract test
template that catches the cdcfdb2 bug class. Consumed by skill-3
(task context), skill-5 (Yellow context-load), skill-6 (test-code).

Closes the 'no explicit mock policy' architectural void identified
in AutoService PV2 audit.

Spec: docs/superpowers/specs/2026-05-09-skill-chain-wiring-design.md §5 P2-9"
```

---

## Task 11 (P2-10): skill-10 Layer-3 drift gate

**Files:**
- Modify: `skills/skill-10-smoke-test/SKILL.md` — add Step 0 drift gate.

- [ ] **Step 11.1: Add Step 0 to skill-10**

Insert at the top of skill-10's procedural section, before any other
step:

```markdown
### Step 0: Layer-3 drift gate (when dev-loop installed)

dev-loop:skill-0-project-builder maintains a `baseline_commit`
frontmatter on the project's "Skill 1" knowledge file plus a
`self-update.sh --check` script returning drift count (new top-level
modules, renamed dirs, etc.). Before running smoke-test, check it.

```
/project-builder self-update --check
```

If returned `drift_count > 50` (configurable) → emit a STAGED warning
prompting user to run `/bootstrap` re-baseline before gate close.
This is a warning, not a hard NO-GO — drift can be intentional.

**When dev-loop missing**: skip with a logged warning, gate proceeds.

Rationale: PV2 shipped `pipeline_v2/kb_mcp/` because the planning step
didn't know `cc_pool.py:691` already auto-injects an MCP server.
A re-baseline would have surfaced the duplication earlier.
```

- [ ] **Step 11.2: Commit Task 11**

```bash
git add skills/skill-10-smoke-test/SKILL.md
git commit -m "feat(skill-10): Step 0 Layer-3 drift gate via dev-loop:skill-0-project-builder

Smoke-test now runs project-builder self-update --check before any
test verification. Drift > 50 emits STAGED warning (not auto NO-GO).
Stale module maps cannot silently pass milestone gates.

Targets PV2 kb_mcp/ duplicate-of-cc_pool failure mode.

Spec: docs/superpowers/specs/2026-05-09-skill-chain-wiring-design.md §5 P2-10"
```

---

## Task 12: Version bump + CHANGELOG

**Files:**
- Modify: `package.json` — version 0.3.1 → 0.4.0
- Modify: `.claude-plugin/plugin.json` — same.
- Create: `CHANGELOG.md` (or update if exists) — 0.4.0 release notes.

- [ ] **Step 12.1: Bump versions**

```bash
sed -i 's/"version": "0.3.1"/"version": "0.4.0"/' D:/Work/h2os.cloud/prd2impl/package.json
sed -i 's/"version": "0.3.1"/"version": "0.4.0"/' D:/Work/h2os.cloud/prd2impl/.claude-plugin/plugin.json
```

(If `sed -i` is fragile on Windows bash, use Edit tool.)

- [ ] **Step 12.2: Verify version bumped**

```bash
grep '"version"' D:/Work/h2os.cloud/prd2impl/package.json D:/Work/h2os.cloud/prd2impl/.claude-plugin/plugin.json
```
Expected: both show `"version": "0.4.0"`.

- [ ] **Step 12.3: Add CHANGELOG entry**

Check if `CHANGELOG.md` exists:
```bash
ls D:/Work/h2os.cloud/prd2impl/CHANGELOG.md 2>&1
```

If it doesn't exist, create with 0.4.0 entry. If it exists, prepend:

```markdown
## 0.4.0 — 2026-05-09

Skill-chain wiring + framework-learning loop. Connects prd2impl's
declared `superpowers` and `dev-loop-skills` capabilities to actual
invocation paths. Closes architectural voids identified in
AutoService PV2 milestone audit (see
`docs/superpowers/specs/2026-05-09-skill-chain-wiring-design.md`).

### Added
- skill-12 AST-based contract snapshot + signature_drift block
- skill-12 `/contract-check --preflight {task_id}` subcommand
- skill-5 Step 4.5 Yellow / must_call_unchanged preflight gate
- skill-11 Step 6 framework-learning loop via superpowers:writing-skills
- skill-3 schema fields: must_call_unchanged, env_var, reload_kind, auto_promoted
- skill-3 auto color-promotion (Green → Yellow on auth/permission/contract/seam)
- skill-13 two-stage Yellow review (spec-compliance then code-quality)
- skill-2 Step 3.5 house-conventions extraction → conventions.md
- using-prd2impl tombstone gate
- references/mock-policy.md
- skill-10 Step 0 Layer-3 drift gate
- skill-12 references/ast-walk-template.md
- skill-11 templates/framework-patch.md

### Changed
- skill-10 Step 3 routes through dev-loop:skill-4-test-runner (raw pytest
  retained as fallback)
- skill-9, skill-11, skill-12 read artifacts via dev-loop:skill-6-artifact-registry
  (direct file read retained as fallback)

### Backward compatibility
All changes are additive. tasks.yaml schema additions are optional
fields. Existing tasks continue to validate. When companions are
absent, behavior matches 0.3.1 with logged warnings.
```

- [ ] **Step 12.4: Commit**

```bash
git add package.json .claude-plugin/plugin.json CHANGELOG.md
git commit -m "chore(release): 0.4.0 — skill-chain wiring + framework-learning loop"
```

---

## Task 13: Push + PR

- [ ] **Step 13.1: Push feature branch**

```bash
git -C D:/Work/h2os.cloud/prd2impl push -u origin feat/skill-chain-wiring
```

- [ ] **Step 13.2: Create PR**

```bash
gh pr create --repo ezagent42/prd2impl --base main --head feat/skill-chain-wiring \
  --title "feat: 0.4.0 — skill-chain wiring + framework-learning loop" \
  --body "$(cat <<'EOF'
## Summary

Connects prd2impl's declared `superpowers` and `dev-loop-skills` capabilities to actual invocation paths. Audit of AutoService PV2 milestone (May 2026) showed 12+ "should-exist" cross-skill edges were advisory at best or completely missing. This PR ships ten additive changes that close the wiring, all backward compatible.

## What's in the box

**P0 (highest ROI):**
- skill-10 routes smoke-test through `dev-loop:skill-4-test-runner` for new-vs-regression classification at gate time
- skill-12 AST-based contract snapshot + `/contract-check --preflight` invoked from skill-5 Yellow tasks (closes the cdcfdb2 bug class — non-existent methods called on real classes)
- skill-11 framework-learning loop via `superpowers:writing-skills` (turns retros from dead-end reports into actual skill patches)

**P1:**
- skill-3 schema additions (`must_call_unchanged`, `env_var.class`, `reload_kind`, `auto_promoted`) + auto Green→Yellow promotion on auth/permission/contract/seam
- skill-9/11/12 route artifact reads via `dev-loop:skill-6-artifact-registry`
- skill-13 two-stage Yellow review (spec-compliance, then code-quality) per `superpowers:subagent-driven-development`

**P2:**
- skill-2 conventions extraction → `conventions.md` inlined into every task's context
- using-prd2impl tombstone gate (refuses dispatch of DEFERRED tasks)
- `references/mock-policy.md` — explicit mock policy with contract test pattern
- skill-10 Step 0 Layer-3 drift gate via `dev-loop:skill-0-project-builder`

## Backward compatibility

All changes additive. tasks.yaml schema additions are optional. When companions absent, behavior matches 0.3.1 with logged warnings. Detailed compatibility table in design spec §6.

## Spec & plan

- Design: `docs/superpowers/specs/2026-05-09-skill-chain-wiring-design.md`
- Plan: `docs/superpowers/plans/2026-05-09-skill-chain-wiring.md`

## Test plan

- [ ] Local install via `/plugin install /path/to/prd2impl`
- [ ] Run `/contract-check --preflight` on the AutoService PV2 cdcfdb2 fixture; expect unresolved `acquire_for_session`
- [ ] Run `/retro` on a milestone with reviewer-missed-signature failure; expect framework-patch targeting skill-13
- [ ] Run `/smoke-test` with dev-loop installed; verify e2e-report consumed; verify regression failure → NO-GO
- [ ] Verify graceful degradation: uninstall dev-loop, re-run `/smoke-test`; expect logged warning + raw pytest fallback
EOF
)"
```

- [ ] **Step 13.3: Capture PR URL**

```bash
gh pr view --repo ezagent42/prd2impl feat/skill-chain-wiring --json url --jq .url
```

Report URL to user.

---

## Self-review checklist

Run through this AFTER all tasks ship to a feature branch but BEFORE PR push:

**1. Spec coverage:** Each P0/P1/P2 in design spec §5 has a corresponding Task 1–11 above. ✓

**2. Placeholder scan:** No "TBD", "TODO", "implement later", "fill in details" in any task body. Code blocks contain real markdown / YAML / Python.

**3. Type consistency:** Every reference to `must_call_unchanged`, `env_var`, `reload_kind`, `auto_promoted` matches the schema field names declared in Task 5. Every `--preflight` invocation uses the same `{task_id}` parameter declared in Task 3. Every `framework-patch.md` reference matches Task 4's template path.

**4. Cross-task wiring:** Task 3 (skill-12 preflight) depends on Task 2 (AST upgrade). Task 5 (must_call_unchanged schema) precedes any task using the field. Tasks 8 (conventions) and 10 (mock-policy) are both referenced from skill-3 Step 4 (Task 5) — no conflict, both append.

**5. Commit graph:** 11 commits per change + 1 release commit = 12 commits. PR body summarizes them. PR uses `--base main`, `--head feat/skill-chain-wiring`.

If self-review reveals issues, fix in-place and proceed.
