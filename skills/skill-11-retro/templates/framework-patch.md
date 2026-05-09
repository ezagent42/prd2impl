# Framework Patch — {slug}

**Source retro**: {plans_dir}/retro-{milestone}-{date}.md (suggestion {N})
**Target skill file**: `skills/{target}/SKILL.md`
**Insertion section**: {section_heading_or_line}
**Pressure-tested via writing-skills**: yes / no / skipped (no superpowers)

---

## Baseline scenario (runnable failure)

> 1–3 sentence description, including a concrete commit / file /
> task-id reference when available. An engineer reading this should
> be able to manually replay the bug under the current rules
> (without the patch).

Example:

> Yellow task T4M.3 (PV2 milestone) ships `runner.prewarm` calling
> `pool.acquire_for_session(conv_id, tenant_id, role=role)`. The real
> `autoservice.cc_pool.CCPool` defines no such method; only
> `acquire_sticky(key, *, tenant_id=None, timeout=None)`. Current
> skill-13 yellow review (commit `cdcfdb2`) approves the diff because
> the test fake `_FakePool` mirrors the fictional API. Expected after
> patch: review fails because Stage A spec-compliance reviewer flags
> the unresolved symbol.

## Proposed rule

> Concrete markdown to insert into target SKILL.md, ready to copy-paste.
> If it modifies an existing block, give a unified-diff-style snippet.

Example:

```markdown
### Yellow review (two-stage)

Stage A — Spec compliance reviewer:
- "Did the diff add ANY code, files, helpers, flags, or tests not
  requested by the task spec? List every extra."
- "For every external symbol called in the diff, does it resolve on
  the real production class? Reject if any call targets a method
  that does not exist on HEAD."
```

## Pressure test result

> If `superpowers:writing-skills` was invoked: report whether the new
> rule caught the baseline. Quote the writing-skills output verbatim.
> If skipped: note "skipped — superpowers not installed; manual
> verification required before applying patch."

## How to apply

1. Open `skills/{target}/SKILL.md`.
2. Find {section_heading} (or insert after line {N}).
3. Paste the "Proposed rule" block verbatim.
4. Replay the baseline scenario; confirm the rule fires.
5. Commit with message:
   ```
   feat({target}): {short rule description} (retro {milestone})

   Closes retro suggestion {N}: {one-line summary}.

   Spec/Plan reference: {plans_dir}/retro-{milestone}-{date}.md
   ```
6. Tag the prd2impl release accordingly.

## Linked artifacts

- Source retro report: {plans_dir}/retro-{milestone}-{date}.md
- Source memory (if applicable): {project memory file path}
- Originating commit (the bug):  {commit-hash}
- Reproducing test (if applicable): tests/path/to/test.py
