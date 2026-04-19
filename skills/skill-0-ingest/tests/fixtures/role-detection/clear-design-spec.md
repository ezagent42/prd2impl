# Admin Portal Web Layout — Design Spec

**Status:** Approved
**Date:** 2026-04-18

## 1. Architecture

Three-panel shell: TopBar + VerticalRail + Canvas.

## 2. Component Tree

```
AdminShell
├── AdminTopbar
├── AdminRail
└── <canvas slot>
    └── <active tab content>
```

## 3. File Changes

### New files

| File | Purpose |
|------|---------|
| `src/components/shell/AdminShell.tsx` | root layout |
| `src/components/shell/AdminTopbar.tsx` | breadcrumb nav |
| `src/components/shell/AdminRail.tsx` | vertical nav |

### Modified files

| File | Change |
|------|--------|
| `src/App.tsx` | wire AdminShell |
| `src/index.css` | grid variables |

## 4. Non-Goals

- No design-system changes (tokens.css unchanged)
- No mobile-specific UX
- No real ⌘K search

## 5. Implementation Steps

1. Build AdminShell + AdminTopbar + AdminRail + CSS grid
2. Wire App.tsx → AdminShell
3. Adapt existing tab components to canvas slot
4. Write unit tests for shell

## 6. Testing

- Preserved data-testids: `tab-wizard`, `tab-dashboard`, `tab-billing`
- New: `AdminShell.test.tsx`, `AdminRail.test.tsx`
- E2E delta: none
