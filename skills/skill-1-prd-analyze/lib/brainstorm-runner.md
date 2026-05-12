# brainstorm-runner — Self-driven invocation contract for superpowers:brainstorming

Used by: `skills/skill-1-prd-analyze/SKILL.md` Phase 0.5 (ambiguity detection).

When skill-1 invokes `superpowers:brainstorming`, it does NOT do so in the skill's default "design a new feature interactively" mode. Instead, it invokes brainstorming in a constrained mode optimized for ambiguity surfacing in an EXISTING PRD. This file specifies that constraint.

## Why a runner contract

`superpowers:brainstorming` is general-purpose. It asks questions to discover what the user wants to build. But in skill-1's context, the user has ALREADY written a PRD — we're not designing, we're surfacing problems in what's already written. Without this contract, brainstorming would ask "what are you trying to build?" and overwhelm the user with discovery questions.

The runner contract gives brainstorming a tighter brief: "find ambiguities, propose resolutions, only escalate the ones the user must decide."

## Inputs

- `prd_text`: The full text of the PRD markdown file(s) skill-1 received.
- `draft_prd_structure`: Skill-1's preliminary extraction (modules, user stories, NFRs, constraints, external_deps). This is what brainstorming will sanity-check against.

## Brainstorming framing prompt

When skill-1 invokes brainstorming, pass this framing (a "system-prompt-like" preamble) to anchor the skill's behavior:

```
You are running in PRD-AMBIGUITY-DETECTION mode for prd2impl skill-1.

Your goal is NOT to design a new feature. The PRD has already been written.
Your goal is to surface ambiguities that, if left unresolved, would cause downstream
task generation (skill-3) to produce wrong or under-specified tasks.

ONLY surface ambiguities that fall into these four categories:

  1. cross_story_conflict — Two or more user stories make incompatible claims
     (e.g., "single-tenant" vs "multi-tenant", "synchronous" vs "eventually consistent").
  2. nfr_vs_functional_conflict — An NFR contradicts a functional requirement
     (e.g., "P95 < 60s" + "every action audited synchronously" + audit-table constraint).
  3. constraint_implicit_external — A constraint references an external system that isn't
     in `external_deps[]`.
  4. module_boundary_undefined — A noun is referenced in 2+ places but never declared as
     a module / external_dep / data type. Cannot infer its shape without input.

DO NOT surface:
  - Stylistic choices (naming, file paths, framework selection)
  - Future-feature questions ("should we also add X?")
  - Implementation-detail questions ("should the cache be in-memory or Redis?")
  - Anything that downstream skills (skill-3 task-gen, skill-4 plan-schedule) can decide on their own

For each ambiguity:
  - Propose 2-3 concrete options
  - State the impact of each option in 1-2 lines
  - Recommend one and give a one-sentence rationale
  - Assign a category from the four listed above

For each obvious resolution (terminology drift, type inference, convention application):
  - Auto-resolve and log to `auto_resolved[]`. Do NOT ask the user about these.

Output format: see "## Output schema" section below in this document.
```

## Output schema

brainstorm-runner returns a YAML structure with this shape:

```yaml
ambiguity_report:
  source_files: [...]
  auto_resolved:
    - signal: "<what was detected>"
      action: "<what you did>"
  user_decisions_pending:
    - id: A1
      category: cross_story_conflict | nfr_vs_functional_conflict | constraint_implicit_external | module_boundary_undefined
      ambiguity: |
        <2-4 line description of the conflict>
      options:
        - {label: "...", impact: "..."}
      recommended: "<one of the labels>"
      rationale: "<one sentence>"
  summary:
    total_signals_scanned: <int>
    auto_resolved_count: <int>
    user_pending_count: <int>
    batches_required: <int>  # ceil(user_pending_count / 8)
```

Note the category enum order matches the priority ordering used in "Interactive batch sizing" below — keep both lists in sync if either is edited.

## Interactive batch sizing

If `len(user_decisions_pending) > 8`, split into rounds of ≤8, prioritized by:

1. `cross_story_conflict` (highest — these affect data model)
2. `nfr_vs_functional_conflict` (system-level contract)
3. `constraint_implicit_external` (integration boundary)
4. `module_boundary_undefined` (lowest — usually has obvious defaults)

Each round is its own user-interaction pass. Apply round-1 answers before computing round-2 (later rounds may collapse if earlier answers resolve cascading ambiguities).

## Acceptance criteria

The contract holds when, applied to a PRD known to contain N ambiguities:
- `len(user_decisions_pending) == N` (no false positives, no false negatives)
- Each entry's `category` is one of the four allowed values
- Each entry's `options` has 2-3 entries
- Each entry's `recommended` is one of its own `options[*].label`
- `summary.batches_required == ceil(N / 8)`

## Verification fixture

Apply this contract to `tests/fixtures/prd-bridge/conflict-prd.md`. The expected output is `tests/expected/conflict-prd.ambiguity-report.yaml`. The output must match it on:
- The 3 `user_decisions_pending` IDs (A1, A2, A3)
- Each one's `category`
- Each one's `recommended` matches one of its own options
- `summary.user_pending_count == 3`
- `summary.batches_required == 1`

`total_signals_scanned` and `auto_resolved_count` may vary by implementation — they're informational, not asserted.

## What happens after

`brainstorm-runner` does NOT apply resolutions itself. It returns the report to skill-1's Phase 0.5, which:
1. Presents `user_decisions_pending` to the user (in rounds if needed)
2. Collects answers
3. Applies them by amending the draft `prd_structure` (e.g., dropping conflicting fields, adding `external_deps[]` entries, narrowing constraints)
4. Inlines a summary in the final `prd-structure.yaml` under `extraction.ambiguity_resolution`

## Graceful degradation

If `superpowers:brainstorming` is not installed:
- Skill-1 Phase 0.5 logs: `"brainstorming unavailable — ambiguity detection skipped; PRD extracted as-written"`
- `prd-structure.yaml.extraction.ambiguity_resolution` is set to `{auto: 0, asked: 0, skipped_reason: "brainstorming-not-installed"}`
- skill-1 proceeds to Phase 1 immediately

This preserves 0.4.x behavior when superpowers is missing.
