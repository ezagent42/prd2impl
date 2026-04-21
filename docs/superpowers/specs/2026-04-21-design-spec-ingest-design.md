# skill-0-ingest: design-spec → prd-structure.yaml 桥接 Design

**Status:** Draft · **Date:** 2026-04-21 · **Owner:** h2os.cloud

## 1. Goal

让 brainstorming skill 产出的 design spec（散文规范，`docs/superpowers/specs/*-design.md`）能被 skill-0-ingest 完整消化：**既抽 task-hints.yaml（现状），也抽 partial prd-structure.yaml（新增）**。打通 `brainstorm → spec → skill-0-ingest → skill-2-gap-scan / skill-3-task-gen` 的 superpowers ↔ prd2impl 整合路径。

## 2. Current State

### 2.1 skill-0-ingest 的 design-spec 角色现状

skill-0 已有 6 个 markdown 角色分类（见 [lib/role-detector.md](../../../skills/skill-0-ingest/lib/role-detector.md)）：

| Role | Produces | Extractor |
|------|----------|-----------|
| gap | gap-analysis.yaml | gap-extractor |
| prd | prd-structure.yaml (full) | prd-extractor |
| plan | prd-structure.yaml (partial) + task-hints.yaml (steps) | prd-extractor |
| user-stories | prd-structure.yaml (us only) | prd-extractor |
| **design-spec** | **task-hints.yaml** | **spec-extractor** |
| unknown | — | — |

design-spec 当前**只**产 task-hints.yaml（file_changes / implementation_steps / non_goals / test_strategy / risks），不产 prd-structure.yaml。

### 2.2 User 反馈的使用痛点

用户在实际使用中发现：brainstorming 产出的 spec 含有丰富的 §3 Design（架构/模块）、§4 Behavioral Requirements（行为约束）、§8 Known Limitations（已知限制）内容，这些天然映射到 prd-structure.yaml 的 `modules[]` / `nfrs[]` / `constraints[]`，但 skill-0 目前统统丢弃。导致用户要么：

- 手写 PRD 把这些字段补进去（重复劳动）
- 只拿 task-hints.yaml 给 skill-3，丢失架构上下文

## 3. Design

### 3.1 Architecture

design-spec 角色从**单派发**改为**双派发**：

```
role=design-spec
  → prd-extractor (新增 routing: "design-spec")
      → prd_structure (partial: modules + nfrs + constraints)
  → spec-extractor (unchanged)
      → task_hints (unchanged)
```

两个 extractor 共享同一份 in-memory state object，分别 append 到 `prd_structure` / `task_hints`。Phase 4.1 按现有逻辑决定写哪几个 YAML（非空即写）。

### 3.2 修改点

| 文件 | 改动类型 | 说明 |
|------|---------|------|
| `skills/skill-0-ingest/lib/prd-extractor.md` | 扩展 | "Role routing" 表加 `design-spec` 行；新增 "Extraction: role=design-spec" section |
| `skills/skill-0-ingest/lib/role-detector.md` | 更新 | `design-spec` 的 "Produces" 列从 `task-hints.yaml` 改为 `prd-structure.yaml (partial) + task-hints.yaml` |
| `skills/skill-0-ingest/SKILL.md` | 修改 | Phase 2 分派逻辑：`design-spec` 跑两个 extractor，结果合并 |
| `skills/skill-0-ingest/lib/cross-validator.md` | 扩展 | 新增 design-spec 相关 warning 类型 |
| `skills/skill-0-ingest/tests/fixtures/` | 新增 | design-spec 规范/松散/乱序/无编号 4 个 fixture |
| `skills/skill-0-ingest/tests/expected/` | 新增 | 对应 4 套 expected YAML |

**不改动**：
- 其他 extractor（gap-extractor / spec-extractor）
- 其他角色的行为
- skill-1 / skill-2 / skill-3 的消费逻辑
- Phase 4 写出机制

**Schema 扩展（non-breaking，可选字段，现有消费者忽略）**：
- `modules[].source: string`：标记模块来源（`"design-spec"` / `"prd"` / `"plan"`）。现有流程不填即为空，消费者可选用
- `modules[].coarse: bool`：design-spec fallback 时标记模块为粗粒度，供 skill-3 调粒度。缺省 `false`
- 复用已有字段 `modules[].prd_sections` / `nfrs[].prd_ref` / `constraints[].prd_ref` 存 source anchor（语义"文档定位"，字段名 legacy）

## 4. Behavioral Requirements

### 4.1 Section-to-Field Mapping

brainstorming skill 产出的 spec 章节映射到 prd-extractor（design-spec 子流程）字段：

| Spec section (CN / EN) | Output field | Notes |
|---|---|---|
| §1 目标 / Goal | — | **skip** — 纯散文 context，不强推断到字段 |
| §2 现状 / Current State | — | **skip** — 让用户需要时跑 /gap-scan |
| §3 设计 / Design / Architecture | `modules[]` | 见 §4.2 |
| §4 行为约束 / Behavioral Requirements | `nfrs[]` | 见 §4.3 |
| §5 变更 / Changes / File Changes | `file_changes[]` | spec-extractor 已覆盖 |
| §6 测试 / Tests / Test Strategy | `test_strategy` | spec-extractor 已覆盖 |
| §7 Rollout / Implementation Steps | `implementation_steps[]` | spec-extractor 已覆盖 |
| §8 已知限制 / Known Limitations | `constraints[]` | 见 §4.4 |

### 4.2 Heading 识别（兼容模式）

prd-extractor 的 design-spec 子流程**通篇扫 heading**，不假设顺序、不依赖编号：

- **modules（§3）**: 匹配 "设计", "Design", "Architecture", "方案", "架构"（任意组合，case-insensitive）
- **nfrs（§4）**: "行为约束", "Behavioral Requirements", "需求", "Requirements", "约束", "验收条件", "Acceptance"
- **constraints（§8）**: "已知限制", "Known Limitations", "Limitations", "Constraints", "已知约束"

**Numbered prefix 容忍**：同时支持 `## 3. 设计` / `## Design` / `## 3.1 路径解析层`（复用 spec-extractor 已有的 numbered-section-matching 逻辑）。

### 4.3 modules 抽取规则

- **有二级标题**：`### 3.1 路径解析层` → `{ id: "MOD-01", name: "路径解析层", description: <首段散文>, prd_sections: ["§3.1"], source: "design-spec", coarse: false }`
- **无二级标题**：整个 §3 塞进 `modules[0]`，`coarse: true`，description 取首段，`prd_sections: ["§3"]`
- **source 字段**（新 optional）：所有 design-spec 产出的 modules 标记 `source: "design-spec"`；skill-3 task-gen 可据此调节 expected-granularity

### 4.4 nfrs & constraints 抽取规则

- **nfrs**：§4 里每个 bullet / 编号列表项抽为 `{ id: NFR-N, category: <auto>, requirement: text, prd_ref: "§4.X" }`。category 按关键词启发：
  - 含 "性能/latency/QPS/throughput/延迟" → `performance`
  - 含 "兼容/backcompat/backward" → `compatibility`
  - 含 "安全/security/auth" → `security`
  - 其他 → `general`
  - `metric` / `target` 字段 design-spec 通常没有，留空或省略
- **constraints**：§8 同模式，`{ id: CON-N, type: <auto>, description, rationale, prd_ref: "§8.X" }`
  - type 按关键词：tech/tool → `technology`，schedule/date → `schedule`，其他 → `general`
  - `rationale` 若 §8 条目是 "X：理由" 格式，冒号后为 rationale；否则与 description 相同

### 4.5 user_stories 处理

design-spec 的输出**不含 user_stories**（字段 empty / 缺省）。这是刻意的：spec 关注"做什么/怎么做"，不是"谁为什么做"。想要 stories 的用户应该写 PRD 或 user-stories 文件（已有 prd 角色覆盖）。

## 5. Graceful Degradation

遵循 skill-0 "warn don't fail" 哲学。任一 section 缺失时：

| 场景 | 行为 | cross-validator warning |
|---|---|---|
| 缺 §3 Design | `modules: []` 空数组 | `"design-spec <file>: 无 §3 Design section, modules[] empty"` |
| 缺 §4 需求 | `nfrs: []` | `"design-spec <file>: 无 §4 Behavioral Requirements, nfrs[] empty"` |
| 缺 §8 限制 | `constraints: []` | `"design-spec <file>: 无 §8 Known Limitations, constraints[] empty"` |
| prd_structure 全空（§3/§4/§8 全缺） | 不写 prd-structure.yaml | `"design-spec <file>: produced no prd-structure content, output file skipped"` |
| §3 有内容但无二级标题 | fallback：整块为 modules[0]（`coarse: true`） | `"design-spec <file>: §3 Design has no sub-headings, treated as single coarse module"` |
| task_hints 也全空（§5/§6/§7 全缺） | 不写 task-hints.yaml | 已有 warning 不变 |
| 双 extractor 双空 | 两 YAML 都不写，但不 fatal | Phase 3 人工审阅表汇总情况 |

## 6. Testing

### 6.1 Fixture 组

| Fixture | 形态 | 预期输出 |
|---|---|---|
| `design-spec-full.md` | §1-§8 全齐全，有二级标题 | prd-structure.yaml + task-hints.yaml 都非空 |
| `design-spec-loose.md` | 只有 §5/§6 | task-hints.yaml 非空，prd-structure.yaml 不写 |
| `design-spec-unordered.md` | §8 出现在 §3 之前 | 正确抽取（顺序无关） |
| `design-spec-no-numbers.md` | 全用纯 heading `## Design`, `## Constraints` | 正确抽取 |

### 6.2 Acceptance Tests

- **T1 规范化 spec**: `design-spec-full.md` → prd-structure.yaml 含 ≥1 module + ≥1 nfr + ≥1 constraint + task-hints.yaml 含 file_changes
- **T2 松散 spec**: `design-spec-loose.md` → 只产 task-hints.yaml，prd-structure.yaml 不写（skip warning 记录）
- **T3 乱序 spec**: `design-spec-unordered.md` → 输出等价于规范化版本（顺序不影响内容）
- **T4 无编号 spec**: `design-spec-no-numbers.md` → 输出等价于规范化版本
- **T5 Cross-validation**: 同时喂 `design-spec-full.md` + 独立 gap 文档 → cross-validator 跑完无 fatal
- **T6 向后兼容（关键）**:
  - 现有**非 design-spec** fixture（prd / plan / user-stories / gap）产物逐字节一致 —— 我的改动不能影响其他角色
  - 现有 design-spec fixture 的产物会**扩充**（新增 prd-structure.yaml 或扩展已有），expected YAML 需同步更新；task-hints.yaml 字段保持不变

### 6.3 Cross-validation 断言

- design-spec 产 modules 后跑 prd-structure.yaml 的模块 id 唯一性检查（不和其他角色合并的 modules 碰撞）
- design-spec 产的 constraints 和 task-hints 的 non_goals 如有语义重叠，log info（不 warn）

## 7. Rollout

此改动侵入性小，**不分阶段**。以单一 feature branch 提交，预期 4-6 commits：

1. `feat(skill-0-ingest)`: extend prd-extractor with design-spec routing
2. `feat(skill-0-ingest)`: update role-detector Produces column
3. `feat(skill-0-ingest)`: Phase 2 双派发逻辑
4. `feat(skill-0-ingest)`: cross-validator design-spec warnings
5. `test(skill-0-ingest)`: 4 新 fixtures + expected YAMLs
6. `docs`: README / using-prd2impl 更新（如需）

不需要版本 bump 到 0.3.0 —— 这是 0.2.x patch（功能扩展，不破坏现有行为）。考虑 0.2.1。

## 8. Known Limitations

1. **modules 粒度**：design-spec 的 §3 如果只有散文无分块（无二级标题），会 fallback 为单个 coarse module。skill-3 task-gen 下游看到 `coarse: true` 时粒度会粗（大任务），用户可选择手动拆分后重跑。

2. **user_stories 永远为空**：design-spec 不生成 user-stories。用户若需要完整 prd-structure，应搭配一份独立的 user-stories 文件（走 user-stories 角色）或写 PRD。

3. **§2 现状被丢弃**：design-spec 的 "Current State" 散文不映射到任何 YAML 字段。用户若要对代码核对现状，应跑 `/gap-scan`（skill-2）或写独立 gap 文件。不做"语义推断现状 = gap" 是故意的 —— LLM 推断容易和真实代码脱节。

4. **category / type 启发是弱推断**：nfrs 的 category 和 constraints 的 type 用关键词启发，不是 100% 准确。用户可在产出的 YAML 里手改。

5. **cross-validation 不合并同义模块**：两份 design-spec 若各自定义 "路径解析层" 模块，会出现 `MOD-01` 和 `MOD-02` 两个 id。cross-validator 检测 id 唯一但不判语义相似度。用户需手动合并。

6. **不触发 writing-plans 直接衔接**：本特性产出的 prd-structure.yaml 走 skill-3 task-gen，而不是直接给 superpowers:writing-plans。两条路线并行：skill-3 用于团队协作 / prd2impl pipeline，writing-plans 用于单工执行。用户按场景选。

---

## Appendix: Mapping 示例

以本文档自身（`2026-04-21-design-spec-ingest-design.md`）为例跑一遍 design-spec 抽取：

```yaml
prd_structure:
  # §1 Goal 和 §2 Current State 故意不抽（skip）
  modules:
    - id: MOD-01
      name: "prd-extractor design-spec routing"
      description: "design-spec 角色从单派发改为双派发..."
      prd_sections: ["§3.1"]
      source: "design-spec"
      coarse: false
    # ... §3.2 修改点表抽为 sub-modules 或 single module
  nfrs:
    - id: NFR-01
      category: compatibility
      requirement: "兼容规范/松散/乱序/无编号 4 种 spec 形态"
      prd_ref: "§4.2"
    - id: NFR-02
      category: general
      requirement: "warn don't fail 哲学"
      prd_ref: "§5"
    # ...
  constraints:
    - id: CON-01
      type: general
      description: "modules 粒度：§3 无二级标题时 fallback 为 coarse"
      prd_ref: "§8.1"
    # ...

task_hints:
  file_changes:
    - path: "skills/skill-0-ingest/lib/prd-extractor.md"
      change_type: modify
      purpose: "加 design-spec routing"
    # ...
  implementation_steps:
    - "1. feat: extend prd-extractor with design-spec routing"
    # ...
  non_goals: []
  test_strategy: "fixture-driven: 4 fixtures covering full/loose/unordered/no-number"
  risks: []
```

这个 Appendix 也起到 self-dogfooding 作用：本 spec 的作者可以手动 review 上面 YAML 和原文的对应关系，发现漏字段或 heading 识别失败的 case。
