# design-spec Ingest Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 skill-0-ingest 的 `design-spec` 角色**双产出** `task-hints.yaml`（现状）+ `prd-structure.yaml (partial)`（新增），打通 `brainstorm → spec → skill-0 → skill-2/3` 整合路径。

**Architecture:** 复用 skill-0 现有的 `plan` 角色已经使用的"双 extractor 调度"模式：`design-spec` 改由 spec-extractor（task-hints）+ prd-extractor（modules/nfrs/constraints）共同消费。不改 schema（仅添加 `modules[].source` 和 `modules[].coarse` 两个 optional 非破坏字段）。

**Tech Stack:** Markdown（SKILL.md + lib/*.md）+ YAML（fixtures expected outputs）+ 手动验证（grep / diff）。

**Spec:** [docs/superpowers/specs/2026-04-21-design-spec-ingest-design.md](../specs/2026-04-21-design-spec-ingest-design.md) — 实施期间保持打开。

---

## Conventions

- **Working directory**: `d:\Work\h2os.cloud\prd2impl`
- **Branch**: `feat/design-spec-ingest`（已创建）
- **File-editing**：已有 lib/SKILL.md 用 Edit；新 fixtures / expected 用 Write
- **Lint after each task**：
  ```bash
  # 确保 design-spec 的路径全面（每阶段末跑）
  grep -rn "detected_role: design-spec\|role: design-spec\|role=design-spec" skills/skill-0-ingest/
  ```
- **Commit style**: `feat(skill-0-ingest)` / `test(skill-0-ingest)` / `docs(skill-0-ingest)` / `chore(release)`
- **Task order rationale**：先写 fixtures+expected（Phase A）作为"验收契约"，再改 extractor（Phase B），最后 cross-validator + docs + release。这样 extractor 的实现针对具体目标，不漂移。
- **验证机制**：本插件无自动测试 runner。fixtures 的 expected YAML 是 acceptance criteria。实施完成后，需在一个 fresh Claude CLI session 手动跑 `/ingest-docs <fixture>` 并 diff 产出 vs expected。

---

## File Structure After This Plan

### 新建
```
skills/skill-0-ingest/
  tests/
    fixtures/
      design-spec/                                  # 新子目录
        design-spec-full.md                         # §1-§8 齐全
        design-spec-loose.md                        # 只有 §5/§6
        design-spec-unordered.md                    # §8 在 §3 前
        design-spec-no-numbers.md                   # 纯 heading 无编号
    expected/
      design-spec-full.prd-structure.yaml           # modules + nfrs + constraints
      design-spec-full.task-hints.yaml              # file_changes + steps
      design-spec-loose.task-hints.yaml             # 仅 task-hints（不写 prd-structure）
      design-spec-unordered.prd-structure.yaml
      design-spec-unordered.task-hints.yaml
      design-spec-no-numbers.prd-structure.yaml
      design-spec-no-numbers.task-hints.yaml
```

### 修改
```
skills/skill-0-ingest/
  lib/
    prd-extractor.md                                # 加 design-spec routing
    role-detector.md                                # Produces 列更新
    cross-validator.md                              # 加 design-spec warnings
  SKILL.md                                          # Phase 2b 双派发
  tests/expected/
    clear-spec.prd-structure.yaml                   # 新增（existing fixture 多出一个产出）
package.json / .claude-plugin/plugin.json /
  .claude-plugin/marketplace.json                   # 0.2.0 → 0.2.1
```

### 不改
- prd-structure.yaml / task-hints.yaml 的 schema（除 optional 新字段）
- 其他 extractor、其他角色行为、skill-1/2/3 消费逻辑

---

# Phase A — Fixtures & Expected Outputs（4 tasks）

先定"验收契约"：输入长啥样，输出应该是什么。后续 Phase B extractor 的实现以此为目标。

## Task A.1: `design-spec-full.md` fixture + 两份 expected

**Files:**
- Create: `skills/skill-0-ingest/tests/fixtures/design-spec/design-spec-full.md`
- Create: `skills/skill-0-ingest/tests/expected/design-spec-full.prd-structure.yaml`
- Create: `skills/skill-0-ingest/tests/expected/design-spec-full.task-hints.yaml`

- [ ] **Step 1: Write fixture — a complete brainstorm-template spec**

Write `skills/skill-0-ingest/tests/fixtures/design-spec/design-spec-full.md`:

```markdown
# Rate Limiter Refactor — Design Spec

**Status:** Approved · **Date:** 2026-04-15

## 1. Goal

降低高峰期 API 429 率，从每日 ~3% 降到 <0.3%。

## 2. Current State

当前 limiter 在 `src/middleware/rate_limit.py`，基于 in-memory counter，重启丢状态。

## 3. Design

### 3.1 Redis-backed Counter

新建 `src/middleware/redis_limiter.py`，用 Redis INCR + EXPIRE 做分布式计数。

### 3.2 Sliding Window Algorithm

替换 fixed-window 为 sliding-window log，精度到毫秒。

### 3.3 Fallback Path

Redis 不可用时，回退到 in-memory limiter 并 log warning。

## 4. Behavioral Requirements

- P99 限流判定延迟 < 5ms
- 重启后 60 秒内恢复限流精度
- 向后兼容现有 `@rate_limit` 装饰器签名

## 5. File Changes

### New files
- `src/middleware/redis_limiter.py` — Redis-backed counter
- `src/middleware/sliding_window.py` — algorithm impl

### Modified files
- `src/middleware/rate_limit.py` — delegate to redis_limiter
- `src/config.py` — add REDIS_URL

### Deleted files
- none

## 6. Tests

Fixture suite under `tests/middleware/test_redis_limiter.py` covering redis-up / redis-down / concurrent hits. E2E: run load test at 1000 QPS, observe 429 rate.

## 7. Rollout

1. 实现 redis_limiter + 单测
2. 实现 sliding_window + 单测
3. 改 rate_limit.py delegation + 回归测试
4. 灰度：先 10% 流量，观察 24h
5. 全量切换

## 8. Known Limitations

- Redis 单点若宕机，回退到 in-memory 会丢限流精度（trade-off 选可用性）
- sliding-window 精度依赖 Redis 时钟同步
- 不处理全局限流（只 per-key），per-user 全局限流需另议
```

- [ ] **Step 2: Write expected `prd-structure.yaml`**

Write `skills/skill-0-ingest/tests/expected/design-spec-full.prd-structure.yaml`:

```yaml
# Expected output for tests/fixtures/design-spec/design-spec-full.md
# Verifies prd-extractor's role=design-spec routing.

prd_structure:
  source_files:
    - "tests/fixtures/design-spec/design-spec-full.md"

  modules:
    - id: MOD-01
      name: "Redis-backed Counter"
      description: "新建 src/middleware/redis_limiter.py，用 Redis INCR + EXPIRE 做分布式计数。"
      prd_sections: ["§3.1"]
      source: "design-spec"
      coarse: false

    - id: MOD-02
      name: "Sliding Window Algorithm"
      description: "替换 fixed-window 为 sliding-window log，精度到毫秒。"
      prd_sections: ["§3.2"]
      source: "design-spec"
      coarse: false

    - id: MOD-03
      name: "Fallback Path"
      description: "Redis 不可用时，回退到 in-memory limiter 并 log warning。"
      prd_sections: ["§3.3"]
      source: "design-spec"
      coarse: false

  user_stories: []

  nfrs:
    - id: NFR-01
      category: performance
      requirement: "P99 限流判定延迟 < 5ms"
      prd_ref: "§4"
    - id: NFR-02
      category: general
      requirement: "重启后 60 秒内恢复限流精度"
      prd_ref: "§4"
    - id: NFR-03
      category: compatibility
      requirement: "向后兼容现有 @rate_limit 装饰器签名"
      prd_ref: "§4"

  constraints:
    - id: CON-01
      type: general
      description: "Redis 单点若宕机，回退到 in-memory 会丢限流精度"
      rationale: "trade-off 选可用性"
      prd_ref: "§8"
    - id: CON-02
      type: general
      description: "sliding-window 精度依赖 Redis 时钟同步"
      rationale: "sliding-window 精度依赖 Redis 时钟同步"
      prd_ref: "§8"
    - id: CON-03
      type: general
      description: "不处理全局限流（只 per-key），per-user 全局限流需另议"
      rationale: "不处理全局限流（只 per-key），per-user 全局限流需另议"
      prd_ref: "§8"

  external_deps: []
```

- [ ] **Step 3: Write expected `task-hints.yaml`**

Write `skills/skill-0-ingest/tests/expected/design-spec-full.task-hints.yaml`:

```yaml
# Expected output for tests/fixtures/design-spec/design-spec-full.md
# Verifies spec-extractor still produces task-hints unchanged.

task_hints:
  source_files:
    - "tests/fixtures/design-spec/design-spec-full.md"

  file_changes:
    - path: "src/middleware/redis_limiter.py"
      change_type: create
      purpose: "Redis-backed counter"
      source_anchor: "5-file-changes"
      related_gap_refs: []
    - path: "src/middleware/sliding_window.py"
      change_type: create
      purpose: "algorithm impl"
      source_anchor: "5-file-changes"
      related_gap_refs: []
    - path: "src/middleware/rate_limit.py"
      change_type: modify
      purpose: "delegate to redis_limiter"
      source_anchor: "5-file-changes"
      related_gap_refs: []
    - path: "src/config.py"
      change_type: modify
      purpose: "add REDIS_URL"
      source_anchor: "5-file-changes"
      related_gap_refs: []

  implementation_steps:
    - "实现 redis_limiter + 单测"
    - "实现 sliding_window + 单测"
    - "改 rate_limit.py delegation + 回归测试"
    - "灰度：先 10% 流量，观察 24h"
    - "全量切换"

  non_goals: []

  test_strategy: "Fixture suite under tests/middleware/test_redis_limiter.py covering redis-up / redis-down / concurrent hits. E2E: run load test at 1000 QPS, observe 429 rate."

  risks: []
```

- [ ] **Step 4: Verify all 3 files exist**

```bash
ls skills/skill-0-ingest/tests/fixtures/design-spec/design-spec-full.md
ls skills/skill-0-ingest/tests/expected/design-spec-full.prd-structure.yaml
ls skills/skill-0-ingest/tests/expected/design-spec-full.task-hints.yaml
```

- [ ] **Step 5: Commit**

```bash
git add skills/skill-0-ingest/tests/fixtures/design-spec/design-spec-full.md \
        skills/skill-0-ingest/tests/expected/design-spec-full.prd-structure.yaml \
        skills/skill-0-ingest/tests/expected/design-spec-full.task-hints.yaml
git commit -m "test(skill-0-ingest): add design-spec-full fixture + dual expected"
```

---

## Task A.2: `design-spec-loose.md` fixture + expected (only task-hints)

**Files:**
- Create: `skills/skill-0-ingest/tests/fixtures/design-spec/design-spec-loose.md`
- Create: `skills/skill-0-ingest/tests/expected/design-spec-loose.task-hints.yaml`
- **NO** prd-structure.yaml expected（刻意：松散 spec 触发 "prd_structure all empty → skip" 规则）

- [ ] **Step 1: Write fixture — only §5 + §6**

Write `skills/skill-0-ingest/tests/fixtures/design-spec/design-spec-loose.md`:

```markdown
# Quick Hotfix — Fix Session Cookie Max-Age

## 5. File Changes

### Modified files
- `src/middleware/session.py` — bump cookie max-age from 3600 to 86400

## 6. Tests

Verify cookie header in browser devtools; no automated test needed for 1-line change.
```

- [ ] **Step 2: Write expected task-hints.yaml**

Write `skills/skill-0-ingest/tests/expected/design-spec-loose.task-hints.yaml`:

```yaml
task_hints:
  source_files:
    - "tests/fixtures/design-spec/design-spec-loose.md"

  file_changes:
    - path: "src/middleware/session.py"
      change_type: modify
      purpose: "bump cookie max-age from 3600 to 86400"
      source_anchor: "5-file-changes"
      related_gap_refs: []

  implementation_steps: []
  non_goals: []
  test_strategy: "Verify cookie header in browser devtools; no automated test needed for 1-line change."
  risks: []
```

- [ ] **Step 3: Write NO prd-structure expected**

Instead, write a sibling `.skip` marker file explaining why:

Write `skills/skill-0-ingest/tests/expected/design-spec-loose.prd-structure.yaml.SKIP`:

```
# Intentional: design-spec-loose.md has no §3 Design / §4 Requirements / §8 Constraints sections,
# so prd_structure is empty. Per spec §5, skill-0 should SKIP writing prd-structure.yaml in this case.
# cross-validator prints warning: "design-spec <file>: produced no prd-structure content, output file skipped"
```

- [ ] **Step 4: Verify + commit**

```bash
ls skills/skill-0-ingest/tests/fixtures/design-spec/design-spec-loose.md
ls skills/skill-0-ingest/tests/expected/design-spec-loose.task-hints.yaml
ls skills/skill-0-ingest/tests/expected/design-spec-loose.prd-structure.yaml.SKIP
git add skills/skill-0-ingest/tests/fixtures/design-spec/design-spec-loose.md \
        skills/skill-0-ingest/tests/expected/design-spec-loose.task-hints.yaml \
        skills/skill-0-ingest/tests/expected/design-spec-loose.prd-structure.yaml.SKIP
git commit -m "test(skill-0-ingest): add design-spec-loose fixture — verifies prd-structure skip on empty"
```

---

## Task A.3: `design-spec-unordered.md` fixture + expected

Same content as full (Task A.1) but sections out of order: §8 before §3, §4 at the top.

**Files:**
- Create: `skills/skill-0-ingest/tests/fixtures/design-spec/design-spec-unordered.md`
- Create: `skills/skill-0-ingest/tests/expected/design-spec-unordered.prd-structure.yaml`
- Create: `skills/skill-0-ingest/tests/expected/design-spec-unordered.task-hints.yaml`

- [ ] **Step 1: Write unordered fixture**

Write `skills/skill-0-ingest/tests/fixtures/design-spec/design-spec-unordered.md`. Take the content of `design-spec-full.md` (from A.1) but reorder sections as: §1 → §4 → §8 → §5 → §3 → §6 → §7 → §2. Preserve all content verbatim; only section order differs.

- [ ] **Step 2: Write expected YAMLs**

The expected YAMLs are **byte-equal to design-spec-full's**（因为内容相同，只是源文件 section 顺序不同）—— 可以用 cp 复制后改 source_files 字段：

```bash
cp skills/skill-0-ingest/tests/expected/design-spec-full.prd-structure.yaml \
   skills/skill-0-ingest/tests/expected/design-spec-unordered.prd-structure.yaml
cp skills/skill-0-ingest/tests/expected/design-spec-full.task-hints.yaml \
   skills/skill-0-ingest/tests/expected/design-spec-unordered.task-hints.yaml
```

然后 Edit 两个 expected 文件，把 `source_files` 改为 `- "tests/fixtures/design-spec/design-spec-unordered.md"`。

- [ ] **Step 3: Commit**

```bash
git add skills/skill-0-ingest/tests/fixtures/design-spec/design-spec-unordered.md \
        skills/skill-0-ingest/tests/expected/design-spec-unordered.prd-structure.yaml \
        skills/skill-0-ingest/tests/expected/design-spec-unordered.task-hints.yaml
git commit -m "test(skill-0-ingest): add design-spec-unordered fixture — verifies order-independence"
```

---

## Task A.4: `design-spec-no-numbers.md` fixture + expected

Same content as full but using pure heading text without numeric prefixes (`## Design` instead of `## 3. Design`).

**Files:**
- Create: `skills/skill-0-ingest/tests/fixtures/design-spec/design-spec-no-numbers.md`
- Create: `skills/skill-0-ingest/tests/expected/design-spec-no-numbers.prd-structure.yaml`
- Create: `skills/skill-0-ingest/tests/expected/design-spec-no-numbers.task-hints.yaml`

- [ ] **Step 1: Write no-numbers fixture**

Take A.1 content, rewrite headings:
- `## 1. Goal` → `## Goal`
- `## 2. Current State` → `## Current State`
- `## 3. Design` → `## Design`
- `### 3.1 Redis-backed Counter` → `### Redis-backed Counter`
- `### 3.2 Sliding Window Algorithm` → `### Sliding Window Algorithm`
- `### 3.3 Fallback Path` → `### Fallback Path`
- `## 4. Behavioral Requirements` → `## Behavioral Requirements`
- `## 5. File Changes` → `## File Changes`
- `## 6. Tests` → `## Tests`
- `## 7. Rollout` → `## Rollout`
- `## 8. Known Limitations` → `## Known Limitations`

- [ ] **Step 2: Write expected YAMLs**

Expected YAMLs byte-equal to design-spec-full (content identical), except:
- `source_files` → `design-spec-no-numbers.md`
- `prd_sections` / `prd_ref` 改为用无编号形式（如 `prd_sections: ["Redis-backed Counter"]` 或 `prd_ref: "Behavioral Requirements"`）

对于 prd_sections / prd_ref：按 heading text（去掉 `### ` 前缀，lowercase+hyphen slug）存，如 `redis-backed-counter`。

```bash
cp skills/skill-0-ingest/tests/expected/design-spec-full.prd-structure.yaml \
   skills/skill-0-ingest/tests/expected/design-spec-no-numbers.prd-structure.yaml
cp skills/skill-0-ingest/tests/expected/design-spec-full.task-hints.yaml \
   skills/skill-0-ingest/tests/expected/design-spec-no-numbers.task-hints.yaml
```

然后 Edit 两个 expected：
- source_files 更新
- prd_sections / prd_ref 从 `§3.1` 等改为 slug（具体由 extractor spec 定义；本 task 用 `behavioral-requirements` / `redis-backed-counter` / `known-limitations` 形式）

- [ ] **Step 3: Commit**

```bash
git add skills/skill-0-ingest/tests/fixtures/design-spec/design-spec-no-numbers.md \
        skills/skill-0-ingest/tests/expected/design-spec-no-numbers.prd-structure.yaml \
        skills/skill-0-ingest/tests/expected/design-spec-no-numbers.task-hints.yaml
git commit -m "test(skill-0-ingest): add design-spec-no-numbers fixture — verifies numberless headings"
```

---

# Phase B — Extractor Implementation（3 tasks）

## Task B.1: Extend `prd-extractor.md` with `design-spec` routing

**Files:**
- Modify: `skills/skill-0-ingest/lib/prd-extractor.md`

- [ ] **Step 1: Locate Role routing table**

```bash
grep -n "Role routing" skills/skill-0-ingest/lib/prd-extractor.md
```

Expected 找到类似第 11 行左右的表格。Table rows 当前是 `prd / plan / user-stories`（3 行）。

- [ ] **Step 2: Add `design-spec` row to Role routing table**

Edit：

old_string:
```
| Role | Extracts | Skips |
|------|----------|-------|
| `prd` | modules, user_stories, nfrs, constraints, external_deps | — (full skill-1 logic) |
| `plan` | modules (as phases/milestones), constraints only | user_stories, nfrs, external_deps |
| `user-stories` | user_stories only | modules, nfrs, constraints, external_deps |
```

new_string:
```
| Role | Extracts | Skips |
|------|----------|-------|
| `prd` | modules, user_stories, nfrs, constraints, external_deps | — (full skill-1 logic) |
| `plan` | modules (as phases/milestones), constraints only | user_stories, nfrs, external_deps |
| `user-stories` | user_stories only | modules, nfrs, constraints, external_deps |
| `design-spec` | modules (partial), nfrs, constraints | user_stories, external_deps |
```

- [ ] **Step 3: Add new section "Extraction: role=design-spec"**

在文件末尾追加新 section。先定位文件末尾：

```bash
tail -20 skills/skill-0-ingest/lib/prd-extractor.md
```

用 Edit 在文件末尾之前插入（或直接 append）：

**New section content** (append via Edit):

```markdown

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

**Case 1: §Design section has `###` sub-headings.**
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

### Extracting nfrs

Each bullet (`- ...`) or numbered item (`1. ...`) under the §Requirements section
becomes one NFR:

```yaml
- id: NFR-{N:02d}
  category: <auto-detect>
  requirement: <bullet text, verbatim>
  prd_ref: "§4"   # or slug
```

**Category heuristic** (lowercase requirement text):
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
  description: <bullet text verbatim>
  rationale: <if bullet is "X: Y", the Y part; else same as description>
  prd_ref: "§8"   # or slug
```

**Type heuristic**:
- contains "tech", "tool", "framework", "library" → `technology`
- contains "schedule", "deadline", "date", "deliver" → `schedule`
- else → `general`

### user_stories handling

**Intentionally not extracted.** design-spec focuses on "what/how", not "who/why".
Output `user_stories: []` (empty array) always for design-spec role.

### Graceful degradation

If the document lacks a §Design section entirely: `modules: []`, no error.
If the document lacks §Requirements: `nfrs: []`, no error.
If the document lacks §Known Limitations: `constraints: []`, no error.
If ALL three are absent: emit empty prd_structure; skill-0 will skip writing
`prd-structure.yaml` per Phase 4.1 (see cross-validator for the warning).
```

- [ ] **Step 4: Verify**

```bash
grep -n "design-spec" skills/skill-0-ingest/lib/prd-extractor.md
wc -l skills/skill-0-ingest/lib/prd-extractor.md
```

Expected: 至少 3 处 design-spec 命中（table row + section heading + mentions）；文件从 170 行增加到 ~270 行。

- [ ] **Step 5: Commit**

```bash
git add skills/skill-0-ingest/lib/prd-extractor.md
git commit -m "feat(skill-0-ingest): extend prd-extractor with design-spec routing"
```

---

## Task B.2: Update `role-detector.md` Produces column

**Files:**
- Modify: `skills/skill-0-ingest/lib/role-detector.md`

- [ ] **Step 1: Locate the Roles table**

```bash
grep -n "design-spec" skills/skill-0-ingest/lib/role-detector.md
```

Expected 找到 `| design-spec | task-hints.yaml | ...` 行。

- [ ] **Step 2: Update Produces column**

Edit：

old_string:
```
| `design-spec` | task-hints.yaml | Design spec / 设计方案 with file-change lists and implementation steps |
```

new_string:
```
| `design-spec` | prd-structure.yaml (partial: modules, nfrs, constraints) + task-hints.yaml | Design spec / 设计方案 with file-change lists and implementation steps. After v0.2.1, also extracts §Design modules, §Requirements nfrs, §Known Limitations constraints into a partial prd-structure.yaml. |
```

- [ ] **Step 3: Verify**

```bash
grep "design-spec" skills/skill-0-ingest/lib/role-detector.md
```

Expected: 行里含 `prd-structure.yaml (partial`.

- [ ] **Step 4: Commit**

```bash
git add skills/skill-0-ingest/lib/role-detector.md
git commit -m "feat(skill-0-ingest): role-detector — design-spec produces dual output"
```

---

## Task B.3: SKILL.md Phase 2b — dual dispatch for design-spec

**Files:**
- Modify: `skills/skill-0-ingest/SKILL.md` (Phase 2b, lines ~77-82)

- [ ] **Step 1: Locate Phase 2b design-spec sub-section**

```bash
grep -n "design-spec" skills/skill-0-ingest/SKILL.md
```

Expected: 第 79 行附近。

- [ ] **Step 2: Replace single-dispatch with dual-dispatch**

Edit：

old_string:
```
### 2b. Spec extraction

If any files have `detected_role: design-spec`:
- **Read**: `lib/spec-extractor.md` — follow it exactly.
- Build `task_hints` dict in memory.
- Print: `  Extracted {F} file_changes, {S} steps, {G} non_goals from {files}`

If any files have `detected_role: plan`:
```

new_string:
```
### 2b. Spec extraction

If any files have `detected_role: design-spec`:
- **Read**: `lib/spec-extractor.md` — follow it exactly for task-hints extraction.
- **Read**: `lib/prd-extractor.md §Extraction: role=design-spec` — follow it for modules/nfrs/constraints extraction.
- Build `task_hints` dict in memory (from spec-extractor).
- Build or extend `prd_structure` dict in memory (from prd-extractor, partial: modules/nfrs/constraints only).
- Print: `  Extracted {F} file_changes, {S} steps, {G} non_goals (spec) + {M} modules, {N} nfrs, {C} constraints (design) from {files}`

If any files have `detected_role: plan`:
```

- [ ] **Step 3: Verify**

```bash
grep -A 6 "detected_role: design-spec" skills/skill-0-ingest/SKILL.md
```

Expected: 看到两行 **Read** 指令 + 两行 Build 指令 + 更新的 Print 格式。

- [ ] **Step 4: Commit**

```bash
git add skills/skill-0-ingest/SKILL.md
git commit -m "feat(skill-0-ingest): Phase 2b dual-dispatch design-spec to spec-extractor + prd-extractor"
```

---

# Phase C — Cross-Validator Warnings（1 task）

## Task C.1: Add design-spec warning rules to `cross-validator.md`

**Files:**
- Modify: `skills/skill-0-ingest/lib/cross-validator.md`

- [ ] **Step 1: Read current cross-validator structure**

```bash
head -40 skills/skill-0-ingest/lib/cross-validator.md
grep -n "^## \|^### " skills/skill-0-ingest/lib/cross-validator.md
```

Identify where "rules" / "warnings" are enumerated. Locate a section like `## Warning rules` or `## Rules` or similar.

- [ ] **Step 2: Append new warning rules section**

Append at end of file (use Edit with tail context as old_string, or add a new section):

New section content:

```markdown

## Design-spec warnings (v0.2.1+)

When Phase 2b processes a file with `detected_role: design-spec`, emit these warnings
if the corresponding sections were not found:

| Condition | Warning message (info level) |
|---|---|
| §Design section missing | `design-spec <file>: no §Design/§Architecture section, modules[] empty` |
| §Requirements section missing | `design-spec <file>: no §Behavioral Requirements section, nfrs[] empty` |
| §Known Limitations section missing | `design-spec <file>: no §Known Limitations section, constraints[] empty` |
| §Design present but no `###` sub-headings | `design-spec <file>: §Design has no sub-headings, treated as single coarse module (MOD-01.coarse=true)` |
| `prd_structure` fully empty after extraction | `design-spec <file>: produced no prd-structure content, prd-structure.yaml skipped for this file` |
| Both `prd_structure` and `task_hints` empty | `design-spec <file>: produced no output — file content had no recognized sections. Check file categorization (role-detector may have misclassified).` |

These warnings are **info-level, non-blocking**. They appear in the Phase 3 human review
table so the user can decide whether the extraction was good enough or the source doc
needs editing before re-running /ingest-docs.
```

- [ ] **Step 3: Verify**

```bash
grep -c "design-spec" skills/skill-0-ingest/lib/cross-validator.md
```

Expected: ≥ 6 命中（每条 warning 一处）。

- [ ] **Step 4: Commit**

```bash
git add skills/skill-0-ingest/lib/cross-validator.md
git commit -m "feat(skill-0-ingest): cross-validator — design-spec warning rules"
```

---

# Phase D — Existing Fixture Update + Docs（2 tasks）

## Task D.1: Add expected prd-structure for `clear-design-spec.md`

**Files:**
- Create: `skills/skill-0-ingest/tests/expected/clear-spec.prd-structure.yaml`

**Rationale:** existing fixture [tests/fixtures/role-detection/clear-design-spec.md](../../../skills/skill-0-ingest/tests/fixtures/role-detection/clear-design-spec.md) 会因为新规则多出一个 prd-structure.yaml 产出。其内容：
- §1 Architecture → matches "Architecture" keyword → single coarse module (no `###` sub-headings)
- §4 Non-Goals → not in nfrs keywords → not extracted
- 无 §Requirements / §Known Limitations → nfrs[] / constraints[] 全空

- [ ] **Step 1: Write expected**

Write `skills/skill-0-ingest/tests/expected/clear-spec.prd-structure.yaml`:

```yaml
# Expected output for tests/fixtures/role-detection/clear-design-spec.md (v0.2.1+)
# Verifies design-spec's NEW prd-structure output (previously this fixture only produced task-hints.yaml).

prd_structure:
  source_files:
    - "tests/fixtures/role-detection/clear-design-spec.md"

  modules:
    - id: MOD-01
      name: "Architecture"
      description: "Three-panel shell: TopBar + VerticalRail + Canvas."
      prd_sections: ["§1"]
      source: "design-spec"
      coarse: true   # §1 has no `###` sub-headings

  user_stories: []
  nfrs: []           # fixture has no §Requirements section
  constraints: []    # fixture has no §Known Limitations section
  external_deps: []
```

- [ ] **Step 2: Verify task-hints expected not changed**

```bash
git diff skills/skill-0-ingest/tests/expected/clear-spec.task-hints.yaml
```

Expected: empty diff — task-hints.yaml 产出不变。

- [ ] **Step 3: Commit**

```bash
git add skills/skill-0-ingest/tests/expected/clear-spec.prd-structure.yaml
git commit -m "test(skill-0-ingest): add clear-spec expected prd-structure (coarse module)"
```

---

## Task D.2: Update `using-prd2impl/SKILL.md` to mention design-spec dual output

**Files:**
- Modify: `skills/using-prd2impl/SKILL.md`

- [ ] **Step 1: Locate Data Files Convention table**

```bash
grep -n "Data Files Convention\|skill-0" skills/using-prd2impl/SKILL.md | head -5
```

- [ ] **Step 2: Update the source column of relevant rows**

Edit `| ... | skill-0 only |` 行 → `| ... | skill-0 or skill-1 |` 形式不变，但在 Data Files Convention section **之后**（或 "Isolating Multiple Scopes" section **之前**）加一段说明：

Find unique anchor:

old_string:
```
If YAML files don't exist yet, skills will fall back to reading existing markdown files (backward compatible with hand-written task-status.md).

## Isolating Multiple Scopes with `plans_dir`
```

new_string:
```
If YAML files don't exist yet, skills will fall back to reading existing markdown files (backward compatible with hand-written task-status.md).

### Design-spec dual output (v0.2.1+)

When `/ingest-docs` processes a file classified as `design-spec` (typical output of
`superpowers:brainstorming`), it now produces **two YAML artifacts** instead of one:

- `{plans_dir}/{date}-task-hints.yaml` — file_changes, implementation_steps, test_strategy (unchanged)
- `{plans_dir}/{date}-prd-structure.yaml` — **partial**: modules (from §Design), nfrs (from §Requirements), constraints (from §Known Limitations)

User stories are intentionally not extracted from design-spec — supply a separate
`user-stories` file if needed. See
`docs/superpowers/specs/2026-04-21-design-spec-ingest-design.md` for full mapping.

## Isolating Multiple Scopes with `plans_dir`
```

- [ ] **Step 3: Verify**

```bash
grep -n "Design-spec dual output\|design-spec" skills/using-prd2impl/SKILL.md
```

Expected: 新 section 可见，`design-spec` 出现多次。

- [ ] **Step 4: Commit**

```bash
git add skills/using-prd2impl/SKILL.md
git commit -m "docs(using-prd2impl): document design-spec dual output path"
```

---

# Phase E — Release（1 task）

## Task E.1: Version bump 0.2.0 → 0.2.1

**Files:**
- Modify: `package.json`
- Modify: `.claude-plugin/plugin.json`
- Modify: `.claude-plugin/marketplace.json`

- [ ] **Step 1: Read current version for each file**

```bash
grep -n '"version"' package.json .claude-plugin/plugin.json .claude-plugin/marketplace.json
```

Expected: all show `"version": "0.2.0"`.

- [ ] **Step 2: Edit all three files**

For each:

old_string: `"version": "0.2.0",`
new_string: `"version": "0.2.1",`

(`.claude-plugin/marketplace.json` has `"version": "0.2.0"` without trailing comma — adjust old/new accordingly)

- [ ] **Step 3: Update description in plugin.json + marketplace.json**

Add mention of design-spec dual output to description. Edit:

old_string:
```
"description": "PRD-to-Implementation pipeline: 14-skill workflow from requirement analysis to task execution, progress tracking, and milestone verification. Per-scope plans_dir isolation for parallel milestones.",
```

new_string:
```
"description": "PRD-to-Implementation pipeline: 14-skill workflow from requirement analysis to task execution, progress tracking, and milestone verification. Per-scope plans_dir isolation for parallel milestones. design-spec → prd-structure.yaml ingest bridge for superpowers integration.",
```

(Apply to both `.claude-plugin/plugin.json` AND `.claude-plugin/marketplace.json`.)

- [ ] **Step 4: Verify**

```bash
grep '"version"' package.json .claude-plugin/plugin.json .claude-plugin/marketplace.json
```

Expected: all three show `0.2.1`.

- [ ] **Step 5: Commit**

```bash
git add package.json .claude-plugin/plugin.json .claude-plugin/marketplace.json
git commit -m "chore(release): 0.2.1 — design-spec → prd-structure.yaml ingest bridge"
```

---

# Phase F — Final verification（no task; run at end）

- [ ] **Step 1: Global lint — no regressed behavior signals**

```bash
# Confirm Phase 2b dual dispatch is in place
grep -A 5 "detected_role: design-spec" skills/skill-0-ingest/SKILL.md

# Confirm prd-extractor has design-spec section
grep -c "role=design-spec\|design-spec routing\|role: design-spec" skills/skill-0-ingest/lib/prd-extractor.md

# Confirm role-detector updated
grep "design-spec" skills/skill-0-ingest/lib/role-detector.md | grep "prd-structure"

# Confirm cross-validator has new warnings
grep -c "design-spec" skills/skill-0-ingest/lib/cross-validator.md

# Confirm new fixtures exist
ls skills/skill-0-ingest/tests/fixtures/design-spec/

# Confirm new expected outputs exist
ls skills/skill-0-ingest/tests/expected/design-spec-*.yaml
```

Expected:
- Phase 2b block shows both spec-extractor AND prd-extractor Read instructions
- prd-extractor has ≥ 5 design-spec mentions
- role-detector line includes `prd-structure`
- cross-validator has ≥ 6 design-spec mentions
- 4 new fixtures present
- 7 new expected YAMLs present (4 prd-structure + 3 task-hints, plus 1 SKIP marker)

- [ ] **Step 2: Acceptance tests (manual runtime validation)**

These tests require a fresh Claude CLI session consuming this branch. The test matrix:

- [ ] **T1**: `/ingest-docs skills/skill-0-ingest/tests/fixtures/design-spec/design-spec-full.md` → diff produced YAMLs against `tests/expected/design-spec-full.*` — byte-equal (modulo source_files path)
- [ ] **T2**: `/ingest-docs ...design-spec-loose.md` → only task-hints.yaml produced; prd-structure.yaml NOT written; cross-validator warning present in output
- [ ] **T3**: `/ingest-docs ...design-spec-unordered.md` → output equivalent to T1 (order-independent extraction)
- [ ] **T4**: `/ingest-docs ...design-spec-no-numbers.md` → output equivalent to T1 with slug-based prd_sections/prd_ref
- [ ] **T5**: `/ingest-docs ...design-spec-full.md ...clear-gap.md` → cross-validator runs without fatals; design-spec modules and gap entries coexist
- [ ] **T6 (regression)**: `/ingest-docs ...clear-prd.md ...clear-plan.md ...clear-user-stories.md ...clear-gap.md` → byte-equal to pre-plan outputs (non-design-spec roles unaffected)

- [ ] **Step 3: Final marker commit**

```bash
git commit --allow-empty -m "chore(design-spec-ingest): all phases complete; 11 tasks; acceptance tests pending manual validation"
```

---

# Self-Review

Spec coverage check（对照 `2026-04-21-design-spec-ingest-design.md`）:

| Spec 章节 | 对应 Task |
|---|---|
| §3.1 Architecture (dual dispatch) | B.3 (SKILL.md) + B.1 (prd-extractor) |
| §3.2 修改点表 | A/B/C/D 按表实现 |
| §4.1 Section-to-Field Mapping | B.1 (prd-extractor.md 新 section) |
| §4.2 Heading 识别（兼容模式） | B.1 (Section scanning 子 section) |
| §4.3 modules 抽取规则 | B.1 (Extracting modules 子 section) + A.1/A.4 fixtures 验证 |
| §4.4 nfrs & constraints 抽取规则 | B.1 (Extracting nfrs / constraints 子 section) |
| §4.5 user_stories 处理（故意空） | B.1 (user_stories handling 子 section) + A.1 expected 里 `user_stories: []` |
| §5 Graceful Degradation（7 场景） | B.1 (Graceful degradation 子 section) + C.1 (warnings) + A.2 loose fixture |
| §6.1 Fixture 组（4 个） | A.1, A.2, A.3, A.4 |
| §6.2 T1-T6 Acceptance | Phase F Step 2 勾选项 |
| §6.3 Cross-validation 断言 | C.1 |
| §7 Rollout（4-6 commits） | 实际 10 code commits + 1 marker = 11 tasks |
| §8.1-8.6 Known Limitations | Spec 已注，plan 无需实现 |

**Placeholder scan:** 无 TBD/TODO/如需。Task E.1 的 description update 对 plugin.json 和 marketplace.json 都明确标注。

**Type consistency:** `prd_sections` / `prd_ref` / `source: "design-spec"` / `coarse: bool` 全 plan 一致；`modules[]` / `nfrs[]` / `constraints[]` 用法一致。

---

# Execution Handoff

Plan complete. 保存在 `docs/superpowers/plans/2026-04-21-design-spec-ingest.md`.

**总任务数**：11 tasks（Phase A×4 + B×3 + C×1 + D×2 + E×1） + Phase F 手动验证（无 commit）

**预估工时**（markdown 编辑为主，不含运行时测试）：2-3 小时

两种执行选项：

1. **Subagent-Driven（推荐）** — 每 task 派一个 fresh subagent，我在 task 间 review。快速迭代、context 轻。
2. **Inline Execution** — 本会话顺序执行，按 phase boundary checkpoint review。

你选哪个？
