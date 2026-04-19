# prd-extractor — Phase 2c of skill-0-ingest

Extract structured PRD data from documents classified as `role: prd`, `plan`, or `user-stories`.
Produces additions to the in-memory `prd_structure` object that becomes `prd-structure.yaml`.

This extractor reuses skill-1's extraction logic for full PRD documents.
For `plan` and `user-stories` roles it applies a subset of that logic.

## Role routing

| Role | Extracts | Skips |
|------|----------|-------|
| `prd` | modules, user_stories, nfrs, constraints, external_deps | — (full skill-1 logic) |
| `plan` | modules (as phases/milestones), constraints only | user_stories, nfrs, external_deps |
| `user-stories` | user_stories only | modules, nfrs, constraints, external_deps |

## Extraction: role=prd (full)

Apply skill-1's Step 2 extraction logic verbatim. See `skill-1-prd-analyze/SKILL.md §Step 2`.

Summary of extracted fields:

**modules**:
```yaml
modules:
  - id: MOD-01
    name: "Module name"
    description: "..."
    prd_sections: ["§3.1"]
    sub_modules: []
```

**user_stories**:
```yaml
user_stories:
  - id: US-001
    module: MOD-01
    persona: "..."
    action: "..."
    goal: "..."
    acceptance_criteria: ["AC-001: ..."]
    prd_ref: "§4.1"
```

**nfrs**:
```yaml
nfrs:
  - id: NFR-01
    category: performance
    requirement: "..."
    metric: "..."
    target: "..."
    prd_ref: "§6.1"
```

**constraints**:
```yaml
constraints:
  - id: CON-01
    type: technology
    description: "..."
    rationale: "..."
    prd_ref: "§7.2"
```

**external_deps**:
```yaml
external_deps:
  - id: DEP-01
    name: "..."
    type: api
    status: available
    owner: "..."
    prd_ref: "§8.1"
```

## Extraction: role=plan

A plan document describes milestones and phases. Map these to prd-structure fields:

**Milestone → module**:

```yaml
modules:
  - id: MOD-01
    name: "M1 — Core Features"         # milestone name
    description: "Phase 1 deliverables"
    prd_sections: []
    sub_modules:
      - id: MOD-01a
        name: "Conversation modes"
        description: "implement state machine"
```

Detection: look for milestone headings (`## M1`, `## Phase 1`, `## Milestone 1`), then collect bullet items under each as sub_modules.

**Constraints from plan**:

Look for constraint-like statements:
- "Must use X" / "requires X" / "only Y" → add as `CON-NN` with `type: architecture`
- Hard deadlines → add as `CON-NN` with `type: deployment`

**Skip**: user_stories, nfrs, external_deps.

## Extraction: role=user-stories

Extract only user_stories:

Recognize "As a X, I want Y, so that Z" pattern (English) or:
- Chinese equivalent: "作为 X，我希望 Y，以便 Z"
- Structured list: `**US-NNN** — As a ...`

For each:
- `id`: extract `US-NNN` from text; if none, auto-assign `US-{seq}`
- `persona`: X from "As a X"
- `action`: Y from "I want Y"
- `goal`: Z from "so that Z" (null if absent)
- `acceptance_criteria`: bullet list after `Acceptance Criteria:` or `AC-NNN:` markers
- `module`: null (cross-validator or user assigns later)
- `prd_ref`: null

## Output format

```yaml
prd_structure:
  source_type: "ingested"
  source_files: ["{md_path}"]
  source_role: "prd"    # prd | plan | user-stories

  modules: [...]         # populated for prd + plan; empty for user-stories
  user_stories: [...]    # populated for prd + user-stories; empty for plan
  nfrs: [...]            # populated for prd only
  constraints: [...]     # populated for prd + plan
  external_deps: [...]   # populated for prd only
```

## Handling multiple prd/plan/user-stories MDs

Multiple MDs of same role → merge:
- Modules: concatenate; re-ID as MOD-01, MOD-02, …
- User stories: concatenate; re-ID as US-001, US-002, …
- NFRs: concatenate; re-ID
- Constraints: concatenate; re-ID; de-duplicate if identical text

Multiple MDs of mixed roles (e.g. one `prd` + one `user-stories`):
- Merge user_stories from user-stories file into prd_structure from prd file
- Warn if user story IDs overlap (keep prd-sourced IDs, append `-b` suffix to user-stories-sourced duplicates)

## Verification

Input 1: `tests/fixtures/role-detection/clear-prd.md`
Expected:
- `len(modules) >= 1`
- `len(user_stories) == 2` (US-001, US-002)
- `len(nfrs) == 2` (NFR-001, NFR-002)
- `len(constraints) >= 1`

Input 2: `tests/fixtures/role-detection/clear-plan.md`
Expected:
- `len(modules) >= 3` (M0, M1, M2 → MOD-01, MOD-02, MOD-03)
- `user_stories == []`
- `nfrs == []`

Input 3: `tests/fixtures/role-detection/clear-user-stories.md`
Expected:
- `len(user_stories) == 5` (US-010 through US-021, 5 items in fixture)
- `modules == []`
- `nfrs == []`

See `tests/expected/clear-prd.prd-structure.yaml` and `tests/expected/clear-plan.prd-structure.yaml`.
