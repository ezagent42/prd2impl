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
| `design-spec` | modules (partial), nfrs, constraints, external_deps | user_stories |

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
  source_role: "prd"    # prd | plan | user-stories | design-spec

  modules: [...]         # populated for prd + plan + design-spec; empty for user-stories
  user_stories: [...]    # populated for prd + user-stories; empty for plan / design-spec
  nfrs: [...]            # populated for prd + design-spec
  constraints: [...]     # populated for prd + plan + design-spec
  external_deps: [...]   # populated for prd + design-spec (from §Dependencies section)
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

## Extraction: role=design-spec

A design-spec document (typically from `superpowers:brainstorming` output) describes
*what to build* and *how* — modules, behavioral requirements, and known limitations.
It usually lacks user stories (those go in `prd` or `user-stories` roles).

### Section scanning

Scan the entire document for top-level (`##`) and second-level (`###`) headings.
Match against the following patterns (case-insensitive, with or without numeric prefix
like `## 3.` or `### 3.1`):

| Target field | Heading keywords |
|---|---|
| `modules[]` | "Design", "设计", "Architecture", "架构", "方案" |
| `nfrs[]` | "Behavioral Requirements", "行为约束", "Requirements", "需求", "Acceptance", "验收条件", "约束" |
| `constraints[]` | "Known Limitations", "已知限制", "Limitations", "Constraints", "已知约束" |

**SKIP** sections: "Goal / 目标", "Current State / 现状" — these are narrative context
and do not map to any prd-structure field.

**Section order**: irrelevant. Scan by heading keyword, not by position.

### Extracting modules

**Sub-heading scoping**: a `###` sub-heading "belongs to" the §Design section only if
it appears between the §Design `##` heading and the next `##` heading. Stop scanning at
the next `##` boundary.

**Case 1: §Design section has `###` sub-headings (scoped as above).**

Each sub-heading becomes one module:

```yaml
- id: MOD-{N:02d}
  name: <sub-heading text, stripped of numeric prefix>
  description: <first paragraph of that sub-section>
  prd_sections: ["§3.{M}"]   # or slug if heading has no number
  source: "design-spec"
  coarse: false
```

**Case 2: §Design section has NO sub-headings.**

Entire section becomes a single coarse module:

```yaml
- id: MOD-01
  name: "Design"   # or the exact heading text
  description: <first paragraph>
  prd_sections: ["§3"]   # or slug
  source: "design-spec"
  coarse: true
```

**prd_sections encoding**:
- Numbered heading `### 3.1 Redis-backed Counter` → `["§3.1"]`
- Unnumbered heading `### Redis-backed Counter` → `["redis-backed-counter"]` (slug: lowercase, hyphens)
- Numbered top-level `## 3. Design` → `["§3"]`
- Unnumbered top-level `## Design` → `["design"]`

**Slug generation algorithm** (for unnumbered headings):
1. Lowercase ASCII letters; leave CJK and other non-ASCII characters untouched
2. Replace any run of whitespace OR ASCII punctuation (`,`, `.`, `:`, `;`, `/`, `\`, `(`, `)`, etc.)
   with a single `-`
3. Strip leading/trailing `-`
4. Preserve existing hyphens (don't collapse `redis-backed` to `redis-backed`; it stays as-is)

Examples:
- `"Redis-backed Counter"` → `"redis-backed-counter"`
- `"架构模块 A"` → `"架构模块-a"` (CJK retained, "A" lowercased)
- `"Step 1: Load Data"` → `"step-1-load-data"`

### Extracting nfrs

Each bullet (`- ...`) or numbered item (`1. ...`) under the §Requirements section
becomes one NFR:

```yaml
- id: NFR-{N:02d}
  category: <auto-detect>
  requirement: <bullet text, verbatim>
  prd_ref: "§4"   # or slug
```

**Category heuristic** (applied to lowercased requirement text):
- contains "performance", "latency", "qps", "throughput", "延迟", "性能" → `performance`
- contains "compat", "backcompat", "backward", "兼容" → `compatibility`
- contains "security", "auth", "安全" → `security`
- else → `general`

`metric` / `target` fields are typically absent in design-spec — omit from output (don't
emit empty strings).

### Extracting constraints

Each bullet under §Known Limitations:

```yaml
- id: CON-{N:02d}
  type: <auto-detect>
  description: <bullet text; if bullet ENDS WITH "（Y）" or ": Y" as a trailing suffix, the part before (with suffix stripped); else full bullet text>
  rationale: <if bullet ends with trailing "（Y）" or ": Y" suffix, the Y part; else same as description>
  prd_ref: "§8"   # or slug

**Important**: the split rule only fires for **trailing** parens/colon. A bullet like
`"不处理全局限流（只 per-key），per-user 全局限流需另议"` has an INLINE paren followed
by more text — no split; description == rationale == whole bullet.
```

**Type heuristic** (applied to lowercased text):
- contains "tech", "tool", "framework", "library" → `technology`
- contains "schedule", "deadline", "date", "deliver" → `schedule`
- else → `general`

### Extracting external_deps

Locate a section heading matching (case-insensitive, match by heading text — NOT by number):

- `Dependencies` / `Dependency`
- `依赖` / `外部依赖`
- Numbered prefixes like `## 8. Dependencies`, `## N. 依赖` — strip the leading number+dot before matching keywords.

If no matching heading is found → `external_deps: []` (not a warning — dep-less specs are valid).

Inside the matching section, detect one of two sub-formats:

**Format A — markdown table**:

```markdown
## 8. Dependencies
| Package | Version | Purpose |
|---------|---------|---------|
| react-markdown | ^9.0.1 | core renderer |
```

Parse columns (flexible ordering, case-insensitive headers):
- `Package` / `Name` / `Library` → `name`
- `Version` / `Ver` → `version`
- `Purpose` / `Description` / `Why` → `purpose`

For each data row emit:

```yaml
- id: DEP-NN            # sequential starting DEP-01
  name: "<name>"         # strip backticks, trim whitespace
  version: "<version>"
  purpose: "<purpose>"
  source_anchor: "<heading text>"
```

**Format B — bullet list**:

```markdown
## 8. Dependencies
- `react-markdown@^9.0.1` — core markdown renderer
- `remark-gfm@^4` — GFM extensions
```

For each bullet:
- Strip leading `- ` and any surrounding whitespace.
- Extract the leading backtick-wrapped token. Split on `@` — left side is `name`, right side is `version`.
- Text after the first ` — ` (em-dash + space) or `: ` becomes `purpose`.
- If no `@` in the token: `version: null`.
- If no em-dash / colon separator: `purpose: null`.

### Numbering

IDs are sequential across the section: DEP-01, DEP-02, ... If multiple Dependencies sections somehow exist (shouldn't, but defensive): continue numbering across them without reset.

### Output

Splice the emitted `external_deps` list into the in-progress `prd_structure` object alongside the existing `modules` / `nfrs` / `constraints` additions.

### Graceful degradation (external_deps)

- No §Dependencies section → `external_deps: []`, no warning.
- §Dependencies exists but has no table and no bullets → `external_deps: []`, warn `§Dependencies section in {file} is empty`.
- A table row with missing Package cell → skip that row, warn `§Dependencies table row {N} missing Package; skipped`.
- A bullet without a backtick-wrapped token → skip that bullet, warn similarly.

### user_stories handling

**Default: not extracted.** design-spec focuses on "what/how", not "who/why".
Output `user_stories: []` (empty array) for design-spec role **unless the
`--synthesize-user-stories` flag was passed to `/ingest-docs`**.

### user_stories LLM synthesis (role=design-spec, opt-in)

Gated on the `--synthesize-user-stories` flag registered in skill-0 SKILL.md §Inputs. When the flag is absent: skip this entire subsection, output `user_stories: []`.

#### Trigger (when flag is set)

Run the LLM pass IF AND ONLY IF:
1. The `--synthesize-user-stories` flag was set, AND
2. A section heading matching `Scope` / `范围` was found, AND
3. Regex-extracted `user_stories` is empty (always true for design-spec).

If flag set but §Scope absent → warn `--synthesize-user-stories set but §Scope not found in {file}; user_stories remains []`. Do NOT make the LLM call.

#### Extract §Scope content

Capture the §Scope section from the first heading line through the next `##`-level heading (exclusive). This is the input to the LLM.

#### LLM prompt

Invoke the LLM (model: `claude-sonnet-4-6`) with:

```
System: You extract user stories from design spec Scope sections. Output YAML only.

User: Extract user stories from this design spec's Scope section.

Rules:
- Produce one user story per surface/row. Max 6 stories.
- `persona` MUST be a string that appears verbatim in the Scope text.
- `action` + `goal` describe what the persona does on that surface, using the
  spec's own language. Do NOT invent features not hinted at in the Scope.
- `acceptance_criteria` MUST be []. Do not hallucinate ACs.
- Return YAML in this exact shape:

user_stories:
  - id: US-NN
    module: MOD-??          # pick from: {modules_list}
    persona: "..."
    action: "..."
    goal: "..."
    acceptance_criteria: []
    prd_ref: "§Scope row N"
    source: synthesized

Scope section:
---
{scope_text}
---

Modules available: {modules_list}
```

Substitute before the call:
- `{scope_text}` = the extracted §Scope block.
- `{modules_list}` = comma-separated list of module IDs from the in-progress `prd_structure.modules`. If the modules list is empty, pass `MOD-01` as a fallback AND emit one synthetic module `MOD-01 "Scope"` so stories have a valid anchor.

#### Parse LLM output

1. Parse the returned YAML (expect a top-level `user_stories:` key).
2. Validate each story:
   - `persona` must be a verbatim substring of the §Scope text (literal check). If not found verbatim → drop that story; log warning `LLM persona {persona} not verbatim in §Scope; story dropped`.
   - `acceptance_criteria` must be `[]` (empty list). If not, force to `[]` and warn.
   - Sequential re-numbering of `id` after validation.
3. Splice the validated list into the in-progress `prd_structure.user_stories`.

#### Error handling

- LLM call fails (timeout, quota) → `user_stories: []`, emit warning `LLM user_stories synthesis skipped: {reason}. Re-run /ingest-docs to retry.`
- LLM output not valid YAML → `user_stories: []`, emit warning + log the raw output for debugging (truncate to 1000 chars).
- No personas pass the verbatim-substring check → `user_stories: []`, warn `LLM produced 0 stories with valid personas; check Scope format`.

#### Cost ceiling

Maximum 1 LLM call per `/ingest-docs` invocation per design-spec file. If multiple design-spec files are ingested in the same run, the call fires once per file (cap still "1 per file"). Cache §Scope text in memory so no repeated extraction.

### Graceful degradation

If the document lacks a §Design section entirely: `modules: []`, no error.
If the document lacks §Requirements: `nfrs: []`, no error.
If the document lacks §Known Limitations: `constraints: []`, no error.
If ALL three are absent: emit empty `prd_structure`; skill-0 Phase 4.1 will skip writing
`prd-structure.yaml`. See `cross-validator.md` for the corresponding warning messages.
