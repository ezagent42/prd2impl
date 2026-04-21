# spec-extractor — Phase 2b of skill-0-ingest

Extract structured design decisions from a Markdown document classified as `role: design-spec`.
Produces the `task_hints` object that becomes `task-hints.yaml`.

## Input

- One or more MD files with `detected_role: design-spec` from role-detector.

## Extraction steps

### Step 1 — Locate section anchors

Scan the document for section headings that match these patterns (case-insensitive, English or Chinese):

| Section type | Heading patterns | Maps to field |
|---|---|---|
| File changes | "File Changes", "Files Changed", "文件变更", "Changed Files", "文件改动", `## N. 文件改动` | `file_changes[]` |
| Implementation steps / order | "Implementation Steps", "Implementation Order", "实施步骤", "实施顺序", "Steps", "Rollout", "Phasing", "灰度", "阶段", `## N. 实施顺序` | `implementation_steps[]` |
| Non-goals | "Non-Goals", "Non Goals", "Out of Scope", "非目标", "不做", "### 非目标" (subsection of 目标与非目标) | `non_goals[]` |
| Test strategy / testing | "Testing", "Test Strategy", "测试策略", "Tests" | `test_strategy` |
| Risks / open questions | "Risks", "Open Questions", "Open Risks", "风险", "开放风险", "待决事项" | `risks[]` |

**Numbered section matching**: Also match headings like `## 6. 文件改动` or `## 9. 实施顺序` — strip the leading number and dot before matching keywords.

Record the heading slug as `source_anchor` for each section.

### Step 2 — Extract file_changes

Within the File Changes section, recognize three sub-formats:

**Format A — Markdown table**:

```markdown
| Path | Change | Purpose |
|------|--------|---------|
| `src/AdminShell.tsx` | create | root layout |
| `src/App.tsx` | modify | wire AdminShell |
```

**Format B — Sub-headed lists** ("### New files", "### Modified files", "### Deleted files", or Chinese equivalents):

Sub-heading → change_type mapping:
| Sub-heading | change_type |
|---|---|
| New files / 新增 / 新文件 | `create` |
| Modified files / 修改 / 修改文件 | `modify` |
| Deleted files / 删除 | `delete` |
| No-change files / 不改 / 保持不变 | `no-change` |

```markdown
### New files    (or: ### 新增)
- `src/AdminShell.tsx` — root layout

### Modified files    (or: ### 修改)
- `src/App.tsx` — wire AdminShell

### No-change files    (or: ### 不改)
- `src/tokens.css` — design system unchanged
```

**Format C — Plain bullet list with inline change type**:

```markdown
- [NEW] `src/AdminShell.tsx` — root layout
- [MODIFY] `src/App.tsx` — wire AdminShell
```

For each file entry, extract:
- `path`: the file path (strip backticks, trim whitespace)
- `change_type`: `create` | `modify` | `delete` | `no-change` — infer from sub-header name or `[NEW]`/`[MODIFY]`/`[DELETE]`/`[NO-CHANGE]` tag; if none, default to `modify`
- `purpose`: text after `—` or `:`
- `source_anchor`: heading slug of the File Changes section
- `related_gap_refs`: initially `[]` (populated by cross-validator)

### Step 3 — Extract implementation_steps

Within the Implementation Steps section, recognize:

**Format A — Numbered list** (most common):

```markdown
1. Build AdminShell + CSS grid
2. Wire App.tsx → AdminShell
   depends on: step 1
```

**Format B — Table**:

```markdown
| Step | Description | Depends on |
|------|------------|------------|
| 1 | Build shell | — |
| 2 | Wire App.tsx | Step 1 |
```

For each step:
- `step`: integer (1-based)
- `description`: the step text
- `depends_on_steps`: parsed from "depends on: N" or table column; empty list if not stated
- `touches_files`: extract any `path/file.ext` patterns mentioned in the step text that match paths from `file_changes`; if no match, leave empty
- `source_anchor`: heading slug of the Implementation Steps section

### Step 4 — Extract non_goals

Within the Non-Goals section, each bullet becomes one string in `non_goals[]`.

Remove leading `- ` and normalize whitespace. No further structure needed.

### Step 5 — Extract test_strategy

Within the Testing section, detect:

**preserved_testids**: Lines matching `data-testid:`, or bullet items containing backtick-wrapped identifiers near words "preserved", "keep", "must not break", "existing".

**new_tests**: Lines or bullets listing new test file names (pattern `*.test.tsx`, `test_*.py`, `*_test.go`, etc.) with optional description after `—` or `:`.

**e2e_delta**: First sentence/bullet mentioning "E2E" or "end-to-end" — capture verbatim.

If the section is absent, set `test_strategy: null`.

### Step 6 — Extract risks

Within the Risks section, each item becomes a `{risk, mitigation}` pair:

**Format A — Bullet with mitigation**:
```markdown
- Risk: selector regression — Mitigation: baseline test run first
```

**Format B — Sub-bullets**:
```markdown
- Selector regression
  - Mitigation: baseline test run first
```

**Format C — Plain bullet** (no mitigation):
```markdown
- CSS grid conflicts with existing tab styles
```
→ `{risk: "CSS grid conflicts...", mitigation: null}`

### Step 7 — Build task_hints object

```yaml
task_hints:
  source_files: ["{md_path}"]
  file_changes: [...]         # from step 2
  implementation_steps: [...] # from step 3
  non_goals: [...]            # from step 4
  test_strategy: {...}        # from step 5 (null if absent)
  risks: [...]                # from step 6 ([] if absent)
```

## Handling multiple spec MDs

If two or more MDs are classified as `design-spec`, merge their `task_hints`:
- Concatenate `file_changes` lists; de-duplicate by `path` (keep last occurrence if same path appears twice).
- Concatenate `implementation_steps`; re-number step IDs sequentially across both docs. Preserve intra-doc `depends_on_steps` references; cross-doc dependencies not inferred (user adds manually).
- Merge `non_goals` (union, de-duplicate by string equality).
- Merge `test_strategy` sub-fields (union lists; last `e2e_delta` wins if both non-null).
- Concatenate `risks`.

## Edge cases

| Situation | Handling |
|---|---|
| File Changes section absent | `file_changes: []` + warning "no file_changes section found in {path}" |
| Implementation Steps absent | `implementation_steps: []` + warning |
| A file path in implementation_steps not in file_changes | Include in `touches_files` as-is; cross-validator flags it as "step references undeclared file" |
| Non-goals section absent | `non_goals: []` (not a warning — optional) |
| Step number not parseable as int | Auto-assign sequential integer from order in document |

## Output

Returns in-memory `task_hints` dict. The main SKILL.md orchestrator writes it to disk in Phase 4.

## Verification (acceptance test)

Input: AutoService `docs/superpowers/specs/2026-04-18-admin-portal-web-layout-design.md`

Expected output assertions:
- `len(file_changes) >= 8`
- `len(implementation_steps) >= 10`
- `len(non_goals) >= 3`
- `test_strategy` is not null; `preserved_testids` non-empty
- `len(risks) >= 1`

See `tests/expected/clear-spec.task-hints.yaml` for the expected YAML.
