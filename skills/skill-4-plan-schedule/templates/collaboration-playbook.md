# {Project Name} 协同 Playbook

> 由 prd2impl 自动生成 · 入职必读

---

## 0. 谁读这份文档

- **A 线开发者**（后端 / 引擎 / 业务）
- **B 线开发者**（前端 / 交付）
- **Lead / PM**（跨线协调、Red 决策、里程碑门控）

---

## 1. 三层协同模型

### Layer 1 · 独立开发（90% 时间）

**目标**：两人不打扰；仅通过 `task-status` 和 git 可见对方进度。

日常循环：
1. `git fetch && git pull`
2. `/next-task` 挑任务
3. `/start-task {ID}` 进入 dev-loop
4. 完成 → `/continue-task` 直至 🟩
5. commit + push

### Layer 2 · 里程碑同步（每 Milestone 5 分钟）

- 触发：Milestone 所有 batch 完成
- 内容：互看 task-status，确认无遗漏
- 产出：go / no-go 决策

### Layer 3 · 联调测试（每 Milestone 30 分钟）

- 触发：Layer 2 决策 go
- 内容：`/smoke-test {Mx}`
- 产出：gate report，merge 到 integration branch

---

## 2. 分支策略

```
main ← (release only)
  └── dev ← (milestone merges)
        ├── dev-a ← (A 线日常)
        └── dev-b ← (B 线日常)
```

- A 线 push 到 `dev-a`，B 线 push 到 `dev-b`
- Milestone 通过后 merge `dev-a` + `dev-b` → `dev`
- `main` 只接受最终验收后的 release

---

## 3. Commit 规范

```
task: T1A.1 → in_progress (DevA)
task: T1A.1 → completed
task: T1A.1 → blocked: waiting for zchat API
task: batch-3 dispatch — T1A.3,T1A.6,T1A.7 → in_progress
milestone: M1 gate passed
contract: add metadata field to Session
retro: M1 retrospective
```

---

## 4. Red / Yellow 任务 SLA

| 类型 | 响应时间 | 说明 |
|------|---------|------|
| Red 决策 | 30 分钟 | 人类主导，CC 起草等批准 |
| Yellow 审查 | 30 分钟 | AI 起草，人 review |
| 阻塞响应 | 1 小时 | blocker 需要人介入 |

---

## 5. 契约变更流程

1. 发现需改契约 → `/contract-check` 分析影响
2. 起草变更 → 开 `contract/{name}` 分支
3. 通知对方线 review
4. 双方确认 → merge 到 `dev`
5. 各自 `git merge origin/dev` 拉回变更

---

## 6. 冲突规避

- DevA 只改 A 线文件，DevB 只改 B 线文件
- 共享文件（task-status, contracts）用精确 Edit 单行替换
- `.gitattributes` 对 task-status 启用 `merge=union`

---

## 7. 紧急情况

- dev-loop 反复失败 → 用应急模板诊断
- 任务粒度不对 → 产出 patch 等审批
- 需人工介入 → 标 ⚠️ + 起草 Issue
