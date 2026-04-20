# prd2impl 使用说明

> `prd2impl` + `dev-loop-skills` + `superpowers` 三个 Claude Code 插件协同完成 **PRD → 任务拆解 → 执行 → 验证** 全流程。本文档是这三套能力的入口手册，适用于任意项目（新项目、已有代码库、已有手写文档的项目均可）。

---

## 1. 它是什么

**prd2impl** 是一个 14-skill 的 Claude Code 插件，负责把 PRD（或已有的手写设计文档）一路推进到 milestone 验证：

```
PRD → 结构化 → gap 分析 → 任务拆解 → 批次计划 → 执行 → 回顾 → 契约校验
```

它是 **orchestrator 层**，自身不做测试、不做 brainstorm、不做 debug，而是在需要时调用两个 companion 插件：

| 插件 | 角色 | 负责 |
|------|------|------|
| `prd2impl@ezagent42` | 项目编排 | 需求→任务→批次→里程碑 |
| `dev-loop-skills@ezagent42` | 测试流水线 | eval-doc / test-plan / test-code / test-run / `.artifacts/` 注册表 |
| `superpowers@claude-plugins-official` | 方法与纪律 | brainstorming / writing-plans / TDD / debugging / code-review / parallel agents |

三个插件都是 **optional with graceful degradation**：缺一个，prd2impl 会退化到更简单的路径而不是报错。

---

## 2. 新项目如何接入

### 2.1 前置条件

- 装好 [Claude Code](https://docs.anthropic.com/claude/docs/claude-code)（CLI 或 IDE 扩展）
- 项目已经是 git 仓库（`git init` 足矣）

### 2.2 三种方式（任选一种）

#### 方式 A：用 `/plugin` 命令交互安装（推荐新项目用）

在项目根目录进入 Claude Code，执行：

```
/plugin marketplace add ezagent42/ezagent42
/plugin install prd2impl@ezagent42
/plugin install dev-loop-skills@ezagent42
/plugin install superpowers@claude-plugins-official
```

Claude Code 会把选择写进项目级或用户级 settings。完成后 `/help` 里就能看到所有 skill 命令。

#### 方式 B：手写 `.claude/settings.json`（团队协作推荐）

把下面这份直接提交到仓库，队友 clone 就能用：

```json
{
  "permissions": {
    "allow": [
      "Read(*)", "Edit(*)", "Write(*)",
      "Bash(git *)", "Bash(ls *)", "Bash(cd *)"
    ],
    "defaultMode": "acceptEdits"
  },
  "enabledPlugins": {
    "prd2impl@ezagent42": true,
    "dev-loop-skills@ezagent42": true
  },
  "extraKnownMarketplaces": {
    "ezagent42": {
      "source": {
        "source": "git",
        "url": "https://github.com/ezagent42/ezagent42.git"
      }
    }
  }
}
```

> `superpowers` 来自官方 marketplace `claude-plugins-official`，Claude Code 默认已知，通常由各人在 user scope 装一次即可（`/plugin install superpowers@claude-plugins-official`），不必写进项目 settings。

#### 方式 C：本地开发版（插件作者才用）

如果你在改 prd2impl 自身，想本地路径引用：

```json
"extraKnownMarketplaces": {
  "prd2impl-local": {
    "source": { "source": "directory", "path": "/abs/path/to/prd2impl" }
  }
},
"enabledPlugins": { "prd2impl@prd2impl-local": true }
```

> 注意：`directory` 源只在有该路径的机器上可用，**不要提交到团队仓库**。团队协作一律用方式 B。

### 2.3 开干：新项目最小启动流程

假设项目刚建好，只有一份手写 PRD：

```bash
mkdir -p docs/prd
# 把你的 PRD 拷到 docs/prd/my-prd.md
```

然后在 Claude Code 里：

```
/prd-analyze docs/prd/my-prd.md   # ① 结构化 PRD
/gap-scan                         # ② 扫描代码库（空仓库也 OK，结果就是"全是 gap"）
/task-gen                         # ③ 生成任务（三色分类）
/plan-schedule                    # ④ 生成批次计划、里程碑、时间线
```

每一步都会停下等你 review YAML 产物。全部通过后：

```
/next-task                        # 问"下一步做什么"
/start-task T1A.1                 # 启动第一个任务
```

### 2.4 验证安装

```
/help
```

应能看到 `prd2impl:*` 共 14 个 skill、`dev-loop-skills:*` 共 7 个、`superpowers:*` 一组。缺哪个就补装哪个 —— 缺了不会报错，只是那一段能力退化。

---

## 3. 两种入口（Entry A vs Entry B）

**互斥，按项目选一种**。

### Entry A — 从原始 PRD 文档开始

适用：**新项目**、只有一份 `.md` 格式的 PRD，还没有任何设计或 gap 文档。

```
/prd-analyze docs/prd/my-prd.md            # skill-1  PRD → 结构化 YAML
/gap-scan                                  # skill-2  代码 vs 需求 gap
/task-gen                                  # skill-3  生成带依赖的任务
/plan-schedule                             # skill-4  批次/里程碑/时间线
```

### Entry B — 已经有手写 MD（gap / 设计 / 计划）

适用：**已有项目**，`docs/` 下已经有人手写的 gap 分析、设计规格或计划文档，不想浪费这些人力成果。

```
/ingest-docs docs/plans/my-gap.md docs/plans/my-design-spec.md
                                           # skill-0  分类 + 提取 → 3 份 YAML
/task-gen                                  # skill-3  （自动读 task-hints.yaml）
/plan-schedule                             # skill-4
```

角色自动识别不准时可强制：

```
/ingest-docs a.md b.md --tag spec=a.md --tag gap=b.md
```

每一步都有 **人工 review checkpoint**，skill 会停下来等你确认再推进。

---

## 4. 日常开发循环

计划定好之后，日常只用这几条：

```
/next-task                                 # 我下一步做什么？
/start-task T1A.1                          # 启动一个具体任务（进入 dev-loop）
/continue-task T1A.1                       # review 后继续
/task-status                               # 整体进度 dashboard（含 Mermaid 图）
```

批量并行：

```
/batch-dispatch batch-3                    # 整个 batch 并行派发
/batch-dispatch T1A.3,T1A.6,T1A.7          # 指定任务并行派发
```

里程碑闸门：

```
/smoke-test M1                             # 里程碑验收
/retro M1                                  # 回顾
/contract-check                            # 接口/Schema 漂移检测
```

全自动（慎用）：

```
/autorun green                             # 仅跑 Green 任务（最安全）
/autorun yellow                            # Green + Yellow（AI 通过 code-reviewer 自审 Yellow）
/autorun all                               # Green + Yellow + Red（AI 对设计题也给默认答案，风险高）
/autorun until M1                          # 跑到 M1 smoke-test 就停

# 要真正免打扰需配合：
claude --dangerously-skip-permissions
# 或 .claude/settings.json → permissions.defaultMode = "bypassPermissions"
```

---

## 5. 任务三色分类

prd2impl 把所有任务分成三类，执行路径不同：

| 颜色 | 含义 | 工作流 |
|------|------|--------|
| `green` 🟢 | AI 可独立完成 | 完整 dev-loop：eval → test-plan → test-code → 实现 → test-run |
| `yellow` 🟡 | AI 起稿，人工审 | 起稿 → review checklist → 通过/打回 |
| `red` 🔴 | 需人工决策 | 起稿 + 决策问题 → 人决定 → 提交 |

颜色在 `/task-gen`（skill-3）阶段打上，后续所有执行 skill 都按颜色分流。

---

## 6. 文件约定

prd2impl 用 **YAML 作为真相源**，Markdown 只是人类可读视图。所有文件默认落在 `docs/plans/`（可通过 skill 参数改目录）：

| 文件 | 生成者 | 作用 |
|------|--------|------|
| `project.yaml` | 手写 | 团队规模、里程碑定义 |
| `*-prd-structure.yaml` | skill-0 / skill-1 | 结构化 PRD |
| `*-gap-analysis.yaml` | skill-0 / skill-2 | Gap 扫描结果 |
| `*-task-hints.yaml` | skill-0 only | 手写 MD 里保留的 file_changes / steps / non_goals |
| `tasks.yaml` | skill-3 | 任务 + 依赖（单一真相源）|
| `execution-plan.yaml` | skill-4 | 批次 + 时间线 |
| `task-status.md` | auto | 进度视图（自动再生成）|
| `prompt-templates.md` | auto | CC 指令模板库 |
| `collaboration-playbook.md` | auto | 团队协作 runbook |
| `batch-*-kickoff.md` | auto | 每个 batch 的 runbook |

**向后兼容**：如果项目只有手写 `task-status.md` / `prompt-templates.md`，execution 阶段（skill-5 ~ skill-12）会直接读它们，跳过上游 skill-1~4 也能用。

---

## 7. 多人协同与任务分工

prd2impl 原生支持 **任意团队规模**（单人 / 双人 / 多人小队），所有协同规则来自 `project.yaml` 一份配置，不做硬编码假设。

### 7.1 Team line 模型

一个"line"（工作线）= 一条独立、并行推进的开发流。常见三种形态：

| 规模 | line 数 | 典型举例 |
|------|--------|----------|
| Solo（单人） | 1 | 全栈一人通吃 |
| Pair（双人） | 2 | 后端 + 前端；或功能 A + 功能 B |
| Squad（多人） | 3+ | 后端 + 前端 + 基础设施 + ... |

`skill-4-plan-schedule` 第一次运行时会问你团队结构，然后生成 `project.yaml`：

```yaml
project:
  team:
    - id: Alice
      line: backend
      branch: dev-backend
      skills: [backend, engine]
    - id: Bob
      line: frontend
      branch: dev-frontend
      skills: [frontend, delivery]
    - id: Carol
      line: infra
      branch: dev-infra
      skills: [devops, database]
  parallel_capacity: 3
```

`skills` 是技能标签，用于 **任务自动派工**。

### 7.2 任务 ID 与 line 的绑定

`/task-gen`（skill-3）生成的任务 ID 模式：`T{phase}{line}.{seq}`

| 示例 | 解读 |
|------|------|
| `T1A.3` | 阶段 1、line A（比如 backend）、序号 3 |
| `T2F.1` | 阶段 2、line F（frontend）、序号 1 |
| `T1S.2` | 阶段 1、shared / 跨线任务（line=`shared`） |

skill-3 自动派工的依据（按优先级）：

1. **模块标签匹配** —— 任务涉及的模块 skill 标签 ↔ 某条 line 的 skills 标签
2. **文件路径匹配** —— deliverable 路径落在谁的目录下（例如 `frontend/` → frontend line）
3. **只有 1 条 line 时** —— 全部派给 TA，不做切分

派工结果写入 `tasks.yaml` 的 `line:` 字段；按 line 分组的汇总写入 `summary.by_line`。

### 7.3 分支策略

由 `project.yaml.branches` 定义，默认三层：

```
main                    # 仅做 release
  └── dev               # integration branch（里程碑合并点）
        ├── dev-backend    # line 1 日常
        ├── dev-frontend   # line 2 日常
        └── dev-infra      # line 3 日常
```

- 平时：各人只在自己的 line branch 上干活，互不 push
- 里程碑过闸：`dev-*` 合到 `dev`，`/smoke-test` 通过后再合到 `main`
- `skill-8-batch-dispatch` 并行派发时，会以 `dev`（integration branch）为 base 建 git worktree，每个任务一个隔离工作区

### 7.4 三层协同模型（多人模式）

由 `skill-4-plan-schedule` 自动生成的 [`collaboration-playbook.md`](../collaboration-playbook.md) 规定：

| Layer | 触发时机 | 时长 | 做什么 |
|-------|---------|------|--------|
| **1 · 独立开发** | 90% 的时间 | — | 各 line 自己跑 dev-loop，只通过 `task-status.md` 和 git log 感知对方进度 |
| **2 · 里程碑同步** | 每 milestone 所有 batch 完成 | ~5 min | 互看 task-status，确认无遗漏；决定是否进入 Layer 3 |
| **3 · 联调测试** | Layer 2 decide go | ~30 min | `/smoke-test {Mx}` → 产 gate report → merge 到 integration branch |

核心理念是 **"90% 时间不打扰，10% 时间在里程碑闸门集中对齐"**。

### 7.5 跨线依赖与契约变更

- **跨线依赖**（例如前端 line 依赖后端 API）由 `tasks.yaml` 的 `depends_on` 字段显式表达，DAG 排程时强制前置完成
- **契约变更**（改接口 / Schema）走独立流程：
  1. 跑 `/contract-check` 先扫影响面
  2. 起 `contract/{name}` 分支，不污染任何 line
  3. 通知受影响 line 的 owner review
  4. 通过后合入 integration branch，各 line `git merge` 拉回

### 7.6 冲突规避规则

- 每条 line **只改自己 line 的文件**
- 共享文件（`task-status.md`、`contracts/*`）用精确 Edit 单行替换，避免大段覆盖
- `.artifacts/tasks/T1A.3/` 等以任务 ID 命名的目录天然隔离，不会相撞

### 7.7 SLA（响应时效）

对 Red / Yellow 任务和 blocker，`project.yaml.sla` 定义默认响应时长：

| 事件 | 默认 SLA | 用途 |
|------|---------|------|
| Red 决策 | 30 min | 人类主导、AI 起草等批准 |
| Yellow review | 30 min | AI 起草、人审 |
| Blocker 响应 | 1 hour | 阻塞其他 line 的问题必须快解决 |

超时会在 `/task-status` dashboard 里高亮，并在 milestone retro 里抓出来分析。

### 7.8 Commit 规范 = git log 状态大盘

`project.yaml.commits` 规定每种操作的 commit message 格式，让 `git log --oneline` 直接变成状态流：

```
task: T1A.1 → in_progress (Alice)
task: T1A.1 → completed
task: T1A.3 → blocked: waiting on contract decision
task: batch-3 dispatch — T1A.3,T1A.6,T1A.7 → in_progress
milestone: M1 gate passed
contract: add session_id to /auth/login
retro: M1 retrospective
```

这样即便没跑 `/task-status`，`git log` 也能还原出"谁在做什么、到哪一步了"。

### 7.9 一句话总结

> **prd2impl 不帮你管人，它帮你把"谁做什么、何时并行、何时对齐、冲突怎么避开"写成可执行的 YAML + Markdown，然后交给 CC 自动编排。** 团队只需要在第一次 `/plan-schedule` 时回答几个问题，之后日常循环都是 skill 自己在跑。

---

## 8. 共享的 `.artifacts/` 目录

三插件共用同一个 artifact 根目录，按所有权分区：

```
.artifacts/
├── registry.json           # dev-loop 写，prd2impl 读
├── eval-docs/              # dev-loop
├── test-plans/             # dev-loop
├── test-diffs/             # dev-loop
├── e2e-reports/            # dev-loop
├── tasks/                  # prd2impl
├── milestones/             # prd2impl
├── retros/                 # prd2impl
└── contract-checks/        # prd2impl
```

`.artifacts/` 会在首次运行时由 `dev-loop-skills:skill-6-artifact-registry` 自动初始化，无需手动创建。

---

## 9. 能力矩阵：三插件各贡献什么

| 能力 | prd2impl 原生 | superpowers | dev-loop-skills |
|------|:------------:|:-----------:|:----------------:|
| PRD → tasks → milestones | ✅ | — | — |
| 需求澄清（brainstorm） | — | ✅ `brainstorming` | — |
| 计划撰写 | 部分 | ✅ `writing-plans` | — |
| TDD 节奏（红/绿/重构） | — | ✅ `test-driven-development` | — |
| 测试计划生成 | — | — | ✅ `skill-2-test-plan-generator` |
| 测试代码生成（pytest） | — | — | ✅ `skill-3-test-code-writer` |
| 测试执行 + 回归识别 | — | — | ✅ `skill-4-test-runner` |
| 测试失败系统化排查 | — | ✅ `systematic-debugging` | — |
| 独立 code review（subagent） | — | ✅ `requesting-code-review` + `receiving-code-review` | — |
| 并行 subagent 派发 | — | ✅ `dispatching-parallel-agents` | — |
| 证据驱动的 GO/NO-GO | — | ✅ `verification-before-completion` | — |
| Artifact 注册表（`.artifacts/`） | — | — | ✅ `skill-6-artifact-registry` |

---

## 10. 已有 skill 清单

### 10.1 prd2impl（14 个）

| # | Skill | 命令 | 作用 |
|---|-------|------|------|
| 0 | skill-0-ingest | `/ingest-docs` | **Entry B**：吃手写 MD，产出 3 份 YAML（含 task-hints） |
| 1 | skill-1-prd-analyze | `/prd-analyze` | **Entry A**：PRD 结构化提取 |
| 2 | skill-2-gap-scan | `/gap-scan` | 代码 vs PRD gap 分析 |
| 3 | skill-3-task-gen | `/task-gen` | 生成带依赖的任务列表（读 task-hints.yaml 时走 Entry B 分支） |
| 4 | skill-4-plan-schedule | `/plan-schedule` | 批次、里程碑、时间线 |
| 5 | skill-5-start-task | `/start-task` | 任务启动器（按颜色分流） |
| 6 | skill-6-continue-task | `/continue-task` | review 后恢复到下一 checkpoint |
| 7 | skill-7-next-task | `/next-task` | 推荐下一可执行任务 |
| 8 | skill-8-batch-dispatch | `/batch-dispatch` | 整批并行派发（走 superpowers 的并行 agent） |
| 9 | skill-9-task-status | `/task-status` | 进度 dashboard + Mermaid |
| 10 | skill-10-smoke-test | `/smoke-test` | 里程碑闸门验收 |
| 11 | skill-11-retro | `/retro` | 里程碑回顾 |
| 12 | skill-12-contract-check | `/contract-check` | 契约漂移检测 |
| 13 | skill-13-autorun | `/autorun` | 全自动（自动选顺序 + 并行度 + 默认决策） |
|  · | using-prd2impl | — | Router：根据意图路由到正确 skill |

### 10.2 dev-loop-skills（7 个）

| Skill | 命令触发词 | 作用 |
|-------|-----------|------|
| skill-0-project-builder | "bootstrap", "onboard project", "set up dev-loop" | 把 60%+ 已有代码的项目一键装上 dev-loop |
| skill-2-test-plan-generator | "test plan", "what should we test", "coverage gap" | 从 diff / eval-doc / coverage 生成结构化 test plan |
| skill-3-test-code-writer | "write tests from plan", "implement test-plan" | 把 test plan 翻译成可跑的 pytest E2E 代码 |
| skill-4-test-runner | "run tests", "test report", "regression check" | 跑全量 E2E，输出 **新 vs 回归** 分类报告 |
| skill-5-feature-eval | "simulate", "verify", "found a bug" | 两种模式：simulate（Phase 1 预演）/ verify（Phase 7 建 issue） |
| skill-6-artifact-registry | "registry", "artifact", ".artifacts/" | `.artifacts/` 生命周期管理，跨 skill 共享真相源 |
| using-dev-loop | — | Router：根据意图决定调哪一个 skill-N |

### 10.3 superpowers（prd2impl 会主动调用的子集）

| Skill | 何时被 prd2impl 调用 |
|-------|---------------------|
| brainstorming | skill-1 PRD 分析前澄清歧义；skill-5 启动 Red 任务时做设计 trade-off |
| writing-plans | skill-4 `/plan-schedule` 的结构化计划撰写 |
| executing-plans | 当计划有明确 review checkpoint 时，替代 ad-hoc 执行 |
| test-driven-development | skill-5 启动 Green/Yellow 任务实现阶段，强制红绿重构节奏 |
| systematic-debugging | skill-6 测试失败时做假设 / 证据驱动的排查 |
| requesting-code-review | skill-6 任务收尾 + skill-10 里程碑 + skill-13 autorun yellow 自审 |
| receiving-code-review | 接收 code-reviewer subagent 的反馈时的技术严谨性检查 |
| verification-before-completion | skill-10 smoke-test 宣布 GO 前强制验证命令证据 |
| dispatching-parallel-agents | skill-8 `/batch-dispatch` 的并行 subagent 派发 |
| using-git-worktrees | 并行派发时为每个 subagent 准备隔离工作区 |
| finishing-a-development-branch | 分支收尾（merge / PR / 清理决策） |
| subagent-driven-development | 执行含独立任务的计划时 |
| writing-skills | 新增或改动 skill 时的元能力 |
| using-superpowers | 每次会话开始时确立"先查 skill 再行动"的纪律 |

> 完整 superpowers 列表在安装后执行 `/help` 查看，或到 [github.com/anthropics/claude-plugins-official](https://github.com/anthropics/claude-plugins-official) 的 `superpowers/` 目录下浏览源码。

---

## 11. 几种典型工作方式

### A. "我有一份 PRD，项目从零起步"
```
/prd-analyze docs/prd/my-prd.md
/gap-scan
/task-gen
/plan-schedule
# 然后进入日常循环：/next-task → /start-task → /continue-task
```

### B. "我已经手写了 gap + plan"
```
/ingest-docs docs/plans/my-gap.md docs/plans/my-tasks.md
/task-gen
/plan-schedule
# 同样进入日常循环
```

### C. "我只是想跑一个 batch"
```
/batch-dispatch batch-1    # 直接读 execution-plan.yaml 里的 batch-1
```

### D. "我今天不想动手"
```
/autorun green until M1
# 建议同时用 --dangerously-skip-permissions，否则还是会问权限
```

### E. "临时冒出一个 bug，想系统化排查"
绕开 prd2impl，直接用 superpowers：
```
# 对话里说明 bug 现象，superpowers:systematic-debugging 会自动被激活
```

### F. "跑完测试，想看有没有回归"
```
# 直接用 dev-loop：
# 说"run the E2E tests and give me a regression report"
# skill-4-test-runner 会自动接手
```

### G. "3 人团队，前后端并行跑一个 Milestone"
```
# 首次配置：在 /plan-schedule 里回答 3 条 line（backend / frontend / infra）
# skill-4 自动生成 project.yaml + collaboration-playbook.md + 3 个 line branch 建议

# 三人各自的日常循环（互不干扰）：
git checkout dev-backend && /next-task       # Alice
git checkout dev-frontend && /next-task      # Bob
git checkout dev-infra && /next-task         # Carol

# Milestone 所有 batch 完成后，任一人在 dev 分支上：
/smoke-test M1                               # 联调 + gate 决策
# 通过 → 三人各自 git merge dev 拉回集成结果
```

### H. "某个 line 跑得飞快，想整批派出去"
```
/batch-dispatch batch-3
# 或指定 line：
/batch-dispatch T1A.3,T1A.6,T1A.7
# skill-8 会为每个任务起一个 git worktree（以 dev 为 base），并行跑
```

---

## 12. 常见问题

**Q：我没装 superpowers / dev-loop-skills，prd2impl 还能用吗？**
能，但会退化：
- 没 superpowers → 规划/执行更简陋但能跑；milestone-only review
- 没 dev-loop-skills → 手写测试，无新/回归分类

**Q：Entry A 和 Entry B 能混用吗？**
**不能**。两者产物互斥，一个项目选一种。

**Q：修改了 PRD 文档，怎么同步任务？**
重新跑 `/prd-analyze`（Entry A）或 `/ingest-docs`（Entry B），然后 `/task-gen --refresh`。tasks.yaml 的 diff 会高亮新增/删除/修改。

**Q：autorun 会不会改坏代码？**
`/autorun green` 是安全默认。`yellow` 让 AI 自审，`all` 让 AI 在 Red（设计决策）任务上给默认答案 —— 风险递增。建议搭配 worktree 隔离（superpowers:using-git-worktrees）。

**Q：单人项目 vs 多人项目，skill 行为有差别吗？**
绝大部分相同，只有少数几处按 `project.yaml.team` 的行数分流：
- **`/plan-schedule`** —— 1 line 时不生成跨线协调段落；2+ lines 时自动写 `collaboration-playbook.md`
- **`/task-gen`** —— 1 line 时全部任务派给那一人；2+ lines 按 skill 标签自动派工
- **`/batch-dispatch`** —— 1 line 时就是顺序启动；2+ lines 才真正并行 worktree
- **`/smoke-test`** —— 1 line 跳过 Layer 2 同步环节，直接进 gate 验收

你完全可以先以 solo 模式起步（`team` 只填一人），后续加人时直接改 `project.yaml` 增条目、重跑一次 `/plan-schedule` 即可，不用重做任务。

**Q：我想中途换 team 配置（加人/减人）怎么办？**
1. 编辑 `project.yaml.team`，加一条或删一条
2. 重跑 `/plan-schedule` —— skill-4 会重新计算 batch 和分工，保留已完成任务的 owner 不变
3. 查 diff，确认调整合理 → commit

**Q：跨 line 合并冲突怎么办？**
按 §7.6 规则执行通常不冲突。若真撞到：
- 优先走 `/contract-check` 的正式契约流程解决接口级冲突
- 共享文件（如 `task-status.md`）撞了 → Claude Code 会检测到 conflict marker，让你选择保留哪一版；两版都要留就手动合并并重新 commit

**Q：插件源码在哪？**
- prd2impl：[github.com/ezagent42/prd2impl](https://github.com/ezagent42/prd2impl)
- dev-loop-skills：[github.com/ezagent42/dev-loop-skills](https://github.com/ezagent42/dev-loop-skills)
- marketplace 注册表：[github.com/ezagent42/ezagent42](https://github.com/ezagent42/ezagent42)
- superpowers：[github.com/anthropics/claude-plugins-official](https://github.com/anthropics/claude-plugins-official) → `superpowers/`

**Q：配置要不要提交到仓库？**
- `.claude/settings.json`（含 `enabledPlugins` + `extraKnownMarketplaces`）**应当提交** —— 队友 clone 即用。
- `.claude/settings.local.json` 包含本机私有项（比如个人 allow 列表），**不应提交**，加入 `.gitignore`。
- 本地 directory marketplace（方式 C）**绝不提交**，会因路径不存在让队友报错。

---

## 13. 项目侧目录约定（建议）

prd2impl 默认会找下面的路径，建议新项目预先建好：

```
<project-root>/
├── .claude/
│   └── settings.json            # 插件启用（方式 B 的成果）
├── docs/
│   ├── prd/                     # Entry A 输入：原始 PRD
│   │   └── my-prd.md
│   └── plans/                   # skill-0~4 的 YAML/MD 产物落这里
│       ├── project.yaml         # 团队与里程碑（手写）
│       ├── *-prd-structure.yaml # skill-1 / skill-0 产出
│       ├── *-gap-analysis.yaml  # skill-2 / skill-0 产出
│       ├── *-task-hints.yaml    # skill-0 专有
│       ├── tasks.yaml           # skill-3 真相源
│       ├── execution-plan.yaml  # skill-4 产出
│       └── task-status.md       # 自动再生
└── .artifacts/                  # dev-loop + prd2impl 共用，自动生成
```

最小必需只有 `.claude/settings.json` + 一份 PRD 或手写 MD，其他都由 skill 自动生成。
