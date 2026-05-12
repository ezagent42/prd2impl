# spec-extractor — Phase 2b of skill-0-ingest

Extract structured design decisions from a Markdown document classified as `role: design-spec` or `role: plan`.
Produces the `task_hints` object that becomes `task-hints.yaml`.

## Input

- One or more MD files with `detected_role: design-spec` or `detected_role: plan` from role-detector.

## Extraction steps

## Phase 0 — Plan-format detection (role=plan only)

**Triggers when**: the calling skill (skill-0-ingest Phase 2b plan branch) passes in a file with `detected_role: plan`.

**Step 0.1**: Check whether the file is writing-plans-format. Scan the first 30 lines for the literal substring `REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development` OR `REQUIRED SUB-SKILL: Use superpowers:executing-plans`. (This is the same signature role-detector Signal 0 uses; both checks must stay in sync. If role-detector classified the file as `plan` via Signal 0, this check necessarily passes — the redundancy is intentional and cheap.)

**Step 0.2** (match): Delegate to `lib/plan-parser.md`. Pass the file bytes; receive the parsed `tasks[]` list. Then:
- Set `task_hints.tasks` = the parsed list.
- For each entry in `task_hints.tasks`, populate `source_plan_path` with the input file's repo-relative path (the parser leaves this null — only the caller knows the path).
- Set `task_hints.source_files = [path]` and `task_hints.source_type = "ingested"`.
- SKIP Steps 1-7 below. file_changes / implementation_steps / non_goals / test_strategy / risks are NOT extracted in the plan-passthrough path — the rich data lives inside `task_hints.tasks[].files` and `.steps` instead.

**Step 0.3** (no match): Continue with the legacy flow (Steps 1-7 below). This preserves backward compatibility with hand-written plan-shaped markdown that does NOT follow writing-plans format.

---

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

## Plan-format passthrough (cross-reference)

When the caller's `detected_role` is `plan` and Phase 0 above matches the writing-plans signature, ALL `tasks[]` extraction happens in `lib/plan-parser.md` — this file is a no-op for steps / file_changes / non_goals / test_strategy / risks. The output is `task_hints.tasks[]` (rich per-plan-task hierarchy with files / steps), not the legacy `task_hints.file_changes` / `task_hints.implementation_steps` layout.

Legacy plans without the writing-plans header still flow through Steps 1-7 — they get the legacy layout, no `tasks[]` field.

Acceptance test for the plan-passthrough path: applying spec-extractor (Phase 0) to `tests/fixtures/plan-passthrough/admin-v2-p1-cr-data-layer.md` must produce a `task_hints` object that, when serialized, equals `tests/expected/admin-v2-p1.task-hints.yaml` byte-for-byte. Regenerate the expected fixture via `python3 tests/fixtures/plan-passthrough/_gen_expected.py`.
