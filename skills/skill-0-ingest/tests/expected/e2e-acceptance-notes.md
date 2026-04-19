# E2E Acceptance Test — AutoService Real MDs

## Input files

```
/ingest-docs \
  docs/plans/2026-04-18-prd-full-journey-gap.md \
  docs/superpowers/specs/2026-04-18-admin-portal-web-layout-design.md
```

## Phase 1 — Role detection expectations

| File | Expected role | Expected confidence | Method | Key signals |
|------|--------------|--------------------|----|-------------|
| `2026-04-18-prd-full-journey-gap.md` | gap | ≥ 70 | heuristic | filename `*-gap.md` (30pts) + H1 "Gap 分析" (30pts) + P0/P1/P2 structural (20pts) |
| `2026-04-18-admin-portal-web-layout-design.md` | design-spec | ≥ 70 | heuristic | filename `*-design.md` (30pts) + H1 "Web Layout Redesign" (30pts) + "文件改动" section (10pts) + "实施顺序" section (10pts) |

## Phase 2a — Gap extraction expectations

Input: `2026-04-18-prd-full-journey-gap.md`

**Gap item pattern in this file**: `#### A-① 缺"注册接入"独立步骤 · P0`
- Heading level: H4 (`####`)
- source_id pattern: `A-①`, `B-⑦`, `C-⑫` etc. (letter-circled-number)
- Priority separator: `· P0` (middle dot, not `[P0]`)

**gap-extractor must handle**: Priority tag after `·` or `·` in addition to `[P0]`.

Expected counts:
- `total_gaps`: 17
- `by_priority.P0`: 6 (A-①, A-②, A-③, B-⑦, C-⑫, C-⑭)
- `by_priority.P1`: 6 (B-⑧, B-⑨, B-⑪, C-⑮, C-⑯, S1/S3 from table)
- `by_priority.P2`: 5 (A-④, A-⑤, A-⑥, B-⑩, C-⑬)

Note: Table rows (S1–S4) at end of file also contain gap items. Gap-extractor should detect
these as Pattern C (table rows). S2 and S4 are P0; S1 and S3 are P1.

All gaps must have:
- `source_id`: non-empty (e.g. "A-①")
- `source_anchor`: non-empty heading slug
- `source_file`: "2026-04-18-prd-full-journey-gap.md"
- `source_type`: "ingested"

## Phase 2b — Spec extraction expectations

Input: `2026-04-18-admin-portal-web-layout-design.md`

**Section heading pattern**: `## 6. 文件改动` (Chinese, numbered)
- spec-extractor must match numbered Chinese headings like `## N. 文件改动`

**Sub-sections**: `### 新增` (New files), `### 修改` (Modified files), `### 不改` (No-change files)
- spec-extractor must map: 新增 → create, 修改 → modify, 不改 → no-change

Expected counts:
- `len(file_changes) >= 8`
- `len(implementation_steps) >= 10` (section `## 9. 实施顺序`)
- `len(non_goals) >= 3` (section `## 2. 目标与非目标` subsection `### 非目标` or `## 11. 未来路径`)
- `test_strategy` non-null (section `## 7. 测试策略`)
- `len(risks) >= 1` (section `## 10. 开放风险`)

## Phase 3 — Cross-validation expectations

Expected warnings (non-fatal):
- Rule 2: Several P0 gaps may have no spec file_change coverage (C-⑫, C-⑭ are in gap MD
  but spec only covers admin-portal front-end; those are backend/channel gaps)
- Rule 1: Some file_changes may have empty related_gap_refs initially (cross-validator backfills)

Expected fatals: none (no non_goal / file_change conflicts expected for these files).

## Phase 4 — Output expectations

```
docs/plans/2026-04-19-gap-analysis.yaml      ← 17 gaps, P0=6/P1=6/P2=5
docs/plans/2026-04-19-prd-structure.yaml     ← possibly empty (no prd/plan MD provided)
docs/plans/2026-04-19-task-hints.yaml        ← ≥8 file_changes, ≥10 steps
```

## Downstream: /task-gen with task-hints

After running `/task-gen`:
- tasks.yaml `deliverables` must come from `task-hints.file_changes` (not inferred from gap text)
- tasks.yaml `depends_on` must reflect `implementation_steps.depends_on_steps`
- any task whose deliverable matches a non_goal keyword must be rejected with warning

## Known adaptation notes for extractors

### gap-extractor

Add to Step 1 detection patterns:
- Priority tag after middle dot: `· P0` / `· P1` / `· P2` (Unicode U+00B7)
- Chinese circled numbers: ①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰ as part of source_id
- H4 heading level (`####`) for gap items (not just H3)

### spec-extractor

Add to Step 1 section detection:
- Numbered Chinese headings: `## N. 文件改动` → File Changes
- Numbered Chinese headings: `## N. 实施顺序` → Implementation Steps
- Sub-section `### 不改` → `change_type: no-change`
- Non-goals may appear in `## 2. 目标与非目标` → `### 非目标` subsection

These adaptations are **additive** — they extend existing pattern lists without breaking English patterns.
