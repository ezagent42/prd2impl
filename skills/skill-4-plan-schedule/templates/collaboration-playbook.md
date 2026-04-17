# {Project Name} 协同 Playbook

> 由 prd2impl 自动生成 · 入职必读

---

## 0. 谁读这份文档

项目参与者（按 `project.yaml` 中 team 配置生成）：

{for each team member in project.yaml, list: id, line, skills}

---

## 1. 协同模型

### 单人模式（1 条 line）
所有任务顺序执行，无需跨线协调。日常循环：
1. `/next-task` 挑任务
2. `/start-task {ID}` 进入 dev-loop
3. 完成 → `/continue-task` 直至完成
4. commit + push

### 多人并行模式（2+ 条 lines）

#### Layer 1 · 独立开发（90% 时间）
**目标**：各线互不打扰；仅通过 `task-status` 和 git 可见对方进度。

#### Layer 2 · 里程碑同步（每 Milestone 5 分钟）
- 触发：Milestone 所有 batch 完成
- 内容：互看 task-status，确认无遗漏

#### Layer 3 · 联调测试（每 Milestone 30 分钟）
- 触发：Layer 2 决策 go
- 内容：`/smoke-test {Mx}`
- 产出：gate report，merge 到 integration branch

---

## 2. 分支策略

```
main ← (release only)
  └── {integration branch} ← (milestone merges)
        ├── {line 1 branch} ← (line 1 日常)
        ├── {line 2 branch} ← (line 2 日常)
        └── ...
```

分支名从 `project.yaml` 的 team 配置读取。

---

## 3. Commit 规范

```
task: T1A.1 → in_progress ({owner})
task: T1A.1 → completed
task: T1A.1 → blocked: {reason}
task: batch-3 dispatch — T1A.3,T1A.6 → in_progress
milestone: M1 gate passed
contract: {description}
retro: M1 retrospective
```

---

## 4. Red / Yellow 任务 SLA

从 `project.yaml` sla 配置读取，默认值：

| 类型 | 响应时间 | 说明 |
|------|---------|------|
| Red 决策 | {sla.red_decision} | 人类主导，CC 起草等批准 |
| Yellow 审查 | {sla.yellow_review} | AI 起草，人 review |
| 阻塞响应 | {sla.blocker_response} | blocker 需要人介入 |

---

## 5. 契约变更流程

1. 发现需改契约 → `/contract-check` 分析影响
2. 起草变更 → 开 `contract/{name}` 分支
3. 通知相关 line 的开发者 review
4. 确认 → merge 到 integration branch
5. 各线 `git merge` 拉回变更

---

## 6. 冲突规避

- 每条 line 只改自己 line 的文件
- 共享文件（task-status, contracts）用精确 Edit 单行替换
- 单人模式下无冲突问题

---

## 7. 紧急情况

- dev-loop 反复失败 → 用应急模板诊断
- 任务粒度不对 → 产出 patch 等审批
- 需人工介入 → 标 ⚠️ + 起草 Issue
