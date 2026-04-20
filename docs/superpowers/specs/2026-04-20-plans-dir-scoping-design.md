# prd2impl — `plans_dir` 目录分域 Design

> 2026-04-20 · Status: draft

## 0. Motivation

prd2impl 插件当前把所有产物硬编码写到 `docs/plans/` 根目录，文件名只以 `{date}` 为变化轴。当同一项目同日触发两套独立的 ingest/generation（例如 M1 刚收尾、M2 立刻启动），输出会落到同一个目录下，导致：

1. **写端冲突**：skill-0 的 `-v2/-v3` 后缀是"版本"语义，但实际冲突是"不同作用域" —— 并列的两个项目/里程碑
2. **读端踩错文件**：skill-3/4/9/10/11 用 glob + 最近选，多项目同日时会挑错文件
3. **`task-status.md` 硬编码无日期**：skill-4 写、skills 5–13 读写，第二次运行会覆盖第一个项目的状态机

作者实测：2026-04-20 同日对 AutoService 项目先跑 M1 ingest、再跑 M2 ingest，触发上述全部三个问题。手动绕过（用 `-m2-` 前缀）能让 skill-0 通过，但 skill-3 以下仍会踩 glob 陷阱。

## 1. Goal

让同一项目下多个并列作用域（里程碑 / 子项目 / 迭代）的 prd2impl 产物天然隔离，且**不引入新的标识符概念、不修改文件命名约定、不破坏旧项目行为**。

**解法一句话：** 用文件系统子目录隔离不同作用域，而不是在文件名里塞 scope 字段。

## 2. Scope

### 2.1 In scope

- 每个 skill 的路径构造从 `docs/plans/` 根目录改成由 `resolve_plans_dir()` 返回的路径
- 新增 `project.yaml.plans_dir` 字段（可选），默认 `docs/plans/`
- 新增 CLI `--plans-dir <path>` flag（可选），优先级最高
- 新增共享 `lib/plans-dir-resolver.md`，所有 skill 引用
- 删除 skill-0 Phase 4.1 的 `-v2/-v3` 冲突逻辑（改动后不再需要）

### 2.2 Out of scope

- **不引入 scope 命名标识符**（目录方案下不存在 scope 概念）
- **不引入 `.active-scope` 或任何会话级状态**
- **不改 `.artifacts/` 目录结构**（跨插件改动，超范围；由未来 registry 级别字段解决）
- **不提供 `/migrate` skill**（`mkdir + mv` 足够）
- **不做跨 plans_dir 的任务依赖或总览**（用户自行切换 plans_dir 运行）
- **不修改文件命名规则**（`{date}-<artifact>.yaml`、`task-status.md` 等文件名都不变）

## 3. Architecture

### 3.1 核心机制

所有 skill 在构造产物路径前，调用统一的解析逻辑：

```
resolve_plans_dir():
  1. if CLI flag --plans-dir <path> was passed:          return <path>
  2. elif project.yaml has `plans_dir` field:            return project.yaml.plans_dir
  3. else:                                               return "docs/plans/"

  after resolving:
    if resolved path does not exist → mkdir -p silently
```

**不变量：** 给定一次 skill 调用，`resolve_plans_dir()` 的返回值在该调用期间恒定。后续所有路径构造都是 `{resolved}/<filename>` 的形式。

### 3.2 使用形态

三种常见用法，从显式到隐式：

```bash
# A. 每次 CLI 显式传
/ingest-docs --plans-dir docs/plans/m2 a.md b.md
/task-gen --plans-dir docs/plans/m2
/task-status --plans-dir docs/plans/m2

# B. 项目级配置（推荐）
# docs/plans/project.yaml:
#   plans_dir: docs/plans/m2
# 之后所有 skill 无需传参

# C. 保持默认
# 不配置 plans_dir，所有产物继续写 docs/plans/ 根目录
# 行为与插件当前版本 100% 一致
```

### 3.3 路径构造示例（对照表）

| Artifact | 当前（硬编码） | 方案后 |
|---|---|---|
| gap-analysis.yaml | `docs/plans/{date}-gap-analysis.yaml` | `{plans_dir}/{date}-gap-analysis.yaml` |
| prd-structure.yaml | `docs/plans/{date}-prd-structure.yaml` | `{plans_dir}/{date}-prd-structure.yaml` |
| task-hints.yaml | `docs/plans/{date}-task-hints.yaml` | `{plans_dir}/{date}-task-hints.yaml` |
| tasks.yaml | `docs/plans/{date}-tasks.yaml` | `{plans_dir}/{date}-tasks.yaml` |
| execution-plan.yaml | `docs/plans/{date}-execution-plan.yaml` | `{plans_dir}/{date}-execution-plan.yaml` |
| task-status.md | `docs/plans/task-status.md`（硬编码无日期） | `{plans_dir}/task-status.md` |
| prompt-templates.md | `docs/plans/prompt-templates.md` | `{plans_dir}/prompt-templates.md` |
| collaboration-playbook.md | `docs/plans/collaboration-playbook.md` | `{plans_dir}/collaboration-playbook.md` |
| retro-{milestone}-{date}.md | `docs/plans/retro-...` | `{plans_dir}/retro-...` |

**文件名全部保持不变**，仅所在目录由 `{plans_dir}` 决定。

## 4. Behavior Details

### 4.1 向后兼容（结构自洽，不需要特殊代码）

默认 `plans_dir = "docs/plans/"` 与旧版插件路径重合。因此：

- **老项目不修改 project.yaml** → 所有路径解析到根目录 → 行为与旧版一致
- **老项目想分域** → 加一行 `plans_dir: docs/plans/m1`，手动 `mv` 老文件进子目录
- **新项目** → 直接设 `plans_dir: docs/plans/<scope>`，干净开始

**读端没有 fallback 逻辑**：`{plans_dir}` 决定的就是当前视野。每个目录内部自洽、闭合。

### 4.2 Glob 歧义问题自动消失

审计报告标红的"skill-3 读 `*-prd-structure.yaml` 多项目时选错"问题在本方案下**结构性消失**：

- 设置 plans_dir 后，glob 根只在单项目目录下
- 永远只看到本项目的文件
- 根本不存在"多个候选怎么选"的决策点

### 4.3 同 plans_dir 重跑 skill-0

重跑 `/ingest-docs`（相同 plans_dir）→ **直接覆盖**。不加 `-v2` 后缀，不做合并，不拒绝，不弹确认提示。

- 覆盖前**打印一行 diff 摘要**（纯信息性，不阻塞）：`"Overwriting {path} (12 modules → 13 modules, 1 constraint removed)"`
- 覆盖后**打印一行下游失效提示**：`"Note: tasks.yaml for this plans_dir already exists and may now be inconsistent. Re-run /task-gen to regenerate."`
- 用户若想并存两版同项目数据 → 用不同 plans_dir（如 `docs/plans/m2` 和 `docs/plans/m2-refined`）
- 用户若覆盖后后悔 → `git restore` 恢复（我们不做回滚机制）

### 4.4 plans_dir 不存在时自动创建

首次解析到 `plans_dir` 时，若目录不存在，自动 `mkdir -p`。不报错，不需用户手动创建。

### 4.5 plans_dir 合法性

只允许项目根相对路径：

- ✅ `docs/plans/m2`
- ✅ `docs/plans/sub/m2` (多级子目录)
- ✅ 尾部带或不带 `/` 都行（内部 normalize）
- ❌ 绝对路径（如 `/tmp/plans` 或 `C:\...`）
- ❌ 包含 `..` 段的路径（如 `../plans` 或 `docs/plans/../../etc`）
- ❌ 空字符串（按默认 `docs/plans/` 处理，不报错）

**检查顺序**（在 `resolve_plans_dir()` 返回前）：

1. **Normalize**：去尾部 `/`、解析 `./`、展开分隔符到 POSIX 形式（Windows 下 `\` → `/`）
2. **绝对路径检查**：若以 `/` 开头或匹配 `[A-Za-z]:`（Windows drive）→ 报错
3. **`..` 检查**：normalize 后的路径 split by `/`，若任一段为 `..` → 报错
4. **空字符串**：直接返回默认 `docs/plans`（normalize 后无尾部 `/`），不报错

错误信息（每种非法情形独立一条，见 `lib/plans-dir-resolver.md` 为权威版本）：
- 绝对路径：`"plans_dir must be a repository-relative path. Got: '<input>'"`
- `..` 段：`"plans_dir must not contain '..' segments. Got: '<input>'"`

## 5. Changes

### 5.1 新增文件

- `lib/plans-dir-resolver.md`（插件根级 lib，所有 skill 引用）
- 在 plugin README / `using-prd2impl` SKILL.md 里加 "plans_dir usage" 小节

### 5.2 project.yaml schema

```yaml
project:
  # ... existing fields (team, milestones, parallel_capacity, ...)
  plans_dir: docs/plans/m2    # new, optional, defaults to "docs/plans/"
```

- 不改现有字段
- 不要求必填
- 若缺省或设为空字符串 → 等同 `docs/plans/`

### 5.3 Skill 改动清单（审计覆盖的 8 个）

| Skill | SKILL.md 行号（当前） | 改动 |
|---|---|---|
| skill-0-ingest | Phase 4.1 / lines 131-189 | 写路径改 `{plans_dir}/...`；**删除** `-v2/-v3` 冲突段 |
| skill-1-prd-analyze | Step 5 / line 122 | 写路径 |
| skill-2-gap-scan | Step 1 / line 31 (read glob), Step 4 / line 144 (write) | 读+写 |
| skill-3-task-gen | Step 1 / lines 32-33 (read globs), Step 7 / lines 195-196 (write) | 读+写 |
| skill-4-plan-schedule | Step 1 / line 30 (read), Step 5+8 / lines 169, 234-236 (write) | 读+写；含硬编码 `task-status.md`、`prompt-templates.md`、`collaboration-playbook.md` |
| skill-9-task-status | Step 1 / lines 22-24 | 读 |
| skill-10-smoke-test | Step 1 / lines 24-26 | 读 |
| skill-11-retro | Step 1 / lines 24-27 (read), Step 5 / line 163 (write) | 读+写 |

### 5.4 次级扫描（审计未覆盖的 6 个 skill）

Skills 5/6/7/8/12/13 根据审计"关键 surprise 1"也读写 `task-status.md` / `tasks.yaml`。需要次级扫描：

- 扫 `skills/skill-{5,6,7,8,12,13}/SKILL.md` 里所有 `task-status.md`、`tasks.yaml`、`docs/plans/` 引用
- 全部改成 `{plans_dir}/` 前缀
- 预估 ~15 处改动

### 5.5 删除的代码

skill-0-ingest Phase 4.1 的 `-v2/-v3` 冲突逻辑（~30 行）：

```markdown
(delete)  If a file already exists with today's date: append `-v2` (then `-v3`, etc.) to avoid overwrite.
```

改写为：

```markdown
If a file already exists at the same path: print diff summary and overwrite
(user rerunning ingest for same plans_dir implies intentional overwrite).
If user wants coexistence, run with a different --plans-dir.
```

### 5.6 改动量估算

| 维度 | 数量 |
|---|---|
| 新 lib 文件 | 1 (`lib/plans-dir-resolver.md`) |
| SKILL.md 改动文件数 | 14 (8 审计 + 6 次扫) |
| 具体行/段改动 | ~50-70 处 |
| project.yaml schema | +1 字段 |
| 删除代码 | skill-0 的 -v2/-v3 冲突逻辑（~30 行） |
| **净增复杂度** | ≈ 0 或负（删的比加的多） |

## 6. Testing

"元"级别改动（所有 skill 的路径构造都变），不按 skill 逐个写 unit test。改用 **pipeline-level 集成测试**：

### 6.1 测试清单

**Test 1 — 默认根目录向后兼容**
- setup: 空项目，无 `plans_dir` 配置
- run: `/ingest-docs a.md → /task-gen → /task-status`
- assert: 所有文件落在 `docs/plans/` 根；和插件旧版行为一致

**Test 2 — 单项目子目录**
- setup: `project.yaml: plans_dir: docs/plans/m2`
- run: `/ingest-docs a.md → /task-gen → /task-status`
- assert: 所有文件落在 `docs/plans/m2/`；根目录无新文件

**Test 3 — 两项目并存不冲突**
- setup: `docs/plans/m1/` 有 M1 的 tasks.yaml；`docs/plans/m2/` 准备空
- run: `/ingest-docs --plans-dir docs/plans/m2 b.md → /task-gen --plans-dir docs/plans/m2`
- assert: m1 目录内容未变；m2 目录只含新产出

**Test 4 — 同 plans_dir 重跑覆盖**
- setup: `docs/plans/m2/` 已有 skill-0 产出
- run: `/ingest-docs --plans-dir docs/plans/m2 a.md`（修改后）
- assert: 旧文件被覆盖，无 `-v2` 后缀出现

**Test 5 — plans_dir 不存在自动创建**
- setup: `docs/plans/m3/` 不存在
- run: `/ingest-docs --plans-dir docs/plans/m3 a.md`
- assert: 目录被自动创建，文件写入

**Test 6 — plans_dir 非法报错**
- setup: 任意
- run: `/ingest-docs --plans-dir /tmp/absolute a.md`
- assert: 报错 `plans_dir must be a repository-relative path`，不写任何文件

### 6.2 实现

因为 prd2impl 是 prompt/doc 插件，没传统代码，测试方案：

- **fixture-based 人工验证**：在 `tests/fixtures/plans-dir-scoping/` 下准备 5 套场景 fixture（每套含 mock project.yaml + mock input MDs + expected tree 结构）
- **自动化 harness**（如有）：用 subprocess 跑 Claude CLI 指向 fixture 根，对比 expected tree
- **冒烟**：至少 Test 1 和 Test 2 要在真实 Claude Code 环境过一遍

## 7. Rollout

按"改了即可独立验证"分阶段，每阶段独立可 PR、独立可用：

### 阶段 A — 基础设施（不影响现有行为）

1. 新增 `lib/plans-dir-resolver.md`
2. `project.yaml` schema 文档加 `plans_dir` 字段说明
3. 更新 `using-prd2impl` README，说明"新项目推荐设 plans_dir"

**验收**：跑 Test 1（默认行为不变）

### 阶段 B — 写端迁移（6 个 skill）

4. 按 §5.3 写端清单改 skill-0/1/2/3/4/11
5. 删除 skill-0 的 `-v2/-v3` 逻辑

**验收**：跑 Test 2 / 4 / 5

### 阶段 C — 读端迁移（8 个 skill，含次扫）

6. 按 §5.3 读端清单改 skill-2/3/4/9/10/11
7. 按 §5.4 扫改 skill-5/6/7/8/12/13

**验收**：跑 Test 3

### 阶段 D — 清理 & 回归

8. 跑 Test 1 和 Test 6，确保向后兼容 + 非法路径处理
9. 更新所有文档 example 和 README 的路径引用

## 8. Known Limitations

1. **`.artifacts/` 目录不跟 plans_dir 走**：多 plans_dir 并存时，`.artifacts/registry.json` 里的条目可能混淆。当前接受；未来通过 registry entry 的 scope 字段解决（跨插件改动，和 dev-loop-skills 协调）
2. **同项目下多 plans_dir 无全局视图**：`/task-status` 只显示当前 plans_dir 的进度。想看全项目多里程碑总览需手动切换 `--plans-dir` 多次运行
3. **plans_dir 只支持项目根相对路径**：不支持绝对路径、`..` 跨出仓库
4. **不迁移老项目已有文件**：由用户自行 `mv`，或选择不迁移保持旧路径
5. **用户需手动维护 plans_dir 的一致性**：CLI 传参时要保证同一项目的 `/ingest-docs`、`/task-gen`、`/task-status` 传同一个 `--plans-dir`（或写进 project.yaml 一劳永逸）
6. **中期 spec 更新 / 任务状态保留不在本 spec 范围**：

   本 spec 的重跑语义是"同 plans_dir → 直接覆盖"（§4.3）。这意味着：如果用户在 M2 任务已跑部分后修改源 MD 并重跑 `/ingest-docs + /task-gen`，现有的 tasks.yaml 会被覆盖，已完成任务的状态（done / in_progress / artifact 链接）会丢失。

   现状盘点（来自扫描 plugin 源码）：
   - `skill-0-ingest` 设计 spec 明确将 incremental ingest 列为 non-goal（`docs/superpowers/specs/2026-04-19-skill-0-ingest-design.md:40`），列为 future extension（同文件 line 409）
   - `skill-3-task-gen` SKILL.md line 26 将 "Existing tasks.yaml (for incremental updates)" 列为 Optional 输入，但 execution flow（Step 1-8）未实现合并逻辑，**该承诺悬挂**
   - `skill-12-contract-check` 做合约漂移 diff，不覆盖 spec 修订场景

   处理方式：
   - 本 spec 不试图解决此问题
   - 未来独立 spec：`docs/superpowers/specs/YYYY-MM-DD-incremental-update-design.md`（待写），专门处理：
     - skill-3 兑现 "incremental updates" 承诺（读 existing tasks.yaml，按 gap_ref/file_change 层面 diff，保留状态）
     - 中期 task ID 策略（新增 append 到末尾，修改保留，删除标记 obsolete）
     - 与 `.artifacts/` 条目的关联保持（task ID 不变时 artifact 链接有效）
   - 当前用户 workaround：避免任务启动后改源 MD；若必须改，手动编辑 tasks.yaml 或接受状态丢失

## 9. Appendix — 未选方案（保留决策记录）

### A. 方案 3：scope-in-filename（`{date}-{scope}-<artifact>.yaml`）

**为什么放弃**：~50+ 处硬编码要改；永久命名复杂度；自动推导、格式校验、`-v2` 语义区分全都要设计；VS Code 文件树/git/ls 都天然理解目录，不理解 filename 前缀；归档/清理要做 50 个 rename 而非一个 mv。

### B. 方案 1：只修 glob 读端（报错 on ambiguity）

**为什么放弃**：autorun 场景会被交互式 prompt 打断；每个新 skill 都要重复处理歧义；没有系统性隔离，多项目并存时仍乱。

### C. 方案 0：不改插件

**为什么放弃**：审计揭示 task-status.md 硬编码是"时间炸弹"（每次 skill-4 覆盖），同日跑两个项目必炸；作者已实测踩坑一次，复现概率不低。

### D. 引入 `.active-scope` 会话级状态指针

**为什么放弃**：多窗口/多人协作场景会打架（A 在 VSCode 开 M1、B 在终端开 M2，切 scope 会互相覆盖）；git 能扛是因为工作区物理隔离，我们没有这个保证。目录方案下，"当前在哪个项目"由 project.yaml + CLI 显式决定，不需要隐式状态。

## 10. Summary Trade-offs

| 维度 | 目录分域（本方案） | scope-in-filename（曾考虑） |
|---|---|---|
| 改动量 | ~50-70 处改动 | ~500 行改动 |
| 新概念 | 无（目录是 FS 天然概念） | scope / scope 命名规则 / 冲突语义 |
| 向后兼容 | 零改动（默认根目录） | 需双栈 or 迁移命令 |
| 归档一操作 | `mv docs/plans/m1 archive/` | 50 个 rename |
| 跨工具理解 | git / ls / VS Code 都懂 | 需脑内解析文件名 |
| 文件名稳定 | 100% 不变 | 每个 artifact 多一段 |

决策：**采用目录分域**。
