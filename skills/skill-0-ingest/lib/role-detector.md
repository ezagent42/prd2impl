# role-detector — Phase 1 of skill-0-ingest

Classify each input MD into one of six roles using a 4-signal heuristic scorer.
Produce a confirmation table for human review before extraction begins.

## Roles

| Role | Produces | Typical document |
|------|----------|-----------------|
| `gap` | gap-analysis.yaml | Gap / 缺口 / 缺失 analysis listing items with P0/P1/P2 |
| `design-spec` | prd-structure.yaml (partial: modules, nfrs, constraints) + task-hints.yaml | Design spec / 设计方案 with file-change lists and implementation steps. After v0.2.1, also extracts §Design modules, §Requirements nfrs, §Known Limitations constraints into a partial prd-structure.yaml. |
| `plan` | prd-structure.yaml (partial) + task-hints.yaml (steps only) | Plan / 计划 with milestones and phases |
| `prd` | prd-structure.yaml (full) | PRD / Requirements with user stories and NFRs |
| `user-stories` | prd-structure.yaml (user_stories section) | Standalone user-story list |
| `unknown` | (skipped with warning) | No clear signal |

## Scoring algorithm

For each input file, FIRST check the writing-plans override (Signal 0). If it fires, the file is classified as `role: plan, confidence: 100` and the 4-signal scoring below is skipped. Otherwise, run the 4-signal heuristic.

### Signal 0 — Writing-plans format override (highest confidence, 100 points)

Scan the FIRST 30 lines of the file for either of these literal substrings:

- `REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development`
- `REQUIRED SUB-SKILL: Use superpowers:executing-plans`

This is the canonical writing-plans header emitted by `superpowers:writing-plans`. Its presence means the file was authored to be consumed by `superpowers:executing-plans` or `subagent-driven-development` — i.e., the plan-passthrough path.

If either substring is present:
- Return `role: plan, confidence: 100, evidence: "writing-plans header detected"` immediately.
- SKIP signals 1-4 entirely.
- Downstream (skill-0 Phase 2b) will route to `lib/plan-parser.md` instead of the legacy implementation_steps extractor.

If neither substring is present, fall through to the 4-signal heuristic below. A hand-written plan that lacks the writing-plans header can still score `role: plan` via signals 1-3, but it will go through the legacy spec-extractor flow rather than plan-parser.

### Signal 1 — Filename (30 points)

Check the base filename (lowercased, dashes normalized to hyphens):

| Pattern match | Points | Role hint |
|---|---|---|
| `*-gap.md` or `*gap-analysis*` or `*-gaps.md` | 30 | gap |
| `*-design.md` or `*-spec.md` or `*-design-spec*` | 30 | design-spec |
| `*-plan.md` or `*-planning*` | 30 | plan |
| `*-prd.md` or `*-requirements*` | 30 | prd |
| `*-stories.md` or `*-user-stories*` | 30 | user-stories |
| No match | 0 | — |

### Signal 2 — Frontmatter (20 points)

Parse YAML frontmatter block (`---` ... `---`) if present:

| Frontmatter field | Points | Role hint |
|---|---|---|
| `type: gap` or `type: gap-analysis` | 20 | gap |
| `type: design-spec` or `type: spec` | 20 | design-spec |
| `type: plan` | 20 | plan |
| `type: prd` or `type: requirements` | 20 | prd |
| `type: user-stories` | 20 | user-stories |
| No `type` field or no frontmatter | 0 | — |

### Signal 3 — First 50 lines keywords (30 points)

Read first 50 lines; look for heading (H1/H2) containing role keywords:

| Keywords (case-insensitive) | Points | Role hint |
|---|---|---|
| Gap / 缺口 / 缺失 / 偏差 / Missing | 30 | gap |
| Design / Spec / 设计 / 方案 / Architecture | 30 | design-spec |
| Plan / 计划 / 规划 / Roadmap | 30 | plan |
| PRD / Requirements / Product Requirements | 30 | prd |
| User Stories / As a … I want | 30 | user-stories |

If multiple keywords hit different roles, take highest-point match.

### Signal 4 — Structural signatures (20 points)

Scan entire document for structural markers:

| Marker | Points | Role hint |
|---|---|---|
| Lines matching `P0` / `P1` / `P2` as priority tag (not inline code) | 15 | gap |
| Section heading containing "File Changes" / "文件变更" | 10 | design-spec |
| Section heading containing "Implementation" / "Steps" / "实施" | 10 | design-spec |
| Lines with pattern `US-\d+` or `As a .* I want` | 15 | user-stories |
| Lines with pattern `NFR-\d+` or `Acceptance Criteria` | 10 | prd |
| Milestone / Phase table or `M\d+` / `P\d+ · ` pattern | 10 | plan |

Add all matching points, cap at 20.

### Final score

If Signal 0 fired, final_score = 100 and role = plan (short-circuited above).

Otherwise:

```
final_score = signal1 + signal2 + signal3 + signal4
role = the hint that contributed most points (sum per role hint)
```

If two roles tie, return both with a note; user breaks tie in confirmation table.

### Thresholds

| Score | Confidence level | Action |
|---|---|---|
| ≥ 70 | High | Auto-accepted; shown green in table |
| 40–69 | Medium | Show top-2 candidates + evidence; user confirms |
| < 40 | Low / unknown | Show as `unknown`; requires `--tag` or user override |

### LLM fallback (score < 70 only)

When the heuristic score is below 70, invoke LLM with this prompt:

```
Read the following Markdown document (first 80 lines shown).
Classify it as one of: gap, design-spec, plan, prd, user-stories, unknown.
Return JSON: {"role": "<role>", "confidence": <0-100>, "reason": "<one sentence>"}

--- DOCUMENT ---
{first_80_lines}
```

Merge: `merged_score = max(heuristic_score, llm_confidence)`. Role from the higher scorer wins.

## Execution steps

1. For each input file path:
   a. **Signal 0 (override)**: read first 30 lines; if writing-plans header substring present, store `{detected_role: "plan", confidence: 100, evidence: "writing-plans header"}` and SKIP steps b-f for this file.
   b. Compute signal 1 from filename.
   c. Read file; parse frontmatter → signal 2.
   d. Read first 50 lines → signal 3.
   e. Scan full document → signal 4.
   f. Sum → `heuristic_score`, identify `role`.
   g. If `heuristic_score < 70`: invoke LLM fallback; merge.
   h. Store `{path, detected_role, confidence, evidence}`.

2. Check `--tag` overrides from CLI: for each `--tag role=path`, force `detected_role = role`, `confidence = 100`.

3. Build and print the confirmation table (see template: `templates/role-confirmation.md`).

4. Wait for user response:
   - User types `ok` / `y` / `yes` → proceed with shown roles.
   - User types `override N role` → update row N to new role.
   - User types `drop N` → remove file from processing list.
   - If all files end up as `unknown` after overrides → abort Phase 1.

## Output format

Return a list in this structure (in-memory; not written to disk):

```yaml
role_detections:
  - path: "docs/plans/2026-04-18-prd-full-journey-gap.md"
    detected_role: gap
    confidence: 90
    method: heuristic      # heuristic | llm | forced
    evidence:
      filename_match: "*-gap.md → 30pts"
      frontmatter: "no type field → 0pts"
      heading_keyword: "'Gap Analysis' in H1 → 30pts"
      structural: "P0/P1/P2 tags present → 15pts, total 20pts capped"

  - path: "docs/superpowers/specs/2026-04-18-admin-portal-web-layout-design.md"
    detected_role: design-spec
    confidence: 80
    method: heuristic
    evidence:
      filename_match: "*-design.md → 30pts"
      frontmatter: "no type field → 0pts"
      heading_keyword: "'Design' in H1 → 30pts"
      structural: "'File Changes' section → 10pts, 'Implementation' section → 10pts = 20pts"
```

## Fixture set (for verification)

Six fixture files live in `tests/fixtures/role-detection/`. Each must score ≥ 70 heuristically:

| Fixture file | Expected role | Key signals |
|---|---|---|
| `clear-gap.md` | gap | filename `-gap`, H1 "Gap Analysis", P0/P1/P2 items |
| `clear-design-spec.md` | design-spec | filename `-design`, H1 "Design", "File Changes" + "Implementation Steps" sections |
| `clear-plan.md` | plan | filename `-plan`, H1 "Plan", milestone table with M1/M2 |
| `clear-prd.md` | prd | filename `-prd`, H1 "PRD", NFR-001, US-001 |
| `clear-user-stories.md` | user-stories | filename `-stories`, H1 "User Stories", "As a … I want" lines |
| `medium-ambiguous.md` | design-spec (score 55, LLM needed) | H1 ambiguous; has "File Changes" but filename generic |
