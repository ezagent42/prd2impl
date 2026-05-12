---
name: prd-analyze
description: "Structured PRD extraction — parse a Product Requirements Document into modules, user stories, NFRs, and constraints. Use when starting a new project from a PRD, or when the user says 'analyze PRD', 'parse requirements', 'read the PRD'."
---

# Skill 1: PRD Analyze

<SUBAGENT-STOP>
If you were dispatched as a subagent to execute a specific task, skip this skill.
</SUBAGENT-STOP>

Parse a Product Requirements Document (PRD) into structured, machine-queryable YAML. This is the first step of the prd2impl pipeline.

## Trigger

- User provides a PRD file path: `/prd-analyze docs/prd/my-prd.md`
- User says "analyze this PRD", "parse requirements", "extract from PRD"
- First step when setting up a new project pipeline

## Input

- **Required**: PRD file path (markdown, PDF, or text)
- **Optional**: Existing `docs/plans/project.yaml` (if project is already initialized)

## Execution Flow

> **Path resolution**: Before constructing any output path, resolve `{plans_dir}` per `lib/plans-dir-resolver.md`. All `docs/plans/` references below (except `docs/plans/project.yaml`, which stays at repo root) are relative to that resolved directory.

### Phase 0.5 — Ambiguity Detection (0.5.0+)

**Triggers when**: `superpowers:brainstorming` is installed AND the input PRD is non-empty.

**Read**: `lib/brainstorm-runner.md` — follow it exactly for this phase.

Steps:

1. Parse the PRD into a draft `prd_structure` dict (modules, user stories, NFRs, constraints, external_deps) using the same regex/scan heuristics as Phase 1 — this is a preliminary pass; the real extraction happens in Phase 1 after Phase 0.5 resolutions are applied.

2. Invoke `superpowers:brainstorming` with the framing prompt from `lib/brainstorm-runner.md`. Pass the PRD text and the draft prd_structure as inputs.

3. Brainstorming returns an `ambiguity_report` (schema in brainstorm-runner.md). Capture:
   - `auto_resolved[]` — append to `{plans_dir}/{date}-ambiguity-resolution-log.md` (one entry per auto-resolve); no user interaction needed
   - `user_decisions_pending[]` — surface to the user

4. **[HUMAN REVIEW CHECKPOINT 0.5]** — if `user_decisions_pending` is non-empty:

   Present in batches of ≤8 per round (priority order: cross_story_conflict → nfr_vs_functional_conflict → constraint_implicit_external → module_boundary_undefined).

   Each question is multi-choice with the brainstorm-runner-provided options.

5. Apply the user's resolutions:
   - For cross_story_conflict: amend `draft_prd_structure.user_stories` per the chosen option (drop fields, add tenant scoping, etc.)
   - For nfr_vs_functional_conflict: amend `draft_prd_structure.nfrs` and/or insert a new `constraints[]` entry capturing the chosen trade-off
   - For module_boundary_undefined: add a stub `modules[]` entry with the chosen interpretation
   - For constraint_implicit_external: add the system to `external_deps[]`

6. Write a summary into the (final) prd_structure:

   ```yaml
   extraction:
     ambiguity_resolution:
       auto: <auto_resolved_count>
       asked: <user_pending_count>
       rounds: <batches_required>
       resolutions:
         - id: A1
           chosen: "<label>"
         # ...
   ```

   When Phase 0.5 was skipped (brainstorming not installed), the same block is written with the skip-path variant:

   ```yaml
   extraction:
     ambiguity_resolution:
       auto: 0
       asked: 0
       skipped_reason: "brainstorming-not-installed"
   ```

   This makes downstream contract-check (skill-12) able to distinguish "Phase 0.5 ran and found nothing" from "Phase 0.5 was skipped."

7. Proceed to Phase 1 with the amended `draft_prd_structure` as the starting point.

**Graceful degradation**: if `superpowers:brainstorming` is not installed, skip this phase entirely. Log the warning prescribed in `lib/brainstorm-runner.md §Graceful degradation`. Phase 1 proceeds with the unamended PRD; the `extraction.ambiguity_resolution` block is written with the skip-path variant shown in Step 6 below.

**Verification**: applying this phase to `tests/fixtures/prd-bridge/conflict-prd.md` must produce an `ambiguity_report` matching `tests/expected/conflict-prd.ambiguity-report.yaml` on the 3 user-pending entries (IDs A1, A2, A3).

### Step 1: Read & Understand the PRD

1. Read the entire PRD document
2. If the PRD is very large (>500 lines), read it in sections and build a structural outline first
3. Identify the document's organizational structure (sections, subsections, appendices)

### Step 2: Extract Structured Data

Parse the PRD into these categories:

**Modules** — Functional groupings of the system:
```yaml
modules:
  - id: MOD-01
    name: "Module name"
    description: "What this module does"
    prd_sections: ["§3.1", "§3.2"]  # Source references
    sub_modules:
      - id: MOD-01a
        name: "Sub-module"
        description: "..."
```

**User Stories** — Who does what and why:
```yaml
user_stories:
  - id: US-001
    module: MOD-01
    persona: "Customer service agent"
    action: "View real-time customer conversation"
    goal: "Respond within SLA"
    acceptance_criteria:
      - "AC-001: Messages appear within 500ms"
      - "AC-002: Customer sentiment is displayed"
    prd_ref: "§4.1.2"
```

**Non-Functional Requirements (NFRs)**:
```yaml
nfrs:
  - id: NFR-01
    category: performance  # performance | security | scalability | compliance | reliability
    requirement: "API response time < 200ms p95"
    metric: "p95 latency"
    target: "200ms"
    prd_ref: "§6.1"
```

**Technical Constraints**:
```yaml
constraints:
  - id: CON-01
    type: technology  # technology | architecture | deployment | data | integration
    description: "Must use Python 3.12+ with async/await"
    rationale: "Existing team expertise"
    prd_ref: "§7.2"
```

**External Dependencies**:
```yaml
external_deps:
  - id: DEP-01
    name: "Third-party API"
    type: api  # api | service | library | data-source
    status: available  # available | pending | unknown
    owner: "External team"
    prd_ref: "§8.1"
```

### Step 3: Cross-Reference & Validate

1. Check that every module has at least one user story
2. Check that every user story has acceptance criteria
3. Identify user stories that span multiple modules (flag as "cross-cutting")
4. Identify NFRs that don't have measurable targets (flag for clarification)
5. Build a module dependency graph (which modules reference each other)

### Step 4: Generate Complexity Assessment

For each module, estimate:
```yaml
complexity:
  - module: MOD-01
    estimated_tasks: 8-12  # Range estimate
    risk_level: medium     # low | medium | high
    risk_factors:
      - "Depends on external API (DEP-01) with unknown availability"
    suggested_type_split:
      green: 6   # Pure implementation
      yellow: 3  # Needs design review
      red: 1     # Needs stakeholder decision
```

### Step 5: Output

1. Write structured output to `{plans_dir}/{date}-prd-structure.yaml`
2. Generate a human-readable summary (print to terminal):
   - Module count and dependency graph (Mermaid)
   - User story count by module
   - NFR summary table
   - Flagged items needing clarification
   - Estimated total task count range

### Step 6: Human Review Checkpoint

**STOP here.** Present the summary and wait for user approval before proceeding.

Prompt the user:
> PRD analysis complete. {N} modules, {M} user stories, {K} NFRs extracted.
> {F} items flagged for clarification (see above).
>
> Review `{plans_dir}/{date}-prd-structure.yaml` and let me know:
> 1. Any modules missing or incorrectly scoped?
> 2. Any user stories that should be split or merged?
> 3. Answers to flagged clarification questions?
>
> When ready, run `/gap-scan` to analyze what already exists in the codebase.

## Output File Format

See `templates/prd-structure.yaml` for the complete output template.

## Tips

- If the PRD is in a non-standard format, adapt extraction to match the document's structure rather than forcing a rigid parse
- When the PRD uses domain-specific terminology, preserve it in the extracted data and add a glossary section
- If the PRD references external documents (API specs, design docs), note them in `external_deps` for later retrieval
- Cross-reference with existing `CLAUDE.md` for project-specific conventions
