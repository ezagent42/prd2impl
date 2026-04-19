# Gap Analysis — AutoService v2

**Date:** 2026-04-18
**Scope:** Full journey PRD vs current implementation

## Summary

17 gaps identified. P0=6, P1=6, P2=5.

## P0 Gaps

### A-① 缺注册接入独立步骤 [P0]

Current state: wizard jumps straight to upload without a registration step.

Missing:
- RegisterStep component
- Country → compliance_profile mapping

### A-② IM 管理群缺失 [P0]

No Feishu management group notification on onboarding completion.

### B-⑦ Customer SDK hardcoded ws://localhost [P0]

Single-tenant only; cannot deploy multi-tenant.

## P1 Gaps

### A-④ Sandbox rehearsal uses real API [P1]

Expected: mock responses. Actual: live API calls.

### C-⑬ Replay job no dedup [P1]

Duplicate conversation replays inflate dream engine training data.

## P2 Gaps

### C-⑮ Morning push no rich text [P2]

Feishu morning push sent as plain text; should use interactive card format.
