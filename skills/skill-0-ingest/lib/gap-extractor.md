# gap-extractor — Phase 2a of skill-0-ingest

Extract structured gap entries from a Markdown document classified as `role: gap`.
Produces additions to the in-memory `gap_analysis` object that becomes `gap-analysis.yaml`.

## Input

- One or more MD files with `detected_role: gap` from role-detector.
- May also receive `--tag gap=path` forced files.

## Extraction steps

### Step 1 — Find gap items

Scan the document for item-level blocks. A gap item is any of:

**Pattern A — Heading item** (most common):

```
### <source_id> <description> [P0|P1|P2]
#### <source_id> <description> · P0          ← middle dot separator (U+00B7)
```

Examples:
- `### A-① 缺注册接入独立步骤 [P0]`
- `#### A-① 缺"注册接入"独立步骤 · P0`         ← real AutoService format
- `### B-⑦ Customer SDK hardcoded ws://localhost [P0]`
- `### GAP-004 Replay job has no dedup [P1]`

Priority tag detection: match `[P0]`, `[P1]`, `[P2]`, `· P0`, `· P1`, `· P2`, `·P0`, `·P1`, `·P2` (Unicode middle dot U+00B7, with or without space).

source_id detection: alphanumeric prefix before first space, including circled Unicode numbers (①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰) and letter-number combinations like `A-①`, `B-⑦`, `C-⑫`.

Heading level: accept H2 (`##`) through H5 (`#####`) as gap item headings. Peer level for "next item" is determined by the same heading depth as the matched item.

**Pattern B — List item with priority tag**:

```
- **<source_id>**: <description> — Priority: P0
```

**Pattern C — Table row** (gap ID in column 1, description in column 2, priority in column 3):

```
| A-① | 缺注册接入独立步骤 | P0 |
```

For each matched item, extract:
- `source_id`: the human-authored ID (`A-①`, `B-⑦`, `GAP-004`, etc.)
- `description`: the item text after source_id, before `[P0]` / `[P1]` / `[P2]`
- `priority`: P0 / P1 / P2 (default P1 if not explicitly tagged)
- `source_anchor`: the Markdown heading slug for this item (use GitHub slug algorithm)

### Step 2 — Extract sub-fields per item

For each gap item, read the content between this heading/bullet and the next peer-level heading/bullet. Extract:

| Sub-field | Detection pattern | Target field |
|---|---|---|
| `existing_code` | Lines starting with `- ` under "Current" / "现状" / "Existing" subsection; also any `file.py:N` patterns | `existing_code[]` |
| `missing_parts` | Bullet list under "Missing" / "缺少" / "需要" subsection | `missing_parts[]` |
| `estimated_effort` | Keywords: small (<2h), medium (2-8h), large (>8h); or Chinese: 小/中/大 | `estimated_effort` |
| `module` | "Module:" label, or infer from file paths in existing_code (e.g. `autoservice/` → module `autoservice`) | `module` |
| `gap_type` | "missing" / "partial" / "outdated" — infer: if existing_code empty → missing; if existing_code present + description says "wrong" / "hardcoded" / "partial" → partial/outdated | `gap_type` |

### Step 3 — Assign canonical IDs

Assign `GAP-NNN` IDs sequentially (starting from 001) in order of appearance:
- P0 items first (in document order)
- Then P1 items
- Then P2 items

This ordering ensures P0 tasks sort to top in task-gen.

Store the mapping `source_id → GAP-NNN` for use by cross-validator and spec-extractor.

### Step 4 — Infer depends_on_gaps

Look for explicit dependency language:
- "depends on", "requires", "needs", "after", "blocked by" followed by another source_id or GAP-NNN
- Emit `depends_on_gaps: [GAP-NNN]`

Leave empty if no dependency language found; cross-validator may infer additional ones.

### Step 5 — Build gap_analysis object

Merge all extracted gaps into:

```yaml
gap_analysis:
  scan_date: "{today}"
  source_type: "ingested"
  source_files: ["{md_path}", ...]

  summary:
    total_gaps: {N}
    by_priority:
      P0: {n0}
      P1: {n1}
      P2: {n2}
    by_gap_type:
      missing: {nm}
      partial: {np}
      outdated: {no}

  gaps:
    - id: GAP-001
      source_id: "{original}"
      source_file: "{basename(md_path)}"
      source_anchor: "{slug}"
      description: "{text}"
      module: "{inferred or empty}"
      priority: P0
      gap_type: missing
      existing_code: []
      missing_parts: []
      estimated_effort: medium
      depends_on_gaps: []
```

## Handling multiple gap MDs

If two or more MDs are classified as `gap`, merge their gaps into one `gap_analysis`:
- Re-assign GAP-NNN IDs across the merged set
- Preserve per-gap `source_file` to keep traceability
- De-duplicate: if two MDs describe the same gap (identical source_id or very similar description), merge into one entry with both source anchors noted in a `notes` field.

## Edge cases

| Situation | Handling |
|---|---|
| Item with no priority tag | Default to P1; add warning "no priority tag on {source_id}" |
| Item with no description text | Skip; add warning "empty description for {source_id}" |
| Priority tag appears multiple times on same item | Take the first occurrence |
| source_id not matching any known pattern | Treat the entire heading text as source_id |
| Circular depends_on_gaps | Detect cycle; mark the last edge as invalid + warning |

## Output

Returns in-memory `gap_analysis` dict. The main SKILL.md orchestrator writes it to disk in Phase 4.

## Verification (acceptance test)

Input: AutoService `docs/plans/2026-04-18-prd-full-journey-gap.md`

Expected output assertions:
- `total_gaps == 17`
- `by_priority.P0 == 6`, `.P1 in [6,7]`, `.P2 in [4,5]`  (allow ±1 for P1/P2 ambiguous items)
- Every gap has `source_id` populated
- Every gap has `source_anchor` populated (non-empty string)
- Every P0 gap has `missing_parts` list with ≥ 1 entry
- `source_type == "ingested"`

See `tests/expected/clear-gap.gap-analysis.yaml` for the expected YAML.
