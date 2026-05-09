---
name: contract-check
description: "Contract drift detection — analyze changes in contract/interface files and assess impact on dependent tasks. Use when the user says 'check contracts', 'contract drift', 'schema changed', 'interface changed', or runs /contract-check."
---

# Skill 12: Contract Check

<SUBAGENT-STOP>
If you were dispatched as a subagent to execute a specific task, skip this skill.
</SUBAGENT-STOP>

Detect changes in contract/interface files and analyze their impact on dependent tasks and code.

## Trigger

- User runs `/contract-check`
- User says "check contracts", "contract drift", "schema changed"
- User reports "I changed the interface and want to know the impact"
- After discovering a test failure that might be contract-related

## Input

- **Optional**: Specific contract file path
- **Data sources**:
  1. `docs/contracts/` directory (contract definitions)
  2. Git diff (to detect changes)
  3. `{plans_dir}/tasks.yaml` (to find affected tasks)
  4. Codebase (to find consumers of the contract)

## Execution Flow

> **Path resolution**: Before constructing any read/write path, resolve `{plans_dir}` per `lib/plans-dir-resolver.md`. All `docs/plans/` references (except `docs/plans/project.yaml`, which stays at repo root) are relative to that resolved directory. Bare references to `tasks.yaml`, `task-status.md`, etc. are also `{plans_dir}`-scoped.

### Step 1: Identify Contract Files

1. Scan `docs/contracts/` for contract definitions
2. Also check for interface files:
   - Python Protocol/ABC classes
   - TypeScript interface/type definitions
   - API schema files (OpenAPI, JSON Schema)
   - WebSocket message schemas
3. If user specified a file, focus on that one

### Step 2: Build signature dictionary via AST

For each contract-side file from Step 1, parse its AST to enumerate
`{Module.Class.method: Signature}`. This replaces the 0.3.x diff-text
parser, which could only see what changed in this run, not the
absolute current state of the contract.

```python
import ast

def enumerate_contract(path):
    """Returns {qualified_name: signature_dict} for every public method in path."""
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

Store the resulting dict as the **canonical contract snapshot** for
this run. This snapshot answers "does this method exist on the real
class right now" rather than "did this method appear in the git
diff".

For TypeScript / JS contracts, use a parallel `tree-sitter-typescript`
walk; if unavailable, fall back to the 0.3.x grep-based extraction
with a logged warning.

**Also keep the diff view for change-summary output** (still useful in
the report):
```bash
git diff {last_milestone_tag}..HEAD -- docs/contracts/ \
  "*.proto" "*.schema.json" "*protocol*.py" "*interface*.ts"
```
Diff is consumed for the human-readable `diff_summary:` block, but
gating decisions use the AST snapshot.

```yaml
changes:
  - file: "docs/contracts/conversation-engine.md"
    type: contract
    diff_summary:
      added_methods: ["async handle_timeout(session_id)"]
      removed_methods: []
      changed_signatures: ["start_session: added 'metadata' param"]
      added_fields: ["Session.metadata: dict"]
    severity: medium  # breaking | medium | minor
    contract_snapshot_qualifies: 14  # methods enumerated by AST
    
  - file: "docs/contracts/frontend-ws-schema.md"
    type: schema
    diff_summary:
      added_events: ["session.timeout"]
      removed_events: []
      changed_events: ["message.new: added 'sentiment' field"]
    severity: minor
```

### Step 2.5: Detect signature drift in consumer code

For each consumer file found in Step 3, AST-walk it and find every
`Call` node whose callee resolves (via local symbol table) to a
tracked method:

```python
def find_calls(consumer_path, contract_snapshot):
    """Yield (lineno, qualified_name, actual_signature) for every tracked call."""
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
    """Return list of mismatches between actual call and definition."""
    drifts = []
    if (actual['positional_count'] > len(definition['positional'])
            and not definition['has_varargs']):
        drifts.append(
            f"too many positional args: {actual['positional_count']} > "
            f"{len(definition['positional'])}"
        )
    for kw in actual['keyword_names']:
        if (kw not in definition['positional']
                and kw not in definition['keyword_only']
                and not definition['has_varkw']):
            drifts.append(f"unknown keyword: {kw}")
    # The T4M.3 pattern: keyword-only arg passed positionally
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

This catches drift that already shipped — independent of git diff —
the cdcfdb2 bug class. See `references/ast-walk-template.md` for a
reusable contract-test template.

### Step 3: Impact Analysis

For each change, find affected code:

1. **Grep for consumers**: Search for imports/usage of changed interfaces
2. **Check task dependencies**: Which tasks reference these contracts?
3. **Check test coverage**: Are there tests for the changed interfaces?

```yaml
impact:
  - change: "start_session: added 'metadata' param"
    affected_files:
      - path: "autoservice/conversation_engine/local_engine.py"
        line: 87
        usage: "def start_session(self, customer_id)"
        action_needed: "Add metadata parameter"
      - path: "tests/contract/test_engine.py"
        line: 23
        usage: "engine.start_session('cust-1')"
        action_needed: "Update test call"
    affected_tasks:
      - id: T1A.1
        status: completed
        needs_update: true
    breaking: false  # New optional param with default
    
  - change: "Session.metadata: dict (new field)"
    affected_files:
      - path: "channels/web/websocket.py"
        line: 145
        usage: "session = Session(id=..., customer=...)"
        action_needed: "Add metadata field"
    affected_tasks:
      - id: T0.5
        status: completed
        needs_update: true
    breaking: false
```

### Step 4: Risk Assessment

```yaml
risk:
  total_changes: 4
  breaking_changes: 0
  affected_files: 8
  affected_tasks: 3 (all completed — need update)
  test_coverage:
    covered: 6/8 files have tests
    uncovered: 
      - "channels/web/websocket.py"
      - "autoservice/plugins/lifecycle_plugin.py"
  
  overall_risk: medium
  recommendation: "Non-breaking changes. Update 8 files and re-run tests."
```

### Step 5: Generate Report

```markdown
# Contract Check Report — {date}

## Changes Detected
| File | Changes | Severity |
|------|---------|----------|
| conversation-engine.md | +1 method, 1 signature change, +1 field | Medium |
| frontend-ws-schema.md | +1 event, 1 event change | Minor |

## Impact Summary
- **Files to update**: 8
- **Tasks to revisit**: 3 (T0.5, T1A.1, T1A.3)
- **Breaking changes**: 0 (all additive)
- **Test coverage**: 75% (2 files uncovered)

## Required Actions
1. `local_engine.py:87` — Add `metadata` param to `start_session`
2. `websocket.py:145` — Add `metadata` field to Session construction
3. `test_engine.py:23` — Update test call signature
... (full list)

## Recommended Workflow
1. Create branch: `contract/add-metadata`
2. Apply changes to the 8 affected files
3. Run contract test suite: `pytest tests/contract/`
4. Send review prompt to other developer line:
   
   > Contract change: `start_session` now accepts optional `metadata` param,
   > `Session` has new `metadata: dict` field, new `session.timeout` WS event.
   > All additive, non-breaking. PR: #{branch_url}
   
5. After review → merge to dev
```

### Step 6: Auto-Fix Option

If changes are straightforward (additive, non-breaking):
```
The changes are non-breaking. Want me to auto-apply fixes?
This will:
- Update 8 files to match new contract
- Re-run contract tests
- Create a commit with all changes

Proceed? (y/n)
```

If yes, apply fixes and run tests. If tests pass, commit.

## When to Run

- **Proactively**: Before starting a new milestone (check for accumulated drift)
- **Reactively**: When a test fails with "unexpected argument" or "missing field" errors
- **On contract change**: After any edit to `docs/contracts/` files
- **Cross-line sync**: When the other developer reports a contract change
- **Pre-flight per task**: Automatically invoked from `skill-5-start-task` Step 4.5 for every Yellow task and any task with `must_call_unchanged`. See `--preflight` subcommand below.

## Preflight subcommand: `/contract-check --preflight {task_id}`

Invoked BEFORE writing code, by `skill-5-start-task` Step 4.5 for any
task that satisfies one of:
- `type: yellow` (always)
- `must_call_unchanged: [...]` is non-empty
- `affects_files` glob matches `**/*contract*` / `**/*protocol*`
- `meta.connector_seam: true`

### Inputs
- `{task_id}` — looked up in `{plans_dir}/tasks.yaml`

### Behavior

1. Load the task definition from `{plans_dir}/tasks.yaml`. Extract
   `must_call_unchanged` (preferred) or, if absent, compute the
   external symbol set by AST-walking each file in `affects_files`
   for cross-module imports.

2. For each `Module.Class.method` symbol in the set:
   - Resolve via `ast.parse` against the file at HEAD (per Step 2's
     contract snapshot logic).
   - If unresolvable → emit `unresolved_symbols: [...]` with the list
     of methods actually present on the target class.
   - If resolvable but signature differs from what the task spec
     implies → emit `signature_concerns: [...]`.

3. Output: short YAML report at
   `{plans_dir}/preflight/{task_id}.yaml`.

4. Exit code: `0` if clean (no unresolved or concerning entries),
   `1` if any entries.

### Example output (PV2 cdcfdb2 fixture)

```yaml
task_id: T4M.3
generated_at: 2026-05-09T14:00:00Z
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

When `--preflight` returns non-zero, `skill-5-start-task` halts the
task with the report content displayed to the user. The user resolves
by either updating the task spec or correcting the underlying
assumption.

### Why this exists

Without preflight, the cdcfdb2 bug class (subagent invents a method
name; fake test double mirrors the invention; CI green; production
AttributeError) ships routinely. AutoService PV2 paid this cost for
~14 days on a single fix. See
`references/ast-walk-template.md` for the contract-test pattern that
preflight auto-suggests when no contract test covers the consumer
yet.
