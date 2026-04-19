# Admin Portal — Shell Refactor Notes

Internal working notes from the frontend team.

These notes describe the planned changes to the admin portal shell layout.
The topbar and rail components need to be extracted from the monolithic App.tsx
into their own files to support the new navigation model.

## File Changes

The following files will be created or modified:

- `src/components/shell/AdminShell.tsx` — new root layout wrapper
- `src/components/shell/AdminTopbar.tsx` — extracted topbar
- `src/App.tsx` — simplified to use AdminShell

## Implementation Notes

Start with the shell component, then wire App.tsx, then adapt the tabs.
Do not change tokens.css or the design system.

## Open Questions

- Should AdminRail use CSS grid or flex?
- Who owns the data-testid for the new shell?
