# {Project Name} Claude Code 指令模板

> 配合 `task-status.md` 使用 · 由 prd2impl 自动生成

---

## 0. 核心原则

**原则 1 · 任务驱动**：不说"帮我写 X"，说"启动任务 T1A.1"。CC 会自动读 tasks.yaml + task-status 形成完整上下文。

**原则 2 · 状态机驱动**：每次交互 CC 都应先读 task-status → 行动 → 更新状态 → commit。

---

## 1. 启动任务（Opening）

```
/start-task {Tx.x}
```

或手动：
```
启动任务 {Tx.x}（{任务名}）。

预期行为：
1. 先读 task-status 确认 {Tx.x} 是 ⬜ 且无前置阻塞
2. 改状态为 🟦 in_progress，填 Owner，commit
3. 读相关契约和 PRD
4. 进入 dev-loop 第一步：eval-doc
5. eval-doc 产出后停住等 review
```

---

## 2. 推进 dev-loop（Running）

```
/continue-task {Tx.x}
```

或手动：
```
继续 {Tx.x}，进入 dev-loop 下一步：
1. test-plan → 停住等确认
2. 确认后 test-code
3. 实现业务代码
4. 跑测试
5. 全绿 → 改 🟩 completed + 填 artifact
```

---

## 3. 归档完成（Closing）

```
{Tx.x} dev-loop 全绿，请归档：
1. 改状态 🟩 completed
2. 填 artifact ID
3. commit + push
4. 推荐下一个可启动任务
```

---

## 4. 任务阻塞（Blocked）

```
{Tx.x} 卡住：{原因}。
1. 改状态 ⚠️ blocked + 填阻塞原因
2. commit
3. 推荐一个无阻塞的替代任务
```

---

## 5. Red 任务（人类主导）

```
/start-task {Tx.x}  （Red 任务自动进入草稿工模式）

流程：读资料 → 起草 → 列设计选择题 → 等人批准 → commit
```

---

## 6. Yellow 任务（AI + 人审）

```
/start-task {Tx.x}  （Yellow 任务自动进入草稿+审查模式）

流程：读资料 → 起草产出 → 输出 review checklist → 等审批
approved {Tx.x} → commit + 🟩
rejected {Tx.x}: {原因} → 改 🟥 + 重做
```

---

## 7. Orchestrator 视角

### 7.1 进度总览
```
/task-status
```

### 7.2 批量派发
```
/batch-dispatch {batch-id}
```

### 7.3 Milestone 门控
```
/smoke-test {Mx}
```

---

## 8. 契约变更

```
/contract-check
```

---

## 9. 新会话接续

```
我是 {team member id}，继续项目的 {line name} 线开发。
请先读 task-status 找我的 🟦 任务，告诉我进度和下一步。
```

---

## 10. 应急

### dev-loop 反复失败
```
{Tx.x} 已失败 3 次：{症状}。
请诊断：契约问题 / Red 缺失 / 逻辑 bug / 测试用例错？
```

### 任务粒度不对
```
{Tx.x} 需要拆分/合并：{原因}。
产出 tasks.yaml 和 task-status 的 patch，等我批准。
```
