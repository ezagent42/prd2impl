# {Project Name} 任务状态表

> 基于 `tasks.yaml` 自动生成 · **Ground truth** 为 `tasks.yaml`
> 本文件为人可读视图，由 `/task-status` 命令更新

**状态图例**: ⬜ pending · 🟦 in_progress · 🟩 completed · ⚠️ blocked · 🟥 failed(需重做)
**类型图例**: 🟢 Green(AI 独立) · 🟡 Yellow(AI+人审) · 🔴 Red(人主导)

**最后更新**: {date} · **整体进度**: 0/{total} (0%)

---

## Phase 0 · {Phase Name}（{Milestone}）

| ID | 名称 | 线 | 类型 | 状态 | Owner | 依赖 | 关联 artifact |
|---|---|---|---|---|---|---|---|
| T0S.1 | {name} | S | 🔴 | ⬜ | — | — | — |

---

## 进度汇总

| Phase | 总数 | 待开始 ⬜ | 进行中 🟦 | 完成 🟩 | 阻塞 ⚠️ |
|---|---|---|---|---|---|
| P0 | 0 | 0 | 0 | 0 | 0 |
| **合计** | **0** | **0** | **0** | **0** | **0** |

---

## 更新规则

1. **Owner 字段**只在任务 `in_progress` 时填写；完成后可保留
2. **状态流转**: `⬜ → 🟦 → 🟩`（正常）或 `⬜ → 🟦 → ⚠️`（阻塞）或 `🟦 → 🟥`（失败待重做）
3. **关联 artifact 字段**随 dev-loop 推进填充
4. **每次修改** commit message 格式: `task: T0.1 → in_progress ({owner})`
5. **冲突规避**: 用 Edit 精确替换单行，避免整表重写
6. **多线并行**: 每条 line 只改自己 line 的任务行；共享任务需 review
