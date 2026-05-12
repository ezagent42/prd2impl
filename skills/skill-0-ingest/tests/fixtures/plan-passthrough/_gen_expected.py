"""One-shot generator for tests/expected/admin-v2-p1.task-hints.yaml.

Implements plan-parser.md rules 1-4 in Python to produce the canonical
expected output. Run from prd2impl repo root:

    python3 skills/skill-0-ingest/tests/fixtures/plan-passthrough/_gen_expected.py

The output is written to skills/skill-0-ingest/tests/expected/.

This script is NOT consumed by any skill — it's a one-shot to produce the
expected fixture. plan-parser.md is the contract; this script just gives
a Python embodiment for fixture generation.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

FIXTURE = Path("skills/skill-0-ingest/tests/fixtures/plan-passthrough/admin-v2-p1-cr-data-layer.md")
EXPECTED = Path("skills/skill-0-ingest/tests/expected/admin-v2-p1.task-hints.yaml")
SOURCE_PLAN_PATH = "docs/superpowers/plans/2026-05-11-admin-v2-p1-cr-data-layer.md"


def slugify(heading_text: str) -> str:
    """Rule 1: GitHub-style slug. Lowercase, spaces→-, strip non-[a-z0-9_-],
    preserve consecutive dashes, trim leading/trailing -."""
    s = heading_text.lower()
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"[^a-z0-9_-]", "", s)
    return s.strip("-")


def parse_files_block(body: str) -> dict:
    """Rule 3: extract **Files:** block; group bullets by verb."""
    out = {"create": [], "modify": [], "test": [], "delete": []}
    lines = body.split("\n")
    in_block = False
    started_after_files = False
    for line in lines:
        if line.strip() == "**Files:**":
            in_block = True
            started_after_files = True
            continue
        if not in_block:
            continue
        # End on first - [ ] **Step or ### Task or ## or EOF
        if re.match(r"^- \[[ x]\] \*\*Step ", line) or line.startswith("### Task ") or line.startswith("## "):
            break
        # Skip blank lines (don't terminate; some plans have blank line between Files and first bullet)
        if not line.strip():
            continue
        m = re.match(r"^- (Create|Modify|Test|Delete):\s+`([^`]+)`", line, re.IGNORECASE)
        if m:
            verb = m.group(1).lower()
            path = m.group(2).strip()
            out[verb].append(path)
    return out


def parse_steps(body: str) -> list:
    """Rule 4: extract - [ ] / - [x] **Step N: <desc>** entries (whole heading bolded) plus body flags."""
    out = []
    lines = body.split("\n")
    step_starts = []
    for i, line in enumerate(lines):
        m = re.match(r"^- \[[ x]\] \*\*Step (\d+):\s*(.+?)\*\*\s*$", line)
        if m:
            step_starts.append((i, int(m.group(1)), m.group(2).strip()))

    for idx, (start_line, step_index, description) in enumerate(step_starts):
        end_line = len(lines)
        # body is between this step and the next step / next ### Task / next ## heading
        for j in range(start_line + 1, len(lines)):
            if re.match(r"^- \[[ x]\] \*\*Step ", lines[j]):
                end_line = j
                break
            if lines[j].startswith("### Task ") or lines[j].startswith("## "):
                end_line = j
                break
        body_lines = lines[start_line + 1 : end_line]
        body_text = "\n".join(body_lines)
        has_code_block = bool(re.search(r"^```", body_text, re.MULTILINE))
        has_run_command = bool(re.search(r"^Run:\s", body_text, re.MULTILINE))
        out.append(
            {
                "step_index": step_index,
                "description": description,
                "has_code_block": has_code_block,
                "has_run_command": has_run_command,
            }
        )
    return out


def parse_plan(text: str, source_plan_path: str) -> list:
    """Rule 1+2: discover tasks, slice bodies, build entries."""
    lines = text.split("\n")
    # Find task heading line numbers
    task_lines = []
    for i, line in enumerate(lines):
        m = re.match(r"^### Task (\d+):\s*(.+)$", line)
        if m:
            task_lines.append((i, int(m.group(1)), m.group(2).rstrip()))

    tasks = []
    for k, (line_no, task_index, name) in enumerate(task_lines):
        # Body ends at next ### Task, or next ## (not ###), or EOF
        body_end = len(lines)
        for j in range(line_no + 1, len(lines)):
            if lines[j].startswith("### Task "):
                body_end = j
                break
            if re.match(r"^## [^#]", lines[j]):
                body_end = j
                break
        body = "\n".join(lines[line_no + 1 : body_end])

        anchor = slugify(f"Task {task_index}: {name}")
        files = parse_files_block(body)
        steps = parse_steps(body)
        tasks.append(
            {
                "task_index": task_index,
                "name": name,
                "source_plan_path": source_plan_path,
                "source_plan_anchor": anchor,
                "files": files,
                "steps": steps,
            }
        )
    return tasks


def main() -> None:
    text = FIXTURE.read_text(encoding="utf-8")
    tasks = parse_plan(text, SOURCE_PLAN_PATH)

    payload = {
        "task_hints": {
            "source_files": [SOURCE_PLAN_PATH],
            "source_type": "ingested",
            "tasks": tasks,
        }
    }

    EXPECTED.parent.mkdir(parents=True, exist_ok=True)
    header = (
        "# Expected output of plan-parser applied to\n"
        "# tests/fixtures/plan-passthrough/admin-v2-p1-cr-data-layer.md\n"
        "# Generated by tests/fixtures/plan-passthrough/_gen_expected.py — regen by re-running it.\n"
        "# This file is the canonical assertion when skill-0 ingests the p1 plan.\n"
        "\n"
    )
    EXPECTED.write_text(
        header + yaml.safe_dump(payload, sort_keys=False, allow_unicode=True, width=200),
        encoding="utf-8",
    )

    # Sanity-check counts vs fixture
    total_steps = sum(len(t["steps"]) for t in tasks)
    total_create = sum(len(t["files"]["create"]) for t in tasks)
    total_modify = sum(len(t["files"]["modify"]) for t in tasks)
    print(f"tasks: {len(tasks)}")
    print(f"total steps: {total_steps}")
    print(f"total create files: {total_create}")
    print(f"total modify files: {total_modify}")
    print(f"wrote: {EXPECTED}")


if __name__ == "__main__":
    main()
