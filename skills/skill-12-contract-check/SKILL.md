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

### Step 2: Detect Changes

**Check git diff** for recent changes:
```bash
# Changes in contract files since last tag/milestone
git diff {last_milestone_tag}..HEAD -- docs/contracts/ 

# Changes in interface files
git diff {last_milestone_tag}..HEAD -- "*.proto" "*.schema.json" "*protocol*.py" "*interface*.ts"
```

**Parse changes**:
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
    
  - file: "docs/contracts/frontend-ws-schema.md"
    type: schema
    diff_summary:
      added_events: ["session.timeout"]
      removed_events: []
      changed_events: ["message.new: added 'sentiment' field"]
    severity: minor
```

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
