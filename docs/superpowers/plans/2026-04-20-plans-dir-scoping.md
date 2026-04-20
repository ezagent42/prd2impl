# plans_dir 目录分域 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 prd2impl 插件支持"一个项目多个 plans_dir"：通过在 `project.yaml` 加 `plans_dir` 字段 + 新增 `--plans-dir` CLI flag + 共享的路径解析逻辑，让不同作用域（里程碑/迭代）的产物落到不同子目录，彻底消除同日跑两套产物的冲突。

**Architecture:** 每个 skill 在构造产物路径前，调用统一的 `resolve_plans_dir()` 逻辑（优先级：CLI > project.yaml > 默认 `docs/plans/`）。文件名约定不变，只改所在目录。

**Tech Stack:** Markdown（SKILL.md 编辑为主）+ YAML（project.yaml schema）+ 手工验证 + grep/ls 基础工具。

**Spec:** [docs/superpowers/specs/2026-04-20-plans-dir-scoping-design.md](../specs/2026-04-20-plans-dir-scoping-design.md) — 实施时保持打开。

---

## Conventions Used in This Plan

- **Working directory**: `D:/Work/h2os.cloud/prd2impl/`（本插件仓库）。所有相对路径从此处起算。
- **Edit vs Write**: 修改已有 SKILL.md 用 Edit 工具（精准保留上下文）；新文件用 Write
- **Lint command**: 贯穿所有阶段的检查命令：`grep -rn "docs/plans/" skills/ | grep -v "plans_dir" | grep -v "docs/plans/project.yaml"` — 阶段 C 末期这条应返回 0 行
- **Commit style**: `feat(<scope>)` / `chore(<scope>)` / `refactor(<scope>)`。Scopes: `plans-dir-infra`, `plans-dir-writers`, `plans-dir-readers`, `plans-dir-cleanup`
- **After each task**: 跑一次 lint 命令确认没引入新硬编码；通过后 commit
- **不修改**：文件命名约定（仍然是 `{date}-<artifact>.yaml`）、`.artifacts/` 机制、dev-loop-skills 插件
- **两个源引用**：审计报告的行号（见 spec §5.3）在当前 SKILL.md 版本下精确；如代码漂移可用 grep 定位

---

## File Structure After This Plan

### 新建文件

```
lib/
  plans-dir-resolver.md                    # 共享路径解析规范
```

### 修改文件

```
skills/
  skill-0-ingest/SKILL.md                  # Phase 4.1 写路径 + 删 -v2/-v3 逻辑
  skill-1-prd-analyze/SKILL.md             # Step 5 写路径
  skill-2-gap-scan/SKILL.md                # Step 1 读 glob + Step 4 写路径
  skill-3-task-gen/SKILL.md                # Step 1 读 globs + Step 7 写路径
  skill-4-plan-schedule/SKILL.md           # Step 1 读 + Step 5/8 写（含硬编码 task-status.md 等）
  skill-4-plan-schedule/templates/project.yaml  # 新增 plans_dir 字段
  skill-5-start-task/SKILL.md              # 次扫：task-status.md / tasks.yaml 引用
  skill-6-continue-task/SKILL.md           # 次扫
  skill-7-next-task/SKILL.md               # 次扫
  skill-8-batch-dispatch/SKILL.md          # 次扫
  skill-9-task-status/SKILL.md             # Step 1 读
  skill-10-smoke-test/SKILL.md             # Step 1 读
  skill-11-retro/SKILL.md                  # Step 1 读 + Step 5 写
  skill-12-contract-check/SKILL.md         # 次扫
  skill-13-autorun/SKILL.md                # 次扫
  using-prd2impl/SKILL.md                  # README 加 "plans_dir usage" 小节
README.md                                  # 如果提到 docs/plans/ 也更新
```

### 不改动

- `.artifacts/registry.json` 及 `.artifacts/` 相关逻辑（见 spec §8 Limitation 1）
- skills 5/6/7/8/12/13 的核心执行逻辑（只改路径构造引用）
- 所有 `schemas/` 和 `tests/fixtures/`（命名约定不变）

---

# Phase A — 基础设施（3 tasks）

此阶段不改任何 skill 的写/读行为，只准备好"可引用的共享规范"和"可校验的 lint 命令"。跑完 Phase A 后插件行为与旧版完全一致。

## Task A.1: 创建 `lib/plans-dir-resolver.md`

**Files:**
- Create: `lib/plans-dir-resolver.md`

**Step 1：检查 lib 目录是否存在**

```bash
ls lib/ 2>/dev/null || echo "需要创建 lib/"
```

若不存在则创建：

```bash
mkdir -p lib
```

**Step 2：Write 新文件 `lib/plans-dir-resolver.md`**

```markdown
# plans-dir-resolver

Shared path resolution logic for prd2impl skills. All skills that read/write
artifacts under `docs/plans/` must call this resolution before constructing
paths.

## Resolution Order

```
resolve_plans_dir():
  1. if CLI flag --plans-dir <path> was passed:         return <path>
  2. elif project.yaml has `plans_dir` field (non-empty): return project.yaml.plans_dir
  3. else:                                               return "docs/plans/"
```

After resolution, if the resolved directory does not exist, `mkdir -p` it
silently (no error, no prompt).

## Legality Checks

Run these checks on the resolved path in order; reject with error message if
any fails:

1. **Normalize**: strip trailing `/`, resolve `./`, convert `\` → `/` (Windows)
2. **Absolute path check**: if starts with `/` or matches `[A-Za-z]:` →
   error: `"plans_dir must be a repository-relative path. Got: '<input>'"`
3. **`..` segment check**: after split by `/`, if any segment is `..` →
   error: `"plans_dir must not contain '..' segments. Got: '<input>'"`
4. **Empty string**: treat as default `docs/plans/` (no error)

## Usage in SKILL.md files

When a skill constructs an output path, use `{plans_dir}` as the placeholder:

- Before: `docs/plans/{date}-tasks.yaml`
- After:  `{plans_dir}/{date}-tasks.yaml`

Where `{plans_dir}` is the return of `resolve_plans_dir()` at skill invocation
time.

## Examples

| Input | Resolved |
|-------|----------|
| CLI `--plans-dir docs/plans/m2`, no project.yaml | `docs/plans/m2` |
| No CLI, `project.yaml.plans_dir: docs/plans/m2` | `docs/plans/m2` |
| No CLI, no project.yaml.plans_dir | `docs/plans/` |
| CLI `--plans-dir /tmp/plans` | ERROR (absolute path) |
| CLI `--plans-dir ../plans` | ERROR (`..` segment) |
| CLI `--plans-dir "docs/plans/m2/"` | `docs/plans/m2` (trailing slash stripped) |
```

**Step 3：Verify 文件就位**

```bash
test -f lib/plans-dir-resolver.md && echo "OK"
```

Expected: `OK`

**Step 4：Commit**

```bash
git add lib/plans-dir-resolver.md
git commit -m "chore(plans-dir-infra): add shared plans_dir resolver spec"
```

---

## Task A.2: 在 `project.yaml` template 中加入 `plans_dir` 字段

**Files:**
- Modify: `skills/skill-4-plan-schedule/templates/project.yaml:44-45`

**Step 1：Read 现状**

当前模板在 line 43-45:
```yaml
  # Work parameters
  work_hours_per_day: 8
  parallel_capacity: 1  # Number of lines that work simultaneously
```

**Step 2：在 `work_hours_per_day` 之前插入 plans_dir 字段**

Edit `skills/skill-4-plan-schedule/templates/project.yaml`:

old_string:
```
  # Work parameters
  work_hours_per_day: 8
  parallel_capacity: 1  # Number of lines that work simultaneously
```

new_string:
```
  # Artifact location (optional)
  # Where prd2impl artifacts (tasks.yaml, task-status.md, etc.) are written/read.
  # Default: "docs/plans/" (project root). Use a subdirectory to isolate
  # milestones/scopes when multiple run in parallel on the same project.
  # plans_dir: docs/plans/m2

  # Work parameters
  work_hours_per_day: 8
  parallel_capacity: 1  # Number of lines that work simultaneously
```

**Step 3：Verify**

```bash
grep -A 1 "plans_dir" skills/skill-4-plan-schedule/templates/project.yaml
```

Expected: 显示 plans_dir 注释 + 被注释掉的示例行。

**Step 4：Commit**

```bash
git add skills/skill-4-plan-schedule/templates/project.yaml
git commit -m "feat(plans-dir-infra): add plans_dir field to project.yaml template"
```

---

## Task A.3: 在 `using-prd2impl/SKILL.md` 添加 plans_dir 使用说明

**Files:**
- Modify: `skills/using-prd2impl/SKILL.md` (在合适位置添加一段)

**Step 1：Read 现状，找插入位置**

```bash
grep -n "^## " skills/using-prd2impl/SKILL.md
```

选一个合适的 section 末尾插入。若有 "Data Files Convention" / "Conventions" 类似段落，插其后。否则插到文件末尾。

**Step 2：Edit 添加新 section**

在选定位置之后插入：

```markdown
## Isolating Multiple Scopes with `plans_dir`

When running multiple milestones/projects in parallel on the same repo
(e.g. finishing M1 while planning M2), set a per-scope `plans_dir` to avoid
artifact collision.

### Quick setup

```yaml
# docs/plans/project.yaml
project:
  # ... other fields ...
  plans_dir: docs/plans/m2   # new scope goes here
```

After this, all prd2impl commands (`/ingest-docs`, `/task-gen`,
`/task-status`, etc.) read/write under `docs/plans/m2/` instead of the root
`docs/plans/` directory.

### Ad-hoc override

Pass `--plans-dir <path>` to any command to override the config for that
invocation:

```bash
/ingest-docs --plans-dir docs/plans/m2 a.md b.md
```

Priority: CLI flag > project.yaml > default (`docs/plans/`).

### Migrating an existing project

```bash
mkdir docs/plans/m1
mv docs/plans/*.yaml docs/plans/*.md docs/plans/m1/
# then in project.yaml:
#   plans_dir: docs/plans/m1
```

### Limitations

- `plans_dir` must be repo-relative; absolute paths and `..` segments rejected
- `.artifacts/` directory is shared across all plans_dir (intentional)
- See `lib/plans-dir-resolver.md` for full spec
```

**Step 3：Verify**

```bash
grep -n "plans_dir" skills/using-prd2impl/SKILL.md
```

Expected: 新 section 可见。

**Step 4：Commit**

```bash
git add skills/using-prd2impl/SKILL.md
git commit -m "docs(plans-dir-infra): document plans_dir usage in using-prd2impl"
```

---

# Phase B — 写端迁移（7 tasks）

此阶段改写所有"产物写出"路径。每个 task 独立一个 skill。

每个 task 的**通用模式**：
1. Grep 定位当前 `docs/plans/` 硬编码处
2. Edit 替换为 `{plans_dir}/...`
3. 在该 skill 的 "Execution Flow" 开头加一句"Resolve `{plans_dir}` per `lib/plans-dir-resolver.md` before any path construction."
4. Verify: grep 检查该 skill 的写路径全部改完
5. Commit

## Task B.1: skill-0-ingest 写端 + 删除 -v2/-v3 冲突逻辑

**Files:**
- Modify: `skills/skill-0-ingest/SKILL.md` (Phase 4.1 写路径 + 删除 same-day collision 逻辑)

**Step 1：定位当前写路径硬编码**

```bash
grep -n "docs/plans/" skills/skill-0-ingest/SKILL.md
```

根据审计，关键行在 Phase 4.1 (line 131-133) 的输出路径列表。

**Step 2：在 Phase 4 顶部加 resolver 引用**

Edit，找到 `## Phase 4 · Write + Summary` 这行，在其下加一行提示：

old_string:
```
## Phase 4 · Write + Summary

### 4.1 Determine output paths
```

new_string:
```
## Phase 4 · Write + Summary

> **Path resolution**: Before constructing any output path, resolve `{plans_dir}` per `lib/plans-dir-resolver.md`. All paths below use `{plans_dir}` as the base directory.

### 4.1 Determine output paths
```

**Step 3：替换 Phase 4.1 的路径模板**

Edit：

old_string:
```
docs/plans/{date}-gap-analysis.yaml      (if gap_analysis populated)
docs/plans/{date}-prd-structure.yaml     (if prd_structure populated)
docs/plans/{date}-task-hints.yaml        (if task_hints populated)
```

new_string:
```
{plans_dir}/{date}-gap-analysis.yaml      (if gap_analysis populated)
{plans_dir}/{date}-prd-structure.yaml     (if prd_structure populated)
{plans_dir}/{date}-task-hints.yaml        (if task_hints populated)
```

**Step 4：删除 -v2/-v3 冲突逻辑**

Edit，找到以下内容并替换：

old_string:
```
If a file already exists with today's date: append `-v2` (then `-v3`, etc.) to avoid overwrite.
```

new_string:
```
If a file already exists at the target path: print a diff summary line (informational, non-blocking) and overwrite. Example: `"Overwriting {path} (12 modules → 13 modules, 1 constraint removed)"`. After overwrite, print a downstream-invalidation hint: `"Note: tasks.yaml for this plans_dir already exists and may now be inconsistent. Re-run /task-gen to regenerate."`. Users who want to keep both versions should run with a different `--plans-dir`.
```

**Step 5：更新 "Same-day output file collision" 行的错误处理表**

Edit，找到：
```
| Same-day output file collision | Append `-v2` suffix |
```

替换为：
```
| Same-day re-run of /ingest-docs | Overwrite with diff-summary log (no suffix; use different --plans-dir for coexistence) |
```

**Step 6：Verify**

```bash
grep -n "docs/plans/" skills/skill-0-ingest/SKILL.md | grep -v "project.yaml"
```

Expected: 0 hits（除了可能保留的 project.yaml 引用；其他都应改为 `{plans_dir}`）

```bash
grep -n "\-v2\|\-v3" skills/skill-0-ingest/SKILL.md
```

Expected: 0 hits（-v2/-v3 冲突逻辑已删）

**Step 7：Commit**

```bash
git add skills/skill-0-ingest/SKILL.md
git commit -m "refactor(plans-dir-writers): skill-0-ingest uses plans_dir; remove -v2/-v3 logic"
```

---

## Task B.2: skill-1-prd-analyze 写端

**Files:**
- Modify: `skills/skill-1-prd-analyze/SKILL.md` (Step 5 写路径)

**Step 1：定位**

```bash
grep -n "docs/plans/" skills/skill-1-prd-analyze/SKILL.md
```

Expected 至少 1 条，对应 Step 5 output path。

**Step 2：在 Execution Flow 顶部加 resolver 引用**

找到 `## Execution Flow` (或等效的第一个主流程 heading)，在其下加一行：

```markdown
> **Path resolution**: Before constructing any output path, resolve `{plans_dir}` per `lib/plans-dir-resolver.md`. All `docs/plans/` references below are relative to that resolved directory.
```

**Step 3：替换写路径**

Edit，把 Step 5 的路径：

old_string 示例（根据实际行调整）：
```
Write `docs/plans/{date}-prd-structure.yaml`
```

new_string:
```
Write `{plans_dir}/{date}-prd-structure.yaml`
```

**Step 4：Verify**

```bash
grep -n "docs/plans/" skills/skill-1-prd-analyze/SKILL.md
```

Expected: 0 hits（或只剩 project.yaml 引用）

**Step 5：Commit**

```bash
git add skills/skill-1-prd-analyze/SKILL.md
git commit -m "refactor(plans-dir-writers): skill-1-prd-analyze uses plans_dir"
```

---

## Task B.3: skill-2-gap-scan 写端（读端留到 Phase C）

**Files:**
- Modify: `skills/skill-2-gap-scan/SKILL.md` (Step 4 写路径，不动 Step 1 读)

**Step 1：定位**

```bash
grep -n "docs/plans/" skills/skill-2-gap-scan/SKILL.md
```

审计记录 Step 1 read at line ~31, Step 4 write at line ~144。**本 task 只改 write**。

**Step 2：在 Execution Flow 顶部加 resolver 引用**

同 B.2 Step 2。

**Step 3：替换 Step 4 写路径**

Edit：

old_string（根据实际行调整，典型形如）：
```
Write `docs/plans/{date}-gap-analysis.yaml`
```

new_string:
```
Write `{plans_dir}/{date}-gap-analysis.yaml`
```

**Step 4：Verify — Step 1 读路径暂时仍硬编码（后续 Phase C 再处理）**

```bash
grep -n "docs/plans/" skills/skill-2-gap-scan/SKILL.md
```

Expected: 至少还能看到 Step 1 的读 glob（那是下一阶段任务）。写路径 0 hits。

**Step 5：Commit**

```bash
git add skills/skill-2-gap-scan/SKILL.md
git commit -m "refactor(plans-dir-writers): skill-2-gap-scan write path uses plans_dir"
```

---

## Task B.4: skill-3-task-gen 写端（读端留到 Phase C）

**Files:**
- Modify: `skills/skill-3-task-gen/SKILL.md` (Step 7 写路径 195-196)

**Step 1：定位**

```bash
grep -n "docs/plans/" skills/skill-3-task-gen/SKILL.md
```

审计：Step 1 read at 32-33, Step 7 write at 195-196。

**Step 2：在 Execution Flow 顶部加 resolver 引用**

同 B.2 Step 2。

**Step 3：替换 Step 7 写路径**

Edit，Step 7 目前大致形如：
```
1. Write `docs/plans/{date}-tasks.yaml` (structured data)
2. Write `docs/plans/{date}-tasks.md` (human-readable table format)
```

替换为：
```
1. Write `{plans_dir}/{date}-tasks.yaml` (structured data)
2. Write `{plans_dir}/{date}-tasks.md` (human-readable table format)
```

**Step 4：Verify**

写路径 0 hits；读路径仍存在（下阶段处理）。

**Step 5：Commit**

```bash
git add skills/skill-3-task-gen/SKILL.md
git commit -m "refactor(plans-dir-writers): skill-3-task-gen write path uses plans_dir"
```

---

## Task B.5: skill-4-plan-schedule 写端（含硬编码 task-status.md / prompt-templates.md / collaboration-playbook.md）

**Files:**
- Modify: `skills/skill-4-plan-schedule/SKILL.md` (Step 5+8 写路径，含 3 个硬编码非-dated 文件)

**Step 1：定位所有写路径**

```bash
grep -n "docs/plans/" skills/skill-4-plan-schedule/SKILL.md
```

审计：line 30 read, line 169/234 写（包括 `task-status.md`、`prompt-templates.md`、`collaboration-playbook.md` 这 3 个无日期前缀的硬编码）。

**Step 2：在 Execution Flow 顶部加 resolver 引用**

同 B.2 Step 2。

**Step 3：替换写路径（全部）**

逐一 Edit 替换。对于 **带日期前缀** 的路径：

old_string:
```
Write `docs/plans/{date}-execution-plan.yaml`
```
new_string:
```
Write `{plans_dir}/{date}-execution-plan.yaml`
```

对于 **无日期前缀** 的硬编码（task-status.md / prompt-templates.md / collaboration-playbook.md）：

old_string:
```
docs/plans/task-status.md
```
new_string:
```
{plans_dir}/task-status.md
```

（其他两个同理）

**Step 4：Verify**

```bash
grep -n "docs/plans/" skills/skill-4-plan-schedule/SKILL.md | grep -v "project.yaml"
```

Expected: 0 hits（读路径也在这里一并改，因为 skill-4 的读/写同 section）。

如果本 task 只改了写端，读端 Step 1 line 30 还剩 1 条 —— 留到 Task C.3 处理。本 task 验收时写端 0 hits 即可。

**Step 5：Commit**

```bash
git add skills/skill-4-plan-schedule/SKILL.md
git commit -m "refactor(plans-dir-writers): skill-4 write paths (incl task-status.md) use plans_dir"
```

---

## Task B.6: skill-11-retro 写端（读端留到 Phase C）

**Files:**
- Modify: `skills/skill-11-retro/SKILL.md` (Step 5 写路径 line 163)

**Step 1：定位**

```bash
grep -n "docs/plans/" skills/skill-11-retro/SKILL.md
```

审计：Step 1 read at 24-27, Step 5 write at 163 (`retro-{milestone}-{date}.md`)。

**Step 2：在 Execution Flow 顶部加 resolver 引用**

同 B.2 Step 2。

**Step 3：替换写路径**

Edit：

old_string:
```
docs/plans/retro-{milestone}-{date}.md
```
new_string:
```
{plans_dir}/retro-{milestone}-{date}.md
```

**Step 4：Verify**

写路径 0 hits；读路径仍在。

**Step 5：Commit**

```bash
git add skills/skill-11-retro/SKILL.md
git commit -m "refactor(plans-dir-writers): skill-11-retro write path uses plans_dir"
```

---

## Task B.7: 写端集成验证（Test 2 + 4 + 5）

**Files:**
- Verify-only (no code changes)
- Optional write: `docs/superpowers/plans/test-evidence/2026-04-20-phase-b-verification.md` (evidence log)

**Step 1：Test 2 — 单项目子目录写入**

在一个临时 workspace 下（或用一个 test fixture project）：

```bash
# setup
mkdir /tmp/prd2impl-test-b
cd /tmp/prd2impl-test-b
mkdir -p docs/plans
cat > docs/plans/project.yaml <<EOF
project:
  name: "Test B"
  plans_dir: docs/plans/m2
EOF
```

现在手动跑（或用 Claude CLI 调用）`/ingest-docs`（传一个 fixture MD）。

Expected:
- `docs/plans/m2/` 目录自动创建
- `docs/plans/m2/{today}-prd-structure.yaml` 等文件存在
- `docs/plans/` 根目录除 project.yaml 外无新增

**Step 2：Test 4 — 同 plans_dir 重跑覆盖**

继续在同一 workspace：

再次运行 `/ingest-docs`（改一个 fixture MD 内容）。

Expected:
- 旧 yaml 被覆盖，无 `-v2` 后缀出现
- 日志里看到 `"Overwriting ... "` 类型的 diff-summary
- 日志里看到 `"Note: tasks.yaml ... may now be inconsistent"`

**Step 3：Test 5 — plans_dir 不存在自动创建**

```bash
# setup: rm -rf /tmp/prd2impl-test-b/docs/plans/m3
```

跑 `/ingest-docs --plans-dir docs/plans/m3 fixture.md`。

Expected: `docs/plans/m3/` 被自动创建，文件写入。

**Step 4：记录验证证据（可选）**

Write `docs/superpowers/plans/test-evidence/2026-04-20-phase-b-verification.md`:

```markdown
# Phase B 写端验证

Date: YYYY-MM-DD

## Test 2 (single subdir)
[粘贴 ls 输出]

## Test 4 (overwrite)
[粘贴日志输出片段，证明 diff-summary + invalidation hint 出现]

## Test 5 (auto mkdir)
[粘贴 ls 输出]

All tests: PASS / FAIL
```

**Step 5：Commit（若记录了证据文件）**

```bash
git add docs/superpowers/plans/test-evidence/
git commit -m "test(plans-dir-writers): phase B verification evidence"
```

---

# Phase C — 读端迁移（8 tasks）

## Task C.1: skill-2-gap-scan 读端

**Files:**
- Modify: `skills/skill-2-gap-scan/SKILL.md` (Step 1 读 glob)

**Step 1：定位**

```bash
grep -n "docs/plans/\*" skills/skill-2-gap-scan/SKILL.md
```

审计：Step 1 line ~31 `docs/plans/*-prd-structure.yaml`。

**Step 2：替换读 glob**

Edit：

old_string:
```
Find the most recent `docs/plans/*-prd-structure.yaml`
```
new_string:
```
Find the most recent `{plans_dir}/*-prd-structure.yaml`
```

（实际文本按 SKILL.md 当前措辞微调）

**Step 3：Verify 该 skill 全部无硬编码**

```bash
grep -n "docs/plans/" skills/skill-2-gap-scan/SKILL.md | grep -v "project.yaml"
```

Expected: 0 hits

**Step 4：Commit**

```bash
git add skills/skill-2-gap-scan/SKILL.md
git commit -m "refactor(plans-dir-readers): skill-2-gap-scan read glob uses plans_dir"
```

---

## Task C.2: skill-3-task-gen 读端

**Files:**
- Modify: `skills/skill-3-task-gen/SKILL.md` (Step 1 读 globs line 32-33)

**Step 1：定位**

```bash
grep -n "docs/plans/" skills/skill-3-task-gen/SKILL.md
```

写端已改，剩余应为 Step 1 读 + Input 列表。

**Step 2：替换 Input 列表中的路径**

Edit，Input 部分：

old_string:
```
- **Required**: `docs/plans/*-gap-analysis.yaml` (output from skill-2 or skill-0)
- **Required**: `docs/plans/*-prd-structure.yaml` (output from skill-1 or skill-0)
- **Optional**: `docs/plans/*-task-hints.yaml` (output from skill-0 only — see §Step 2.5)
- **Optional**: `docs/plans/project.yaml` (team configuration)
- **Optional**: Existing `docs/plans/tasks.yaml` (for incremental updates)
```

new_string:
```
- **Required**: `{plans_dir}/*-gap-analysis.yaml` (output from skill-2 or skill-0)
- **Required**: `{plans_dir}/*-prd-structure.yaml` (output from skill-1 or skill-0)
- **Optional**: `{plans_dir}/*-task-hints.yaml` (output from skill-0 only — see §Step 2.5)
- **Optional**: `docs/plans/project.yaml` (team configuration; always at project root)
- **Optional**: Existing `{plans_dir}/tasks.yaml` (for incremental updates — see docs/superpowers/specs/2026-04-20-plans-dir-scoping-design.md §8.6 for status)
```

**注意**：`project.yaml` 保持在根目录 `docs/plans/project.yaml`（它本身决定 plans_dir，不能被它自己控制）。

**Step 3：替换 Step 1 的 read globs**

Edit：

old_string:
```
1. Find the most recent `gap-analysis.yaml` and `prd-structure.yaml`
```
（可能包含完整路径，按实际微调）

如果具体路径出现，也替换 `docs/plans/` → `{plans_dir}/`。

**Step 4：Verify**

```bash
grep -n "docs/plans/" skills/skill-3-task-gen/SKILL.md | grep -v "project.yaml"
```

Expected: 0 hits

**Step 5：Commit**

```bash
git add skills/skill-3-task-gen/SKILL.md
git commit -m "refactor(plans-dir-readers): skill-3-task-gen read paths use plans_dir"
```

---

## Task C.3: skill-4-plan-schedule 读端

**Files:**
- Modify: `skills/skill-4-plan-schedule/SKILL.md` (Step 1 读 line ~30)

**Step 1：定位**

```bash
grep -n "docs/plans/" skills/skill-4-plan-schedule/SKILL.md | grep -v "project.yaml"
```

Expected: 剩 1 条 Step 1 读路径（写端已在 B.5 改完）。

**Step 2：替换读路径**

Edit：

old_string:
```
Find the most recent `docs/plans/*-tasks.yaml`
```
new_string:
```
Find the most recent `{plans_dir}/*-tasks.yaml`
```

**Step 3：Verify**

```bash
grep -n "docs/plans/" skills/skill-4-plan-schedule/SKILL.md | grep -v "project.yaml"
```

Expected: 0 hits

**Step 4：Commit**

```bash
git add skills/skill-4-plan-schedule/SKILL.md
git commit -m "refactor(plans-dir-readers): skill-4 read path uses plans_dir"
```

---

## Task C.4: skill-9-task-status 读端

**Files:**
- Modify: `skills/skill-9-task-status/SKILL.md` (line 22-24 reads)

**Step 1：定位**

```bash
grep -n "docs/plans/\|task-status\.md\|tasks\.yaml" skills/skill-9-task-status/SKILL.md
```

审计：line 22-24 读 `tasks.yaml`（优先）、`task-status.md`、`*-execution-plan.yaml`。

**Step 2：在 Execution Flow 顶部加 resolver 引用**

同 B.2 Step 2。

**Step 3：替换读路径**

Edit 替换所有 `docs/plans/tasks.yaml` → `{plans_dir}/tasks.yaml`，`docs/plans/task-status.md` → `{plans_dir}/task-status.md`，`docs/plans/*-execution-plan.yaml` → `{plans_dir}/*-execution-plan.yaml`。

**Step 4：Verify**

```bash
grep -n "docs/plans/" skills/skill-9-task-status/SKILL.md | grep -v "project.yaml"
```

Expected: 0 hits

**Step 5：Commit**

```bash
git add skills/skill-9-task-status/SKILL.md
git commit -m "refactor(plans-dir-readers): skill-9-task-status reads use plans_dir"
```

---

## Task C.5: skill-10-smoke-test 读端

**Files:**
- Modify: `skills/skill-10-smoke-test/SKILL.md` (line 24-26 reads)

**Step 1：定位**

```bash
grep -n "docs/plans/\|task-status\.md\|tasks\.yaml" skills/skill-10-smoke-test/SKILL.md
```

审计：line 24-26 读 `*-execution-plan.yaml`、`tasks.yaml`、`task-status.md`。另外还读 `.artifacts/registry.json` —— **不改** `.artifacts/`（per spec §8 L1）。

**Step 2：同 C.4，替换**

加 resolver 引用 + 替换 `docs/plans/` → `{plans_dir}/`。**保留** `.artifacts/registry.json` 不变。

**Step 3：Verify**

```bash
grep -n "docs/plans/" skills/skill-10-smoke-test/SKILL.md | grep -v "project.yaml"
```

Expected: 0 hits

**Step 4：Commit**

```bash
git add skills/skill-10-smoke-test/SKILL.md
git commit -m "refactor(plans-dir-readers): skill-10-smoke-test reads use plans_dir"
```

---

## Task C.6: skill-11-retro 读端

**Files:**
- Modify: `skills/skill-11-retro/SKILL.md` (line 24-27 reads)

**Step 1：定位 + Edit**

```bash
grep -n "docs/plans/\|task-status\.md\|tasks\.yaml" skills/skill-11-retro/SKILL.md
```

审计：line 24-27 读 `tasks.yaml`、`task-status.md`、`*-execution-plan.yaml`、git log、registry。

**Step 2：替换**

同 C.4 模式。保留 git log 和 registry.json 引用不变。

**Step 3：Verify**

```bash
grep -n "docs/plans/" skills/skill-11-retro/SKILL.md | grep -v "project.yaml"
```

Expected: 0 hits

**Step 4：Commit**

```bash
git add skills/skill-11-retro/SKILL.md
git commit -m "refactor(plans-dir-readers): skill-11-retro reads use plans_dir"
```

---

## Task C.7: 次级扫描 — skills 5/6/7/8/12/13

**Files:**
- Modify (potentially): 这 6 个 skill 的 SKILL.md
- Modify (if exist): 这些 skill 的 lib/templates 下的引用

**Step 1：批量定位硬编码**

```bash
for s in skill-5-start-task skill-6-continue-task skill-7-next-task skill-8-batch-dispatch skill-12-contract-check skill-13-autorun; do
  echo "=== $s ==="
  grep -n "docs/plans/\|task-status\.md\|tasks\.yaml" "skills/$s/SKILL.md" 2>/dev/null
done
```

记录每个 skill 里每条命中。预估总共 ~15 处（见 spec §5.4）。

**Step 2：逐 skill 处理**

对每个 skill，重复 C.4 模式：
1. 在 Execution Flow（或入口流程）顶部加 resolver 引用
2. 把 `docs/plans/task-status.md` → `{plans_dir}/task-status.md`
3. 把 `docs/plans/tasks.yaml` → `{plans_dir}/tasks.yaml`
4. 把其他 `docs/plans/*.yaml` → `{plans_dir}/*.yaml`
5. **例外**：`docs/plans/project.yaml` 保持不变（因为 project.yaml 自己决定 plans_dir）
6. **例外**：`.artifacts/` 路径保持不变
7. Grep 本 skill 验收：0 硬编码（除 project.yaml）

**Step 3：全局验收**

```bash
grep -rn "docs/plans/" skills/ | grep -v "plans_dir" | grep -v "project\.yaml" | grep -v "docs/plans/$\|docs/plans/\"\s*$"
```

Expected: 0 hits（除保留项外全部改完）

**Step 4：Commit（一次性提交 6 个 skill 的变更）**

```bash
git add skills/skill-5-start-task skills/skill-6-continue-task skills/skill-7-next-task \
        skills/skill-8-batch-dispatch skills/skill-12-contract-check skills/skill-13-autorun
git commit -m "refactor(plans-dir-readers): secondary scan — skills 5/6/7/8/12/13 use plans_dir"
```

---

## Task C.8: 读端集成验证（Test 3）

**Files:**
- Verify-only
- Optional: `docs/superpowers/plans/test-evidence/2026-04-20-phase-c-verification.md`

**Step 1：Test 3 — 两项目并存不冲突**

在一个 fixture workspace:

```bash
mkdir -p /tmp/prd2impl-test-c
cd /tmp/prd2impl-test-c
mkdir -p docs/plans/m1 docs/plans/m2

# 塞一组旧的 M1 数据
cat > docs/plans/m1/2026-04-10-tasks.yaml <<EOF
tasks: [{id: T1.1, status: completed}]
EOF

# project.yaml 指向 m2
cat > docs/plans/project.yaml <<EOF
project:
  plans_dir: docs/plans/m2
EOF
```

跑 `/ingest-docs fixture.md → /task-gen → /task-status`：
- 所有产物应落在 `docs/plans/m2/`
- `docs/plans/m1/` 内容完全未改
- `/task-status` 只显示 m2 的进度，看不到 m1

**Step 2：切换到 m1 查询**

```bash
/task-status --plans-dir docs/plans/m1
```

Expected: 显示 m1 的 T1.1 completed 状态。

**Step 3：Commit evidence（可选）**

```bash
git add docs/superpowers/plans/test-evidence/
git commit -m "test(plans-dir-readers): phase C verification evidence"
```

---

# Phase D — 清理 & 回归（3 tasks）

## Task D.1: 回归测试（Test 1 + 6）

**Files:**
- Verify-only

**Step 1：Test 1 — 默认根目录向后兼容**

fixture workspace，**不配置 plans_dir**:

```bash
mkdir -p /tmp/prd2impl-test-d1
cd /tmp/prd2impl-test-d1
mkdir -p docs/plans
# 不写 project.yaml，或写一个不含 plans_dir 的
```

跑完整 pipeline `/ingest-docs → /task-gen → /task-status`。

Expected: 所有产物落在 `docs/plans/` 根目录，行为与老插件完全一致。

**Step 2：Test 6 — plans_dir 非法报错**

```bash
cd /tmp/prd2impl-test-d1
/ingest-docs --plans-dir /tmp/absolute fixture.md
```

Expected: 报错 `plans_dir must be a repository-relative path`，不写任何文件。

```bash
/ingest-docs --plans-dir ../plans fixture.md
```

Expected: 报错 `plans_dir must not contain '..' segments`。

**Step 3：Commit（若记录 evidence）**

```bash
git add docs/superpowers/plans/test-evidence/
git commit -m "test(plans-dir-cleanup): phase D regression verification"
```

---

## Task D.2: 文档 example 和 README 路径引用更新

**Files:**
- Modify: `README.md` (如果提到 `docs/plans/` 硬编码)
- Modify: `docs/guide-zh.md` (同上)
- Modify: 任何 `skills/*/README.md` 或 example 文件

**Step 1：全仓扫描**

```bash
grep -rn "docs/plans/" README.md docs/ 2>/dev/null | grep -v "\.pen$\|\.artifacts/"
```

**Step 2：逐一 Edit 把示例路径改为统一的 `{plans_dir}/...` 语法说明**

对每条硬编码，修改为 markdown 示例里写：
```
docs/plans/{date}-tasks.yaml  (or {plans_dir}/{date}-tasks.yaml if plans_dir is configured)
```

或者：
```
{plans_dir}/{date}-tasks.yaml  (defaults to docs/plans/)
```

按上下文选择更清晰的表述。

**Step 3：Verify**

```bash
grep -rn "docs/plans/" README.md docs/
```

Expected: 每处都附有 plans_dir 语法说明，或明确标记为默认值示例。

**Step 4：Commit**

```bash
git add README.md docs/
git commit -m "docs(plans-dir-cleanup): update README and guides for plans_dir"
```

---

## Task D.3: 最终验收 — 完整 lint 一遍

**Files:**
- Verify-only

**Step 1：全量 lint**

```bash
# 检查没有遗漏的 docs/plans/ 硬编码
grep -rn "docs/plans/" skills/ | grep -v "plans_dir" | grep -v "project\.yaml"
```

Expected: 0 hits

**Step 2：检查每个 SKILL.md 都引用了 plans-dir-resolver**

```bash
for f in skills/*/SKILL.md; do
  if grep -l "docs/plans\|tasks\.yaml\|task-status\.md" "$f" > /dev/null; then
    if ! grep -l "plans-dir-resolver\|plans_dir" "$f" > /dev/null; then
      echo "MISSING resolver reference: $f"
    fi
  fi
done
```

Expected: 无 `MISSING` 输出

**Step 3：Smoke-run 所有 6 个测试**

- [ ] Test 1 (Task D.1 Step 1): 默认根目录 PASS
- [ ] Test 2 (Task B.7 Step 1): 单子目录 PASS
- [ ] Test 3 (Task C.8 Step 1): 两项目并存 PASS
- [ ] Test 4 (Task B.7 Step 2): 重跑覆盖 PASS
- [ ] Test 5 (Task B.7 Step 3): 自动 mkdir PASS
- [ ] Test 6 (Task D.1 Step 2): 非法路径 PASS

**Step 4：Final commit 标记完成**

```bash
git commit --allow-empty -m "chore(plans-dir): all phases complete; 6/6 tests passing"
```

---

# Self-Review 笔记

已完成的 spec 覆盖检查：

| Spec 要求 | 对应 Task |
|---|---|
| §3.1 resolve_plans_dir() 逻辑 | A.1 (定义) + B/C 全部（引用） |
| §3.2 三种使用形态 | A.3 (README) |
| §3.3 路径构造对照表 | B/C 按表实现 |
| §4.1 向后兼容（默认根目录） | D.1 Test 1 验收 |
| §4.2 glob 歧义消失 | C.8 Test 3 验收 |
| §4.3 同 plans_dir 覆盖语义 | B.1 (删 -v2 + 加 diff-summary) + B.7 Test 4 |
| §4.4 自动 mkdir | A.1 resolver 规范 + B.7 Test 5 |
| §4.5 合法性检查 | A.1 resolver 规范 + D.1 Test 6 |
| §5.1 新增 lib 文件 | A.1 |
| §5.2 project.yaml schema | A.2 |
| §5.3 8 个核心 skill | B.1–B.6 + C.1–C.6 |
| §5.4 次级扫描 6 skill | C.7 |
| §5.5 删除 -v2/-v3 | B.1 |
| §6 6 个测试 | B.7 (2/4/5) + C.8 (3) + D.1 (1/6) |
| §7 4 阶段 rollout | Phase A/B/C/D 结构对齐 |
| §8 已知限制 | spec 已注，plan 无需实现 |

类型一致性：`plans_dir` / `{plans_dir}` / `--plans-dir` 在全 plan 中用法统一。

无 TBD / TODO。

---

# Execution Handoff

Plan complete. 保存在 `docs/superpowers/plans/2026-04-20-plans-dir-scoping.md`。

**总任务数**: 21 tasks
- Phase A: 3 tasks
- Phase B: 7 tasks
- Phase C: 8 tasks
- Phase D: 3 tasks

**总 commit 数**（估算）: ~21-25 commits

**预估工时**（doc 编辑为主，不含测试执行）: 4-6 小时

两种执行选项：

1. **Subagent-Driven（推荐）** — 每 task 派发一个新 subagent，我在 task 之间 review。快速迭代、context 轻、适合 doc 编辑这种"可并行的独立修改"
2. **Inline Execution** — 本会话顺序执行，按 checkpoint review。context 累积较重但上下文连续

你选哪个？
