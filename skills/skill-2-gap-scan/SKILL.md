---
name: gap-scan
description: "Codebase vs PRD gap analysis — scan existing code against structured PRD requirements to identify what's implemented, partial, or missing. Use when the user says 'gap scan', 'what's missing', 'scan codebase', or after /prd-analyze."
---

# Skill 2: Gap Scan

<SUBAGENT-STOP>
If you were dispatched as a subagent to execute a specific task, skip this skill.
</SUBAGENT-STOP>

Automatically scan the existing codebase against PRD requirements to identify implementation gaps. This is the second step of the prd2impl pipeline.

## Trigger

- User runs `/gap-scan`
- User says "what gaps exist", "what's missing", "scan codebase against PRD"
- After `/prd-analyze` has produced `prd-structure.yaml`

## Input

- **Required**: `{plans_dir}/*-prd-structure.yaml` (output from skill-1)
- **Optional**: Existing codebase in the working directory

If `prd-structure.yaml` doesn't exist, prompt the user to run `/prd-analyze` first.

## Execution Flow

> **Path resolution**: Before constructing any output path, resolve `{plans_dir}` per `lib/plans-dir-resolver.md`. All `docs/plans/` references below (except `docs/plans/project.yaml`, which stays at repo root) are relative to that resolved directory.

### Step 1: Load PRD Structure

1. Find the most recent `{plans_dir}/*-prd-structure.yaml`
2. Parse modules, user stories, NFRs, constraints
3. Build a checklist of all items to verify

### Step 2: Scan Codebase Per Module

For each module in the PRD structure:

1. **File Discovery**: Use Glob to find files matching the module's expected location
   - Check directory names, file names, class names matching module keywords
   - Check import statements referencing the module
   
2. **Feature Coverage**: For each user story in the module:
   - Use Grep to search for keywords from the story's action and acceptance criteria
   - Check for relevant test files
   - Check for relevant API endpoints (routes, handlers)
   - Check for relevant UI components (if frontend)

3. **Classify Coverage**:
   ```yaml
   coverage:
     - story_id: US-001
       status: implemented  # implemented | partial | missing
       evidence:
         - file: "autoservice/conversation_engine.py"
           line: 42
           match: "class ConversationEngine"
         - file: "tests/test_engine.py"
           line: 10
           match: "def test_conversation_flow"
       missing_criteria:
         - "AC-003: Sentiment display not found"
       confidence: high  # high | medium | low
   ```

4. **NFR Check**: For each NFR:
   - Search for performance tests, security configs, scaling configurations
   - Check for monitoring/alerting setup
   - Note: NFRs are harder to verify by code scan alone — flag uncertain items

### Step 3: Analyze Dependencies

1. Check external dependencies status:
   - Are SDK/client libraries installed? (check package.json, requirements.txt, pyproject.toml)
   - Are API credentials configured? (check .env.example, config files)
   - Are integration tests present?

2. Check internal module dependencies:
   - Verify import paths exist
   - Check for interface/contract files between modules

### Step 3.5: House-conventions extraction (0.4.0+)

Subagents writing new code should follow project-wide patterns
rather than reinventing them. Extract recurring patterns into a
cheat-sheet that skill-3-task-gen inlines into every task's context
block. Without this step, subagents in skill-8 dispatch produce
code that re-invents what's already in the project — see AutoService
PV2 `pipeline_v2/kb_mcp/` (commit `f82c22e` deleted it as duplicate
of `cc_pool.py:691`).

**Patterns to grep**:

1. **Timestamp format** — `datetime.utcnow()` vs `time.time()` vs
   ISO string. Capture the dominant pattern + 2 example file:line.
2. **ID generation** — `uuid.uuid4()`, `secrets.token_urlsafe(N)`,
   custom prefix scheme. Capture pattern + N + example.
3. **Error types** — project-defined exception classes, common
   inheritance (e.g. `class FooError(BaseError)`). List top 5 by
   reference count.
4. **Test fixture singletons** — `_reset_*_db_for_tests` patterns,
   `conftest.py` scope conventions.
5. **Logging** — logger name pattern (`logger = logging.getLogger(__name__)`),
   structured log helper if any.
6. **HTTP / RPC client setup** — bare `httpx.Client()` vs project-
   scoped wrapper; auth header injection convention.
7. **MCP server registration** — for projects using MCP, look for
   existing auto-injection points (e.g. AutoService's
   `cc_pool.py:691`-style `build_kb_mcp_server`). New MCP tasks
   should reuse, not duplicate.

**Output**: write to `{plans_dir}/conventions.md`:

```markdown
# Project conventions (extracted by skill-2-gap-scan)

Generated: 2026-05-09
Inputs scanned: autoservice/, channels/, plugins/

## Timestamps
- Format: ISO 8601 strings (`datetime.utcnow().isoformat()`)
- Source: autoservice/customer_manager.py:42, autoservice/crm.py:118
- Avoid: epoch ints, naive datetimes

## ID generation
- Pattern: `secrets.token_urlsafe(36)`
- Source: autoservice/customer_manager.py:42

## Error types
- Base: `AutoServiceError` (autoservice/errors.py:5)
- Top inheritors: TenantError, ChannelError, ContractError

## MCP server registration
- Pattern: per-tenant auto-inject via `cc_pool.py:691` `build_kb_mcp_server(tenant_id) -> MCPServer`
- Reuse rule: any new MCP need should hook into this auto-inject path,
  NOT duplicate the bootstrap. (PV2 kb_mcp/ duplicate-of-cc_pool
  failure mode.)

(... continued for each pattern ...)
```

This file becomes a stable input to skill-3-task-gen Step 4 (which
reads it and inlines relevant entries into each task's context block).

### Step 4: Generate Gap Report

Produce structured output:

```yaml
gap_analysis:
  scan_date: "2026-04-17"
  prd_source: "{plans_dir}/2026-04-17-prd-structure.yaml"
  
  summary:
    total_stories: 45
    implemented: 28
    partial: 10
    missing: 7
    coverage_pct: 62
    
  by_module:
    - module: MOD-01
      stories_total: 12
      implemented: 8
      partial: 3
      missing: 1
      coverage_pct: 67
      
  gaps:
    - id: GAP-001
      story_id: US-015
      module: MOD-03
      description: "Billing module not yet implemented"
      gap_type: missing  # missing | partial | outdated
      missing_parts:
        - "Tiered pricing calculation"
        - "Invoice generation"
        - "Payment gateway integration"
      estimated_effort: medium  # small | medium | large
      depends_on_gaps: []  # Other gaps this depends on
      
    - id: GAP-002
      story_id: US-008
      module: MOD-02
      description: "SLA monitoring partially implemented — alerting missing"
      gap_type: partial
      existing_code:
        - "autoservice/sla_aggregator.py"
      missing_parts:
        - "Alert dispatch to Feishu/Slack"
        - "Escalation rules engine"
      estimated_effort: small
      
  nfr_gaps:
    - nfr_id: NFR-03
      status: unknown
      note: "No performance tests found for API latency requirement"
      
  dependency_gaps:
    - dep_id: DEP-02
      status: missing
      note: "Payment gateway SDK not installed"
```

### Step 5: Output

1. Write to `{plans_dir}/{date}-gap-analysis.yaml`
2. Print summary to terminal:

```
Gap Analysis Complete
=====================
Coverage: 62% (28/45 stories implemented)

By Module:
  MOD-01 Conversation Engine  ████████░░ 67% (8/12)
  MOD-02 SLA Monitoring       ██████░░░░ 60% (6/10)
  MOD-03 Billing              ░░░░░░░░░░  0% (0/8)
  ...

Gaps Found: 17
  Missing:  7 (need full implementation)
  Partial: 10 (need completion)

NFR Gaps: 3 items need verification
Dependency Gaps: 1 missing SDK
```

### Step 6: Human Review Checkpoint

**STOP here.** Present the gap report and wait for user review.

> Gap analysis complete. {N}% coverage, {M} gaps identified.
>
> Review `{plans_dir}/{date}-gap-analysis.yaml` and confirm:
> 1. Are there implemented features I missed? (false negatives)
> 2. Are there gaps that should be descoped? (won't implement)
> 3. Any gaps that are actually blocked on external dependencies?
>
> When ready, run `/task-gen` to generate tasks from these gaps.

## Scanning Strategy

- **Breadth-first**: Scan all modules at surface level first, then deep-dive into uncertain areas
- **Keyword-based**: Use module names, story keywords, and acceptance criteria as search terms
- **Convention-aware**: Check the project's CLAUDE.md for directory conventions and naming patterns
- **Test-aware**: Finding a test for a feature is strong evidence of implementation
- **Import-aware**: Check import graphs to verify module integration

## Limitations

- Cannot verify runtime behavior (only static code analysis)
- NFR coverage is inherently low-confidence
- UI/UX requirements need manual browser verification
- External API integration status may require runtime checks
