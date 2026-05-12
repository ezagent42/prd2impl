# Admin V2 — P1: CR Data Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the foundational Change Request (CR) abstraction layer — `change_requests` + `cr_audit` tables in `database/audit.db`, full CRUD repository, state machine, partial-unique-index concurrency guard, `/api/crs/*` HTTP surface, integration with existing publish/rollback endpoints, `manifest.yaml` cr_id/source/actor extension, legacy publish wrapper, and a one-shot backfill script for snapshot Phase 1's pre-existing release versions.

**Architecture:** New module `autoservice/change_request/` owns schema, models, repository, state machine, and HTTP routes; existing `autoservice/api_routes.py` `POST /api/tenants/:tid/publish` and `/rollback` handlers are extended to require/produce CR rows; V1 `POST /api/tenants/:tid/publish` is renamed to `/api/legacy/tenants/:tid/publish` and wrapped to auto-create a `source='legacy_publish'` CR (preserving V1 PublishPanel and existing e2e tests); `autoservice/release_snapshot.py::build_release_snapshot` adds 3 manifest fields (`cr_id`, `cr_source`, `cr_actor`); `scripts/backfill_cr_for_releases.py` walks existing `released/<tid>/v<N>/` dirs and writes one `source='migration'` CR per version.

**Tech Stack:**
- Python 3.13+ (project standard)
- SQLite via `sqlite3` stdlib (connect-per-call, WAL mode — same pattern as `tenant_pointer.py`)
- FastAPI + pydantic (existing in repo)
- pytest + pytest-asyncio
- Reuses existing modules: [autoservice/tenant_paths.py](../../autoservice/tenant_paths.py), [autoservice/tenant_pointer.py](../../autoservice/tenant_pointer.py), [autoservice/release_snapshot.py](../../autoservice/release_snapshot.py), [autoservice/publish_lock.py](../../autoservice/publish_lock.py), [autoservice/publish.py](../../autoservice/publish.py), [autoservice/api_routes.py](../../autoservice/api_routes.py), [autoservice/auth.py](../../autoservice/auth.py)

**File Structure:**

```
# New
autoservice/change_request/
  __init__.py              ← re-exports public API
  schema.py                ← SQL CREATE TABLE constants
  models.py                ← @dataclass CR + CRAudit + CRStatus / CRSource enums
  repository.py            ← create_cr / load_cr / list_crs / update_status / append_audit
  state_machine.py         ← TRANSITIONS table + validate_transition + custom exceptions
  api_routes.py            ← /api/crs/* HTTP endpoints (mounted under main api_router)

autoservice/legacy_routes.py ← /api/legacy/* sub-router (only legacy_publish endpoint in P1)
scripts/backfill_cr_for_releases.py ← one-shot backfill

# Modified
autoservice/release_snapshot.py     ← manifest.yaml writer accepts cr_id/cr_source/cr_actor
autoservice/api_routes.py           ← publish/rollback handlers integrate with CR layer
autoservice/publish.py              ← check_publish_gate() signature accepts cr_id (validated upstream)

# New tests
tests/change_request/
  __init__.py
  conftest.py              ← fixture: clean audit.db per test
  test_schema.py
  test_models.py
  test_repository_crud.py
  test_repository_list.py
  test_state_machine.py
  test_active_cr_unique.py
  test_api_routes.py
tests/release_snapshot/
  test_manifest_cr_fields.py
tests/api_routes/
  test_publish_with_cr.py
  test_rollback_inverse_cr.py
  test_legacy_publish_wrapper.py
tests/scripts/
  test_backfill_cr_for_releases.py
```

**TDD Discipline:** Every task follows the five-step rhythm — write failing test, run to confirm right failure mode, write minimal implementation, run to confirm pass, commit. Don't deviate. Don't batch. A passing test on the first run means the test isn't testing the new behavior.

---

## Phase A — Foundation (schema + models + repo)

### Task 1: Create `change_request` package skeleton + `audit.db` schema

**Files:**
- Create: `autoservice/change_request/__init__.py`
- Create: `autoservice/change_request/schema.py`
- Create: `tests/change_request/__init__.py` (empty)
- Create: `tests/change_request/conftest.py`
- Create: `tests/change_request/test_schema.py`

- [ ] **Step 1: Create the conftest.py fixture (used by all later tasks)**

Create `tests/change_request/conftest.py`:

```python
"""Shared fixtures for change_request tests.

Uses a per-test isolated audit.db by overriding AUTOSERVICE_RUNTIME_DATA_DIR
to a tmp_path subdirectory. Schema is re-applied on each test connection
(idempotent CREATE TABLE IF NOT EXISTS).
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.fixture
def isolated_audit_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point AUTOSERVICE_RUNTIME_DATA_DIR at tmp_path so audit.db lives there."""
    monkeypatch.setenv("AUTOSERVICE_RUNTIME_DATA_DIR", str(tmp_path))
    return tmp_path / "audit.db"
```

- [ ] **Step 2: Write the failing schema test**

Create `tests/change_request/test_schema.py`:

```python
"""Schema sanity — both tables exist with expected columns."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from autoservice.change_request import schema as cr_schema


def test_apply_schema_creates_change_requests(isolated_audit_db: Path):
    isolated_audit_db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(isolated_audit_db))
    conn.executescript(cr_schema.SCHEMA_SQL)
    cols = {
        row[1]
        for row in conn.execute("PRAGMA table_info(change_requests)").fetchall()
    }
    expected = {
        "id", "tenant_id", "source", "actor", "title", "description",
        "status", "sandbox_diff", "parent_cr_id", "target_release_ver",
        "rolled_back_to_ver", "metadata_json", "created_at", "updated_at",
        "closed_at",
    }
    assert expected <= cols, f"missing columns: {expected - cols}"
    conn.close()


def test_apply_schema_creates_cr_audit(isolated_audit_db: Path):
    isolated_audit_db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(isolated_audit_db))
    conn.executescript(cr_schema.SCHEMA_SQL)
    cols = {
        row[1] for row in conn.execute("PRAGMA table_info(cr_audit)").fetchall()
    }
    assert {"id", "cr_id", "ts", "actor", "action", "payload"} <= cols
    conn.close()


def test_schema_is_idempotent(isolated_audit_db: Path):
    isolated_audit_db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(isolated_audit_db))
    conn.executescript(cr_schema.SCHEMA_SQL)
    # second apply must not raise
    conn.executescript(cr_schema.SCHEMA_SQL)
    conn.close()
```

- [ ] **Step 3: Run test to verify it fails**

```bash
uv run pytest tests/change_request/test_schema.py -v
```

Expected: `ModuleNotFoundError: No module named 'autoservice.change_request'`

- [ ] **Step 4: Write minimal schema module**

Create `autoservice/change_request/__init__.py`:

```python
"""CR (Change Request) data layer.

See docs/superpowers/specs/2026-05-11-admin-v2-design.md §2.
"""
from autoservice.change_request import schema

__all__ = ["schema"]
```

Create `autoservice/change_request/schema.py`:

```python
"""SQL schema for the Change Request layer.

Tables live in database/audit.db (platform-wide, not per-tenant).
Schema is idempotent — safe to apply on every connection.
"""
from __future__ import annotations

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS change_requests (
    id                  TEXT PRIMARY KEY,
    tenant_id           TEXT NOT NULL,
    source              TEXT NOT NULL,
    actor               TEXT NOT NULL,
    title               TEXT NOT NULL,
    description         TEXT,
    status              TEXT NOT NULL,
    sandbox_diff        TEXT,
    parent_cr_id        TEXT,
    target_release_ver  TEXT,
    rolled_back_to_ver  TEXT,
    metadata_json       TEXT,
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL,
    closed_at           TEXT,
    FOREIGN KEY(parent_cr_id) REFERENCES change_requests(id)
);

CREATE INDEX IF NOT EXISTS idx_cr_tenant_status
    ON change_requests(tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_cr_source
    ON change_requests(source);
CREATE INDEX IF NOT EXISTS idx_cr_created
    ON change_requests(created_at);

CREATE TABLE IF NOT EXISTS cr_audit (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    cr_id    TEXT NOT NULL,
    ts       TEXT NOT NULL,
    actor    TEXT NOT NULL,
    action   TEXT NOT NULL,
    payload  TEXT,
    FOREIGN KEY(cr_id) REFERENCES change_requests(id)
);

CREATE INDEX IF NOT EXISTS idx_cr_audit_cr
    ON cr_audit(cr_id, ts);
"""
```

Note: the `uq_active_cr_per_tenant` partial unique index is added in **Task 7**, not here. Keep the foundation schema minimal so early tasks can insert duplicates while testing other concerns.

- [ ] **Step 5: Run test to verify it passes**

```bash
uv run pytest tests/change_request/test_schema.py -v
```

Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add autoservice/change_request/__init__.py autoservice/change_request/schema.py tests/change_request/__init__.py tests/change_request/conftest.py tests/change_request/test_schema.py
git commit -m "feat(change_request): audit.db schema for change_requests + cr_audit tables"
```

---

### Task 2: CR + CRAudit dataclass models with `CRStatus` / `CRSource` enums

**Files:**
- Create: `autoservice/change_request/models.py`
- Create: `tests/change_request/test_models.py`

- [ ] **Step 1: Write the failing model test**

Create `tests/change_request/test_models.py`:

```python
"""@dataclass models for CR and CRAudit + status/source enums."""
from __future__ import annotations

import pytest

from autoservice.change_request import models


def test_cr_status_enum_has_all_six_values():
    expected = {
        "draft", "ready_for_review", "publishing",
        "published", "rolled_back", "abandoned",
    }
    assert {s.value for s in models.CRStatus} == expected


def test_cr_source_enum_has_all_seven_values():
    expected = {
        "manual", "docs_regen", "dream_proposal", "master_dream",
        "legacy_publish", "rollback", "migration",
    }
    assert {s.value for s in models.CRSource} == expected


def test_cr_construction_with_required_fields():
    cr = models.CR(
        id="cr_test123",
        tenant_id="cinnox",
        source=models.CRSource.MANUAL,
        actor="admin@h2os.cloud",
        title="Bump customer soul",
        status=models.CRStatus.DRAFT,
        created_at="2026-05-11T00:00:00+00:00",
        updated_at="2026-05-11T00:00:00+00:00",
    )
    assert cr.id == "cr_test123"
    assert cr.source is models.CRSource.MANUAL
    assert cr.description is None
    assert cr.parent_cr_id is None
    assert cr.closed_at is None


def test_cr_generate_id_has_correct_prefix_and_length():
    new_id = models.generate_cr_id()
    assert new_id.startswith("cr_")
    assert len(new_id) == 3 + 12  # "cr_" + 12 hex chars


def test_cr_audit_construction():
    audit = models.CRAudit(
        cr_id="cr_test123",
        ts="2026-05-11T00:00:00+00:00",
        actor="admin@h2os.cloud",
        action="created",
        payload=None,
    )
    assert audit.action == "created"
```

- [ ] **Step 2: Run to verify it fails**

```bash
uv run pytest tests/change_request/test_models.py -v
```

Expected: `ImportError: cannot import name 'models'` or similar.

- [ ] **Step 3: Write minimal models module**

Create `autoservice/change_request/models.py`:

```python
"""@dataclass models + status/source enums for the CR layer.

See docs/superpowers/specs/2026-05-11-admin-v2-design.md §2.1, §2.2, §2.3.
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class CRStatus(str, Enum):
    """States in the CR lifecycle. See spec §2.2 for the transition matrix."""
    DRAFT = "draft"
    READY_FOR_REVIEW = "ready_for_review"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    ROLLED_BACK = "rolled_back"
    ABANDONED = "abandoned"


class CRSource(str, Enum):
    """Origin of a CR. See spec §2.3 for semantics per source."""
    MANUAL = "manual"
    DOCS_REGEN = "docs_regen"
    DREAM_PROPOSAL = "dream_proposal"
    MASTER_DREAM = "master_dream"
    LEGACY_PUBLISH = "legacy_publish"
    ROLLBACK = "rollback"
    MIGRATION = "migration"


def generate_cr_id() -> str:
    """cr_<hex12>. 12 hex chars = 48 bits; collision probability negligible
    for our scale (single-digit-billion CRs would be needed for 1% chance)."""
    return f"cr_{secrets.token_hex(6)}"


@dataclass
class CR:
    """A row from the change_requests table.

    Required fields are the SQL NOT NULL columns. Optional fields default
    to None and may be filled later in the lifecycle (e.g. target_release_ver
    is set when status flips to published).
    """
    id: str
    tenant_id: str
    source: CRSource
    actor: str
    title: str
    status: CRStatus
    created_at: str
    updated_at: str
    description: Optional[str] = None
    sandbox_diff: Optional[str] = None             # JSON metadata
    parent_cr_id: Optional[str] = None
    target_release_ver: Optional[str] = None
    rolled_back_to_ver: Optional[str] = None
    metadata_json: Optional[str] = None
    closed_at: Optional[str] = None


@dataclass
class CRAudit:
    """A row from the cr_audit table — one per state change or event."""
    cr_id: str
    ts: str
    actor: str
    action: str
    payload: Optional[str] = None                  # JSON, action-specific
    id: Optional[int] = None                       # autoincrement, set by DB
```

Update `autoservice/change_request/__init__.py`:

```python
"""CR (Change Request) data layer.

See docs/superpowers/specs/2026-05-11-admin-v2-design.md §2.
"""
from autoservice.change_request import models, schema
from autoservice.change_request.models import CR, CRAudit, CRSource, CRStatus

__all__ = ["CR", "CRAudit", "CRSource", "CRStatus", "models", "schema"]
```

- [ ] **Step 4: Run to verify it passes**

```bash
uv run pytest tests/change_request/test_models.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add autoservice/change_request/__init__.py autoservice/change_request/models.py tests/change_request/test_models.py
git commit -m "feat(change_request): CR / CRAudit dataclasses + CRStatus / CRSource enums"
```

---

### Task 3: Repository — `create_cr` + `load_cr`

**Files:**
- Create: `autoservice/change_request/repository.py`
- Create: `tests/change_request/test_repository_crud.py`

- [ ] **Step 1: Write the failing CRUD test**

Create `tests/change_request/test_repository_crud.py`:

```python
"""create_cr / load_cr roundtrip + missing-row handling."""
from __future__ import annotations

from pathlib import Path

import pytest

from autoservice.change_request import repository as repo
from autoservice.change_request.models import CRSource, CRStatus


def test_create_cr_returns_id_and_persists(isolated_audit_db: Path):
    cr_id = repo.create_cr(
        tenant_id="cinnox",
        source=CRSource.MANUAL,
        actor="admin@h2os.cloud",
        title="Test CR",
    )
    assert cr_id.startswith("cr_")
    loaded = repo.load_cr(cr_id)
    assert loaded is not None
    assert loaded.tenant_id == "cinnox"
    assert loaded.source is CRSource.MANUAL
    assert loaded.status is CRStatus.DRAFT     # default for normal sources
    assert loaded.actor == "admin@h2os.cloud"


def test_load_cr_returns_none_for_unknown_id(isolated_audit_db: Path):
    assert repo.load_cr("cr_does_not_exist") is None


def test_create_cr_writes_initial_audit_row(isolated_audit_db: Path):
    cr_id = repo.create_cr(
        tenant_id="cinnox",
        source=CRSource.DOCS_REGEN,
        actor="admin@h2os.cloud",
        title="Bump KB",
    )
    audits = repo.list_audit(cr_id)
    assert len(audits) == 1
    assert audits[0].action == "created"
    assert audits[0].actor == "admin@h2os.cloud"


def test_create_cr_with_initial_status_published(isolated_audit_db: Path):
    """source='legacy_publish' / 'rollback' / 'migration' can start at published."""
    cr_id = repo.create_cr(
        tenant_id="cinnox",
        source=CRSource.LEGACY_PUBLISH,
        actor="legacy-apply-wrapper",
        title="V1 publish at ...",
        initial_status=CRStatus.PUBLISHED,
    )
    loaded = repo.load_cr(cr_id)
    assert loaded.status is CRStatus.PUBLISHED
    assert loaded.closed_at is not None         # terminal → closed_at filled
```

- [ ] **Step 2: Run to verify it fails**

```bash
uv run pytest tests/change_request/test_repository_crud.py -v
```

Expected: `ImportError: cannot import name 'repository'`.

- [ ] **Step 3: Write the minimal repository module**

Create `autoservice/change_request/repository.py`:

```python
"""SQLite-backed CRUD for change_requests + cr_audit.

Thread-safety: connect-per-call (sqlite3 connections aren't thread-safe by
default and FastAPI may dispatch from worker threads). The audit DB is small
and writes are infrequent, so connect overhead is negligible.

Path resolution: AUTOSERVICE_RUNTIME_DATA_DIR / audit.db. Honors env-var
override the same way tenant_paths does — see autoservice/tenant_paths.py.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from autoservice import tenant_paths
from autoservice.change_request import schema as cr_schema
from autoservice.change_request.models import (
    CR,
    CRAudit,
    CRSource,
    CRStatus,
    generate_cr_id,
)


_TERMINAL_STATUSES = {CRStatus.PUBLISHED, CRStatus.ROLLED_BACK, CRStatus.ABANDONED}


def _db_path() -> Path:
    """audit.db lives in the runtime-data root (platform-wide)."""
    root = tenant_paths.runtime_data_root()
    root.mkdir(parents=True, exist_ok=True)
    return root / "audit.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_db_path()))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.executescript(cr_schema.SCHEMA_SQL)
    return conn


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_cr(
    *,
    tenant_id: str,
    source: CRSource,
    actor: str,
    title: str,
    description: Optional[str] = None,
    initial_status: CRStatus = CRStatus.DRAFT,
    parent_cr_id: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> str:
    """Insert a new CR row + the initial 'created' audit entry.

    Returns the new cr_id.
    """
    cr_id = generate_cr_id()
    now = _now_iso()
    closed_at = now if initial_status in _TERMINAL_STATUSES else None
    metadata_json = json.dumps(metadata) if metadata else None

    with closing(_connect()) as conn, conn:
        conn.execute(
            "INSERT INTO change_requests "
            "(id, tenant_id, source, actor, title, description, status, "
            " parent_cr_id, metadata_json, created_at, updated_at, closed_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                cr_id, tenant_id, source.value, actor, title, description,
                initial_status.value, parent_cr_id, metadata_json,
                now, now, closed_at,
            ),
        )
        conn.execute(
            "INSERT INTO cr_audit (cr_id, ts, actor, action, payload) "
            "VALUES (?, ?, ?, 'created', ?)",
            (cr_id, now, actor,
             json.dumps({"source": source.value, "title": title})),
        )
    return cr_id


def load_cr(cr_id: str) -> Optional[CR]:
    with closing(_connect()) as conn, conn:
        row = conn.execute(
            "SELECT id, tenant_id, source, actor, title, description, status, "
            "       sandbox_diff, parent_cr_id, target_release_ver, "
            "       rolled_back_to_ver, metadata_json, created_at, updated_at, "
            "       closed_at FROM change_requests WHERE id=?",
            (cr_id,),
        ).fetchone()
    if row is None:
        return None
    return CR(
        id=row[0], tenant_id=row[1], source=CRSource(row[2]), actor=row[3],
        title=row[4], description=row[5], status=CRStatus(row[6]),
        sandbox_diff=row[7], parent_cr_id=row[8], target_release_ver=row[9],
        rolled_back_to_ver=row[10], metadata_json=row[11],
        created_at=row[12], updated_at=row[13], closed_at=row[14],
    )


def list_audit(cr_id: str) -> list[CRAudit]:
    """Audit chain for one CR, oldest-first."""
    with closing(_connect()) as conn, conn:
        rows = conn.execute(
            "SELECT id, cr_id, ts, actor, action, payload "
            "FROM cr_audit WHERE cr_id=? ORDER BY ts ASC, id ASC",
            (cr_id,),
        ).fetchall()
    return [
        CRAudit(
            id=r[0], cr_id=r[1], ts=r[2], actor=r[3], action=r[4], payload=r[5]
        )
        for r in rows
    ]
```

- [ ] **Step 4: Run to verify it passes**

```bash
uv run pytest tests/change_request/test_repository_crud.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add autoservice/change_request/repository.py tests/change_request/test_repository_crud.py
git commit -m "feat(change_request): repository — create_cr / load_cr / list_audit"
```

---

### Task 4: Repository — `list_crs` with filters

**Files:**
- Modify: `autoservice/change_request/repository.py` (append list_crs)
- Create: `tests/change_request/test_repository_list.py`

- [ ] **Step 1: Write failing list test**

Create `tests/change_request/test_repository_list.py`:

```python
"""list_crs — filter by tenant_id / status / source, newest-first."""
from __future__ import annotations

from pathlib import Path

import pytest

from autoservice.change_request import repository as repo
from autoservice.change_request.models import CRSource, CRStatus


@pytest.fixture
def three_crs(isolated_audit_db: Path) -> list[str]:
    ids = [
        repo.create_cr(
            tenant_id="cinnox", source=CRSource.MANUAL,
            actor="a@x.com", title="A",
        ),
        repo.create_cr(
            tenant_id="cinnox", source=CRSource.DREAM_PROPOSAL,
            actor="dream-auto", title="B",
        ),
        repo.create_cr(
            tenant_id="acme", source=CRSource.MANUAL,
            actor="a@x.com", title="C",
        ),
    ]
    return ids


def test_list_crs_filters_by_tenant_id(three_crs):
    rows = repo.list_crs(tenant_id="cinnox")
    assert len(rows) == 2
    assert {r.tenant_id for r in rows} == {"cinnox"}


def test_list_crs_filters_by_status(three_crs):
    rows = repo.list_crs(tenant_id="cinnox", status=CRStatus.DRAFT)
    assert len(rows) == 2


def test_list_crs_filters_by_source(three_crs):
    rows = repo.list_crs(tenant_id="cinnox", source=CRSource.DREAM_PROPOSAL)
    assert len(rows) == 1
    assert rows[0].title == "B"


def test_list_crs_newest_first(three_crs):
    rows = repo.list_crs(tenant_id="cinnox")
    # B was created after A → B should come first
    assert rows[0].title == "B"
    assert rows[1].title == "A"


def test_list_crs_respects_limit(three_crs):
    rows = repo.list_crs(tenant_id="cinnox", limit=1)
    assert len(rows) == 1
```

- [ ] **Step 2: Run to verify it fails**

```bash
uv run pytest tests/change_request/test_repository_list.py -v
```

Expected: `AttributeError: module ... has no attribute 'list_crs'`.

- [ ] **Step 3: Add `list_crs` to repository.py**

Append to `autoservice/change_request/repository.py`:

```python
def list_crs(
    *,
    tenant_id: Optional[str] = None,
    status: Optional[CRStatus] = None,
    source: Optional[CRSource] = None,
    limit: int = 100,
) -> list[CR]:
    """Newest-first list of CRs filtered by any combination of tenant/status/source.

    Filters compose as AND. Pass tenant_id=None to query across all tenants
    (master view).
    """
    where = []
    params: list = []
    if tenant_id is not None:
        where.append("tenant_id = ?")
        params.append(tenant_id)
    if status is not None:
        where.append("status = ?")
        params.append(status.value)
    if source is not None:
        where.append("source = ?")
        params.append(source.value)

    clause = (" WHERE " + " AND ".join(where)) if where else ""
    sql = (
        "SELECT id, tenant_id, source, actor, title, description, status, "
        "       sandbox_diff, parent_cr_id, target_release_ver, "
        "       rolled_back_to_ver, metadata_json, created_at, updated_at, "
        "       closed_at FROM change_requests"
        + clause
        + " ORDER BY created_at DESC, id DESC LIMIT ?"
    )
    params.append(limit)

    with closing(_connect()) as conn, conn:
        rows = conn.execute(sql, tuple(params)).fetchall()

    return [
        CR(
            id=r[0], tenant_id=r[1], source=CRSource(r[2]), actor=r[3],
            title=r[4], description=r[5], status=CRStatus(r[6]),
            sandbox_diff=r[7], parent_cr_id=r[8], target_release_ver=r[9],
            rolled_back_to_ver=r[10], metadata_json=r[11],
            created_at=r[12], updated_at=r[13], closed_at=r[14],
        )
        for r in rows
    ]
```

- [ ] **Step 4: Run to verify it passes**

```bash
uv run pytest tests/change_request/test_repository_list.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add autoservice/change_request/repository.py tests/change_request/test_repository_list.py
git commit -m "feat(change_request): repository — list_crs with tenant/status/source filters"
```

---

## Phase B — State machine + concurrency

### Task 5: State machine — `validate_transition` + custom exceptions

**Files:**
- Create: `autoservice/change_request/state_machine.py`
- Create: `tests/change_request/test_state_machine.py`

- [ ] **Step 1: Write failing transition tests**

Create `tests/change_request/test_state_machine.py`:

```python
"""State machine — every legal transition allowed, every illegal one raises."""
from __future__ import annotations

import pytest

from autoservice.change_request import state_machine as sm
from autoservice.change_request.models import CRStatus


LEGAL = [
    (CRStatus.DRAFT, CRStatus.READY_FOR_REVIEW),
    (CRStatus.DRAFT, CRStatus.ABANDONED),
    (CRStatus.READY_FOR_REVIEW, CRStatus.DRAFT),
    (CRStatus.READY_FOR_REVIEW, CRStatus.PUBLISHING),
    (CRStatus.READY_FOR_REVIEW, CRStatus.ABANDONED),
    (CRStatus.PUBLISHING, CRStatus.READY_FOR_REVIEW),   # gate failed
    (CRStatus.PUBLISHING, CRStatus.PUBLISHED),
    (CRStatus.PUBLISHING, CRStatus.ABANDONED),          # lock TTL elapsed
    (CRStatus.PUBLISHED, CRStatus.ROLLED_BACK),
]


@pytest.mark.parametrize("frm,to", LEGAL)
def test_legal_transitions(frm: CRStatus, to: CRStatus):
    sm.validate_transition(frm, to)        # no exception → pass


def test_illegal_draft_to_publishing_raises():
    with pytest.raises(sm.CRStateInvalid):
        sm.validate_transition(CRStatus.DRAFT, CRStatus.PUBLISHING)


def test_illegal_published_to_draft_raises():
    with pytest.raises(sm.CRStateInvalid):
        sm.validate_transition(CRStatus.PUBLISHED, CRStatus.DRAFT)


def test_terminal_to_anything_raises():
    for terminal in (CRStatus.ABANDONED, CRStatus.ROLLED_BACK):
        for to in CRStatus:
            if to is terminal:
                continue
            with pytest.raises(sm.CRStateInvalid):
                sm.validate_transition(terminal, to)


def test_cr_not_found_exception_exists():
    """Importable for use by API / repository callers."""
    assert issubclass(sm.CRNotFound, Exception)


def test_cr_tenant_mismatch_exception_exists():
    assert issubclass(sm.CRTenantMismatch, Exception)
```

- [ ] **Step 2: Run to verify it fails**

```bash
uv run pytest tests/change_request/test_state_machine.py -v
```

Expected: `ImportError: cannot import name 'state_machine'`.

- [ ] **Step 3: Write state_machine.py**

Create `autoservice/change_request/state_machine.py`:

```python
"""CR state machine — legal transitions + custom exceptions.

See docs/superpowers/specs/2026-05-11-admin-v2-design.md §2.2 for the
canonical transition matrix.
"""
from __future__ import annotations

from autoservice.change_request.models import CRStatus


# from -> set of legal next states
_TRANSITIONS: dict[CRStatus, set[CRStatus]] = {
    CRStatus.DRAFT: {
        CRStatus.READY_FOR_REVIEW,
        CRStatus.ABANDONED,
    },
    CRStatus.READY_FOR_REVIEW: {
        CRStatus.DRAFT,
        CRStatus.PUBLISHING,
        CRStatus.ABANDONED,
    },
    CRStatus.PUBLISHING: {
        CRStatus.READY_FOR_REVIEW,       # gate / snapshot failed
        CRStatus.PUBLISHED,
        CRStatus.ABANDONED,              # publish_lock TTL elapsed
    },
    CRStatus.PUBLISHED: {
        CRStatus.ROLLED_BACK,            # only set by rollback handler
    },
    CRStatus.ROLLED_BACK: set(),          # terminal
    CRStatus.ABANDONED: set(),            # terminal
}


class CRStateInvalid(Exception):
    """Raised when a status transition violates the state machine."""

    def __init__(self, from_status: CRStatus, to_status: CRStatus, *, cr_id: str | None = None):
        msg = f"Illegal CR transition {from_status.value!r} -> {to_status.value!r}"
        if cr_id:
            msg = f"{msg} (cr_id={cr_id})"
        super().__init__(msg)
        self.from_status = from_status
        self.to_status = to_status
        self.cr_id = cr_id


class CRNotFound(Exception):
    """Raised when load_cr / update_status is called with an unknown cr_id."""

    def __init__(self, cr_id: str):
        super().__init__(f"CR not found: {cr_id}")
        self.cr_id = cr_id


class CRTenantMismatch(Exception):
    """Raised when a CR is used against a tenant_id different from its own."""

    def __init__(self, cr_id: str, expected: str, actual: str):
        super().__init__(
            f"CR {cr_id} belongs to tenant {actual!r}, not {expected!r}"
        )
        self.cr_id = cr_id
        self.expected = expected
        self.actual = actual


def validate_transition(
    from_status: CRStatus,
    to_status: CRStatus,
    *,
    cr_id: str | None = None,
) -> None:
    """Raises CRStateInvalid if from_status -> to_status is not legal."""
    if to_status not in _TRANSITIONS.get(from_status, set()):
        raise CRStateInvalid(from_status, to_status, cr_id=cr_id)
```

Update `autoservice/change_request/__init__.py` to re-export:

```python
"""CR (Change Request) data layer.

See docs/superpowers/specs/2026-05-11-admin-v2-design.md §2.
"""
from autoservice.change_request import models, repository, schema, state_machine
from autoservice.change_request.models import CR, CRAudit, CRSource, CRStatus
from autoservice.change_request.state_machine import (
    CRNotFound,
    CRStateInvalid,
    CRTenantMismatch,
)

__all__ = [
    "CR", "CRAudit", "CRSource", "CRStatus",
    "CRNotFound", "CRStateInvalid", "CRTenantMismatch",
    "models", "repository", "schema", "state_machine",
]
```

- [ ] **Step 4: Run to verify it passes**

```bash
uv run pytest tests/change_request/test_state_machine.py -v
```

Expected: 14 passed (9 legal + 1 draft-illegal + 1 published-illegal + terminal × 10 illegal + 2 exception-existence ≈ 14, exact count from parametrize expansion).

- [ ] **Step 5: Commit**

```bash
git add autoservice/change_request/state_machine.py autoservice/change_request/__init__.py tests/change_request/test_state_machine.py
git commit -m "feat(change_request): state machine — validate_transition + custom exceptions"
```

---

### Task 6: Repository — `update_status` (uses state machine)

**Files:**
- Modify: `autoservice/change_request/repository.py` (append update_status)
- Modify: `tests/change_request/test_repository_crud.py` (append update_status tests)

- [ ] **Step 1: Append failing tests to test_repository_crud.py**

```python
# Append to tests/change_request/test_repository_crud.py

from autoservice.change_request import state_machine as sm


def test_update_status_legal_transition(isolated_audit_db: Path):
    cr_id = repo.create_cr(
        tenant_id="cinnox", source=CRSource.MANUAL,
        actor="a@x.com", title="t",
    )
    repo.update_status(
        cr_id, new_status=CRStatus.READY_FOR_REVIEW, actor="a@x.com"
    )
    assert repo.load_cr(cr_id).status is CRStatus.READY_FOR_REVIEW


def test_update_status_writes_audit_row(isolated_audit_db: Path):
    cr_id = repo.create_cr(
        tenant_id="cinnox", source=CRSource.MANUAL,
        actor="a@x.com", title="t",
    )
    repo.update_status(
        cr_id, new_status=CRStatus.READY_FOR_REVIEW, actor="a@x.com"
    )
    audits = repo.list_audit(cr_id)
    assert len(audits) == 2          # created + reviewed
    assert audits[1].action == "status_changed"


def test_update_status_illegal_raises(isolated_audit_db: Path):
    cr_id = repo.create_cr(
        tenant_id="cinnox", source=CRSource.MANUAL,
        actor="a@x.com", title="t",
    )
    with pytest.raises(sm.CRStateInvalid):
        repo.update_status(
            cr_id, new_status=CRStatus.PUBLISHING, actor="a@x.com"
        )


def test_update_status_to_terminal_sets_closed_at(isolated_audit_db: Path):
    cr_id = repo.create_cr(
        tenant_id="cinnox", source=CRSource.MANUAL,
        actor="a@x.com", title="t",
    )
    repo.update_status(cr_id, new_status=CRStatus.ABANDONED, actor="a@x.com")
    cr = repo.load_cr(cr_id)
    assert cr.status is CRStatus.ABANDONED
    assert cr.closed_at is not None


def test_update_status_on_unknown_raises_cr_not_found(isolated_audit_db: Path):
    with pytest.raises(sm.CRNotFound):
        repo.update_status(
            "cr_does_not_exist", new_status=CRStatus.ABANDONED, actor="x"
        )
```

- [ ] **Step 2: Run to verify it fails**

```bash
uv run pytest tests/change_request/test_repository_crud.py -v
```

Expected: 5 new tests fail with `AttributeError: ... no attribute 'update_status'`.

- [ ] **Step 3: Append `update_status` + `append_audit` to repository.py**

Append to `autoservice/change_request/repository.py`:

```python
from autoservice.change_request import state_machine as _sm


def append_audit(
    cr_id: str,
    *,
    actor: str,
    action: str,
    payload: Optional[dict] = None,
) -> None:
    """Free-standing audit row writer (used by API / wrappers that don't
    transition status but still want an audit entry)."""
    payload_json = json.dumps(payload) if payload else None
    with closing(_connect()) as conn, conn:
        conn.execute(
            "INSERT INTO cr_audit (cr_id, ts, actor, action, payload) "
            "VALUES (?, ?, ?, ?, ?)",
            (cr_id, _now_iso(), actor, action, payload_json),
        )


def update_status(
    cr_id: str,
    *,
    new_status: CRStatus,
    actor: str,
    extra_audit_payload: Optional[dict] = None,
) -> None:
    """Validate the transition against the state machine and apply it.

    Raises CRNotFound / CRStateInvalid as appropriate.
    """
    cr = load_cr(cr_id)
    if cr is None:
        raise _sm.CRNotFound(cr_id)

    _sm.validate_transition(cr.status, new_status, cr_id=cr_id)

    now = _now_iso()
    closed_at = now if new_status in _TERMINAL_STATUSES else None

    audit_payload: dict = {
        "from": cr.status.value,
        "to": new_status.value,
    }
    if extra_audit_payload:
        audit_payload.update(extra_audit_payload)

    with closing(_connect()) as conn, conn:
        if closed_at is not None:
            conn.execute(
                "UPDATE change_requests "
                "SET status=?, updated_at=?, closed_at=COALESCE(closed_at, ?) "
                "WHERE id=?",
                (new_status.value, now, closed_at, cr_id),
            )
        else:
            conn.execute(
                "UPDATE change_requests SET status=?, updated_at=? WHERE id=?",
                (new_status.value, now, cr_id),
            )
        conn.execute(
            "INSERT INTO cr_audit (cr_id, ts, actor, action, payload) "
            "VALUES (?, ?, ?, 'status_changed', ?)",
            (cr_id, now, actor, json.dumps(audit_payload)),
        )
```

- [ ] **Step 4: Run to verify it passes**

```bash
uv run pytest tests/change_request/test_repository_crud.py -v
```

Expected: 9 passed (4 original + 5 new).

- [ ] **Step 5: Commit**

```bash
git add autoservice/change_request/repository.py tests/change_request/test_repository_crud.py
git commit -m "feat(change_request): repository — update_status + append_audit"
```

---

### Task 7: Partial unique index — enforce one active CR per tenant

**Files:**
- Modify: `autoservice/change_request/schema.py` (add partial unique index)
- Modify: `autoservice/change_request/repository.py` (catch IntegrityError → CRConflict)
- Modify: `autoservice/change_request/state_machine.py` (add CRConflict)
- Create: `tests/change_request/test_active_cr_unique.py`

- [ ] **Step 1: Write failing partial-index test**

Create `tests/change_request/test_active_cr_unique.py`:

```python
"""uq_active_cr_per_tenant — only one non-terminal CR per tenant."""
from __future__ import annotations

from pathlib import Path

import pytest

from autoservice.change_request import repository as repo
from autoservice.change_request import state_machine as sm
from autoservice.change_request.models import CRSource, CRStatus


def test_first_active_cr_succeeds(isolated_audit_db: Path):
    cr_id = repo.create_cr(
        tenant_id="cinnox", source=CRSource.MANUAL,
        actor="a@x.com", title="A",
    )
    assert cr_id.startswith("cr_")


def test_second_active_cr_same_tenant_raises_cr_conflict(isolated_audit_db: Path):
    repo.create_cr(
        tenant_id="cinnox", source=CRSource.MANUAL,
        actor="a@x.com", title="A",
    )
    with pytest.raises(sm.CRConflict):
        repo.create_cr(
            tenant_id="cinnox", source=CRSource.MANUAL,
            actor="b@x.com", title="B",
        )


def test_active_cr_in_different_tenant_ok(isolated_audit_db: Path):
    repo.create_cr(
        tenant_id="cinnox", source=CRSource.MANUAL,
        actor="a@x.com", title="A",
    )
    cr_id_b = repo.create_cr(
        tenant_id="acme", source=CRSource.MANUAL,
        actor="b@x.com", title="B",
    )
    assert cr_id_b.startswith("cr_")


def test_new_cr_after_abandon_ok(isolated_audit_db: Path):
    cr1 = repo.create_cr(
        tenant_id="cinnox", source=CRSource.MANUAL,
        actor="a@x.com", title="A",
    )
    repo.update_status(cr1, new_status=CRStatus.ABANDONED, actor="a@x.com")
    cr2 = repo.create_cr(
        tenant_id="cinnox", source=CRSource.MANUAL,
        actor="a@x.com", title="B",
    )
    assert cr2 != cr1


def test_terminal_cr_creation_bypasses_partial_index(isolated_audit_db: Path):
    """source='legacy_publish' / 'rollback' / 'migration' all create rows
    that start in published — they should never trip the index even if
    an unrelated draft CR exists for the same tenant."""
    repo.create_cr(
        tenant_id="cinnox", source=CRSource.MANUAL,
        actor="a@x.com", title="draft A",
    )
    cr_legacy = repo.create_cr(
        tenant_id="cinnox", source=CRSource.LEGACY_PUBLISH,
        actor="legacy-apply-wrapper", title="V1 publish",
        initial_status=CRStatus.PUBLISHED,
    )
    assert cr_legacy.startswith("cr_")
```

- [ ] **Step 2: Run to verify it fails**

```bash
uv run pytest tests/change_request/test_active_cr_unique.py -v
```

Expected: `test_second_active_cr_same_tenant_raises_cr_conflict` succeeds at insert (no constraint yet) and instead loads two rows. Test fails because no exception was raised.

- [ ] **Step 3: Add partial unique index to schema**

Modify `autoservice/change_request/schema.py` — append to the SCHEMA_SQL string:

```python
SCHEMA_SQL = """
... (existing tables and indexes unchanged) ...

-- Active-CR-per-tenant guard. SQLite ≥3.8 supports partial indexes.
-- Active = draft | ready_for_review | publishing. The 3 terminal statuses
-- (published, rolled_back, abandoned) are not constrained.
CREATE UNIQUE INDEX IF NOT EXISTS uq_active_cr_per_tenant
    ON change_requests(tenant_id)
    WHERE status IN ('draft', 'ready_for_review', 'publishing');
"""
```

- [ ] **Step 4: Add `CRConflict` exception**

Append to `autoservice/change_request/state_machine.py`:

```python
class CRConflict(Exception):
    """Raised when an attempt to create / activate a CR violates the
    active-CR-per-tenant constraint."""

    def __init__(self, tenant_id: str, existing_cr_id: str | None = None):
        if existing_cr_id:
            msg = (
                f"Tenant {tenant_id!r} already has an active CR "
                f"({existing_cr_id}); abandon or publish it first"
            )
        else:
            msg = f"Tenant {tenant_id!r} already has an active CR"
        super().__init__(msg)
        self.tenant_id = tenant_id
        self.existing_cr_id = existing_cr_id
```

And re-export it in `autoservice/change_request/__init__.py`:

```python
from autoservice.change_request.state_machine import (
    CRConflict,           # ← add
    CRNotFound,
    CRStateInvalid,
    CRTenantMismatch,
)

__all__ = [
    "CR", "CRAudit", "CRSource", "CRStatus",
    "CRConflict",          # ← add
    "CRNotFound", "CRStateInvalid", "CRTenantMismatch",
    "models", "repository", "schema", "state_machine",
]
```

- [ ] **Step 5: Catch IntegrityError in `create_cr`**

Modify `autoservice/change_request/repository.py::create_cr` — wrap the INSERT block:

```python
def create_cr(
    *,
    tenant_id: str,
    source: CRSource,
    actor: str,
    title: str,
    description: Optional[str] = None,
    initial_status: CRStatus = CRStatus.DRAFT,
    parent_cr_id: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> str:
    cr_id = generate_cr_id()
    now = _now_iso()
    closed_at = now if initial_status in _TERMINAL_STATUSES else None
    metadata_json = json.dumps(metadata) if metadata else None

    try:
        with closing(_connect()) as conn, conn:
            conn.execute(
                "INSERT INTO change_requests "
                "(id, tenant_id, source, actor, title, description, status, "
                " parent_cr_id, metadata_json, created_at, updated_at, closed_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    cr_id, tenant_id, source.value, actor, title, description,
                    initial_status.value, parent_cr_id, metadata_json,
                    now, now, closed_at,
                ),
            )
            conn.execute(
                "INSERT INTO cr_audit (cr_id, ts, actor, action, payload) "
                "VALUES (?, ?, ?, 'created', ?)",
                (cr_id, now, actor,
                 json.dumps({"source": source.value, "title": title})),
            )
    except sqlite3.IntegrityError as exc:
        # Only the partial unique index can trigger this on create_cr.
        if "uq_active_cr_per_tenant" in str(exc):
            existing = _find_active_cr_id(tenant_id)
            raise _sm.CRConflict(tenant_id, existing) from exc
        raise

    return cr_id


def _find_active_cr_id(tenant_id: str) -> Optional[str]:
    """Look up the existing active CR id for error reporting."""
    with closing(_connect()) as conn, conn:
        row = conn.execute(
            "SELECT id FROM change_requests "
            "WHERE tenant_id=? "
            "  AND status IN ('draft','ready_for_review','publishing') "
            "LIMIT 1",
            (tenant_id,),
        ).fetchone()
    return row[0] if row else None
```

- [ ] **Step 6: Run to verify it passes**

```bash
uv run pytest tests/change_request/test_active_cr_unique.py -v
```

Expected: 5 passed.

- [ ] **Step 7: Run the full change_request suite to confirm no regression**

```bash
uv run pytest tests/change_request/ -v
```

Expected: all tests pass.

- [ ] **Step 8: Commit**

```bash
git add autoservice/change_request/schema.py autoservice/change_request/state_machine.py autoservice/change_request/__init__.py autoservice/change_request/repository.py tests/change_request/test_active_cr_unique.py
git commit -m "feat(change_request): partial unique index enforces one active CR per tenant"
```

---

## Phase C — HTTP API for CR

### Task 8: `/api/crs` core endpoints — POST / GET / list / PATCH / DELETE

**Files:**
- Create: `autoservice/change_request/api_routes.py`
- Modify: `autoservice/api_routes.py` (mount cr_router)
- Create: `tests/change_request/test_api_routes.py`

- [ ] **Step 1: Read the existing auth pattern**

Read `autoservice/api_routes.py` lines around 1331 to see how `_MASTER_AUTH_DEP` is wired. Also read `autoservice/auth.py` around line 473 for the `require_tenant_access_for` helper. The pattern we'll follow:

```python
from autoservice.api_routes import _MASTER_AUTH_DEP   # already exported
```

If `_MASTER_AUTH_DEP` is module-private and not exported, use the underlying `Depends(auth.require_tenant_access_for("_master"))` directly. Do **not** invent a new auth mechanism — reuse what exists.

- [ ] **Step 2: Write failing API tests**

Create `tests/change_request/test_api_routes.py`:

```python
"""HTTP surface for /api/crs/*.

Uses the existing FastAPI app from autoservice.web_gateway with the
admin auth bypass for tests (AUTH_DEV_MODE=1 + ADMIN_DEV_USER=...).
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from autoservice.change_request.models import CRSource, CRStatus


@pytest.fixture
def app_client(isolated_audit_db: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("AUTH_DEV_MODE", "1")
    # Import the app AFTER env vars are set so module-level config picks them up.
    from autoservice.web_gateway import create_app
    app = create_app()
    client = TestClient(app)
    # Log in via dev-mode endpoint (returns admin session cookie)
    r = client.post("/api/auth/dev-login")
    assert r.status_code == 200, r.text
    return client


def test_post_crs_creates_draft_cr(app_client: TestClient):
    r = app_client.post(
        "/api/crs",
        json={
            "tenant_id": "cinnox",
            "source": "manual",
            "title": "Bump customer soul",
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["id"].startswith("cr_")
    assert body["status"] == "draft"


def test_get_crs_filters_by_tenant(app_client: TestClient):
    app_client.post(
        "/api/crs",
        json={"tenant_id": "cinnox", "source": "manual", "title": "A"},
    )
    app_client.post(
        "/api/crs",
        json={"tenant_id": "acme", "source": "manual", "title": "B"},
    )
    r = app_client.get("/api/crs?tenant_id=cinnox")
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["tenant_id"] == "cinnox"


def test_get_cr_by_id(app_client: TestClient):
    r1 = app_client.post(
        "/api/crs",
        json={"tenant_id": "cinnox", "source": "manual", "title": "A"},
    )
    cr_id = r1.json()["id"]
    r2 = app_client.get(f"/api/crs/{cr_id}")
    assert r2.status_code == 200
    assert r2.json()["id"] == cr_id


def test_get_cr_404(app_client: TestClient):
    r = app_client.get("/api/crs/cr_unknown")
    assert r.status_code == 404


def test_patch_status_legal_transition(app_client: TestClient):
    r1 = app_client.post(
        "/api/crs",
        json={"tenant_id": "cinnox", "source": "manual", "title": "A"},
    )
    cr_id = r1.json()["id"]
    r2 = app_client.patch(
        f"/api/crs/{cr_id}/status",
        json={"status": "ready_for_review"},
    )
    assert r2.status_code == 200, r2.text
    assert r2.json()["status"] == "ready_for_review"


def test_patch_status_illegal_transition_409(app_client: TestClient):
    r1 = app_client.post(
        "/api/crs",
        json={"tenant_id": "cinnox", "source": "manual", "title": "A"},
    )
    cr_id = r1.json()["id"]
    r2 = app_client.patch(
        f"/api/crs/{cr_id}/status",
        json={"status": "publishing"},     # skip ready_for_review
    )
    assert r2.status_code == 409
    assert "illegal" in r2.text.lower()


def test_delete_cr_marks_abandoned(app_client: TestClient):
    r1 = app_client.post(
        "/api/crs",
        json={"tenant_id": "cinnox", "source": "manual", "title": "A"},
    )
    cr_id = r1.json()["id"]
    r2 = app_client.delete(f"/api/crs/{cr_id}")
    assert r2.status_code == 200
    r3 = app_client.get(f"/api/crs/{cr_id}")
    assert r3.json()["status"] == "abandoned"


def test_second_active_cr_409(app_client: TestClient):
    app_client.post(
        "/api/crs",
        json={"tenant_id": "cinnox", "source": "manual", "title": "A"},
    )
    r = app_client.post(
        "/api/crs",
        json={"tenant_id": "cinnox", "source": "manual", "title": "B"},
    )
    assert r.status_code == 409


def test_post_crs_rejects_disallowed_source_via_api(app_client: TestClient):
    """API never lets a caller specify legacy_publish / rollback / migration —
    those are internal-only sources."""
    r = app_client.post(
        "/api/crs",
        json={"tenant_id": "cinnox", "source": "legacy_publish", "title": "A"},
    )
    assert r.status_code == 400
```

- [ ] **Step 3: Run to verify it fails**

```bash
uv run pytest tests/change_request/test_api_routes.py -v
```

Expected: 404 on `/api/crs` POST (router not mounted yet).

- [ ] **Step 4: Write the API routes module**

Create `autoservice/change_request/api_routes.py`:

```python
"""HTTP surface for /api/crs/*.

Auth: master tier only (admin). Per-tenant operators do not interact with
CRs in P1; that comes in §7 admin V2 UI Phase 2.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from autoservice import auth as _auth
from autoservice.change_request import repository as repo
from autoservice.change_request import state_machine as sm
from autoservice.change_request.models import CR, CRSource, CRStatus


cr_router = APIRouter()


_USER_FACING_SOURCES = {CRSource.MANUAL, CRSource.DOCS_REGEN}
# dream_proposal / master_dream / legacy_publish / rollback / migration are
# all created by internal machinery, never by direct API calls.


def _serialize(cr: CR) -> dict:
    d = asdict(cr)
    d["source"] = cr.source.value
    d["status"] = cr.status.value
    return d


def _actor_from_auth(auth_ctx: dict) -> str:
    return (auth_ctx.get("email") if isinstance(auth_ctx, dict) else None) or "unknown"


@cr_router.post("/crs", status_code=201)
async def post_cr(
    body: dict = Body(...),
    auth_ctx: dict = Depends(_auth.require_tenant_access_for("_master")),
):
    tenant_id = body.get("tenant_id")
    source_raw = body.get("source")
    title = body.get("title")
    if not tenant_id or not source_raw or not title:
        raise HTTPException(400, "tenant_id, source, title required")
    try:
        source = CRSource(source_raw)
    except ValueError:
        raise HTTPException(400, f"unknown source {source_raw!r}")
    if source not in _USER_FACING_SOURCES:
        raise HTTPException(
            400,
            f"source {source.value!r} is internal-only; cannot be set via API",
        )

    actor = _actor_from_auth(auth_ctx)
    try:
        cr_id = repo.create_cr(
            tenant_id=tenant_id,
            source=source,
            actor=actor,
            title=title,
            description=body.get("description"),
        )
    except sm.CRConflict as exc:
        raise HTTPException(
            409,
            f"Active CR already exists for tenant {tenant_id}: {exc.existing_cr_id}",
        )
    return _serialize(repo.load_cr(cr_id))


@cr_router.get("/crs")
async def get_crs(
    tenant_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    auth_ctx: dict = Depends(_auth.require_tenant_access_for("_master")),
):
    status_filter = CRStatus(status) if status else None
    source_filter = CRSource(source) if source else None
    items = repo.list_crs(
        tenant_id=tenant_id,
        status=status_filter,
        source=source_filter,
        limit=limit,
    )
    return {"items": [_serialize(c) for c in items], "total": len(items)}


@cr_router.get("/crs/{cr_id}")
async def get_cr(
    cr_id: str,
    auth_ctx: dict = Depends(_auth.require_tenant_access_for("_master")),
):
    cr = repo.load_cr(cr_id)
    if cr is None:
        raise HTTPException(404, f"CR {cr_id} not found")
    return _serialize(cr)


@cr_router.patch("/crs/{cr_id}/status")
async def patch_cr_status(
    cr_id: str,
    body: dict = Body(...),
    auth_ctx: dict = Depends(_auth.require_tenant_access_for("_master")),
):
    status_raw = body.get("status")
    if not status_raw:
        raise HTTPException(400, "status required")
    try:
        new_status = CRStatus(status_raw)
    except ValueError:
        raise HTTPException(400, f"unknown status {status_raw!r}")

    actor = _actor_from_auth(auth_ctx)
    try:
        repo.update_status(cr_id, new_status=new_status, actor=actor)
    except sm.CRNotFound:
        raise HTTPException(404, f"CR {cr_id} not found")
    except sm.CRStateInvalid as exc:
        raise HTTPException(409, str(exc))
    return _serialize(repo.load_cr(cr_id))


@cr_router.delete("/crs/{cr_id}")
async def delete_cr(
    cr_id: str,
    auth_ctx: dict = Depends(_auth.require_tenant_access_for("_master")),
):
    """Soft delete = transition to abandoned."""
    actor = _actor_from_auth(auth_ctx)
    try:
        repo.update_status(cr_id, new_status=CRStatus.ABANDONED, actor=actor)
    except sm.CRNotFound:
        raise HTTPException(404, f"CR {cr_id} not found")
    except sm.CRStateInvalid as exc:
        raise HTTPException(409, str(exc))
    return _serialize(repo.load_cr(cr_id))
```

- [ ] **Step 5: Mount `cr_router` in the main api_router**

Modify `autoservice/api_routes.py` — find the section near the bottom that does `api_router.include_router(_operator_router)` and add **before** it:

```python
from autoservice.change_request.api_routes import cr_router as _cr_router  # noqa: E402

api_router.include_router(_cr_router)
```

- [ ] **Step 6: Run to verify it passes**

```bash
uv run pytest tests/change_request/test_api_routes.py -v
```

Expected: 9 passed.

- [ ] **Step 7: Run the full change_request suite for regression**

```bash
uv run pytest tests/change_request/ -v
```

Expected: all tests in Phase A-C pass.

- [ ] **Step 8: Commit**

```bash
git add autoservice/change_request/api_routes.py autoservice/api_routes.py tests/change_request/test_api_routes.py
git commit -m "feat(change_request): /api/crs HTTP surface (POST/GET/PATCH/DELETE)"
```

---

## Phase D — Integration with existing publish/rollback

### Task 9: Manifest extension — `cr_id` / `cr_source` / `cr_actor` fields

**Files:**
- Modify: `autoservice/release_snapshot.py`
- Create: `tests/release_snapshot/__init__.py` (empty)
- Create: `tests/release_snapshot/test_manifest_cr_fields.py`

- [ ] **Step 1: Read existing build_release_snapshot signature**

Read `autoservice/release_snapshot.py` end-to-end. Note the existing signature of `build_release_snapshot` and the current manifest schema. You need to add 3 optional kwargs without breaking existing callers.

- [ ] **Step 2: Write the failing manifest test**

Create `tests/release_snapshot/test_manifest_cr_fields.py`:

```python
"""manifest.yaml carries cr_id / cr_source / cr_actor when supplied."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from autoservice import release_snapshot


@pytest.fixture
def fake_sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a minimal sandbox/cinnox/ structure that build_release_snapshot
    can copy from."""
    monkeypatch.setenv("AUTOSERVICE_SANDBOX_DIR", str(tmp_path / "sandbox"))
    monkeypatch.setenv("AUTOSERVICE_RELEASES_DIR", str(tmp_path / "released"))
    sandbox = tmp_path / "sandbox" / "cinnox"
    (sandbox / "souls").mkdir(parents=True)
    (sandbox / "souls" / "customer_soul.md").write_text("# customer soul\n")
    (sandbox / "config.json").write_text('{"tenant_id": "cinnox"}\n')
    return sandbox


def test_manifest_includes_cr_fields(fake_sandbox: Path, tmp_path: Path):
    out = release_snapshot.build_release_snapshot(
        tenant_id="cinnox",
        version="v1",
        framework_ver="abcdef0",
        gate_results={"passed": True},
        cr_id="cr_abc123def456",
        cr_source="manual",
        cr_actor="admin@h2os.cloud",
    )
    manifest = yaml.safe_load((out / "manifest.yaml").read_text())
    assert manifest["cr_id"] == "cr_abc123def456"
    assert manifest["cr_source"] == "manual"
    assert manifest["cr_actor"] == "admin@h2os.cloud"


def test_manifest_omits_cr_fields_when_not_supplied(fake_sandbox: Path, tmp_path: Path):
    """Backward compatibility: legacy callers that don't pass cr_id still work."""
    out = release_snapshot.build_release_snapshot(
        tenant_id="cinnox",
        version="v1",
        framework_ver="abcdef0",
        gate_results={"passed": True},
    )
    manifest = yaml.safe_load((out / "manifest.yaml").read_text())
    # cr_id absence is acceptable; existing fields must still be present
    assert manifest["version"] == "v1"
    assert manifest["framework_ver"] == "abcdef0"
    assert manifest.get("cr_id") is None       # absent or None
```

- [ ] **Step 3: Run to verify it fails**

```bash
uv run pytest tests/release_snapshot/test_manifest_cr_fields.py -v
```

Expected: `TypeError: build_release_snapshot() got an unexpected keyword argument 'cr_id'`.

- [ ] **Step 4: Add `cr_id` / `cr_source` / `cr_actor` to `build_release_snapshot`**

Modify `autoservice/release_snapshot.py`:

```python
# In the function signature
def build_release_snapshot(
    *,
    tenant_id: str,
    version: str,
    framework_ver: str,
    gate_results: dict,
    cr_id: str | None = None,
    cr_source: str | None = None,
    cr_actor: str | None = None,
) -> Path:
    """... existing docstring ...

    The optional cr_id / cr_source / cr_actor fields land in manifest.yaml
    when supplied; legacy callers leave them None for backward compatibility.
    """
    # ... existing copy + VACUUM INTO logic unchanged ...

    # When constructing the manifest dict:
    manifest = {
        "version": version,
        "framework_ver": framework_ver,
        "published_at": _now_iso(),
        "gate_results": gate_results,
        "sha256_per_file": ...,        # existing
    }
    if cr_id is not None:
        manifest["cr_id"] = cr_id
    if cr_source is not None:
        manifest["cr_source"] = cr_source
    if cr_actor is not None:
        manifest["cr_actor"] = cr_actor

    (out_dir / "manifest.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False))
    # ... rest unchanged ...
```

Read the existing function and apply the changes minimally — do **not** rewrite the file. The exact placement of the 3 new kwargs and the 3 manifest field assignments depend on the current code layout.

- [ ] **Step 5: Run to verify it passes**

```bash
uv run pytest tests/release_snapshot/test_manifest_cr_fields.py -v
```

Expected: 2 passed.

- [ ] **Step 6: Run the existing e2e to confirm no regression**

```bash
uv run pytest tests/ -k "publish_v1_v2_rollback" -v
```

Expected: pre-existing e2e test still passes (legacy caller path is unchanged).

- [ ] **Step 7: Commit**

```bash
git add autoservice/release_snapshot.py tests/release_snapshot/__init__.py tests/release_snapshot/test_manifest_cr_fields.py
git commit -m "feat(release_snapshot): optional cr_id/cr_source/cr_actor in manifest.yaml"
```

---

### Task 10: Publish endpoint — `cr_id` required + state transitions

**Files:**
- Modify: `autoservice/api_routes.py` (publish_tenant handler)
- Create: `tests/api_routes/test_publish_with_cr.py`

- [ ] **Step 1: Write failing publish-with-cr tests**

Create `tests/api_routes/test_publish_with_cr.py`:

```python
"""POST /api/tenants/:tid/publish requires cr_id; transitions CR through
ready_for_review -> publishing -> published; manifest carries cr_id."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from autoservice.change_request import repository as repo
from autoservice.change_request.models import CRSource, CRStatus


@pytest.fixture
def app_client(isolated_audit_db: Path, tmp_path: Path,
               monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("AUTH_DEV_MODE", "1")
    monkeypatch.setenv("AUTOSERVICE_SANDBOX_DIR", str(tmp_path / "sandbox"))
    monkeypatch.setenv("AUTOSERVICE_RELEASES_DIR", str(tmp_path / "released"))
    monkeypatch.setenv("AUTOSERVICE_CURRENT_DIR", str(tmp_path / "current"))
    # Minimal sandbox so publish_gate's KB / souls checks pass — use the
    # same scaffold as the existing publish e2e fixture (see
    # tests/conftest.py for any reusable helper, otherwise inline it here).
    sandbox = tmp_path / "sandbox" / "cinnox"
    (sandbox / "souls").mkdir(parents=True)
    for role in ("customer", "translate", "lead", "triage"):
        (sandbox / "souls" / f"{role}_soul.md").write_text(f"# {role}\n")
    (sandbox / "kb").mkdir()
    (sandbox / "config.json").write_text('{"tenant_id":"cinnox"}\n')
    # If the existing publish_gate stub requires more (rehearsal etc),
    # copy the pre-existing e2e test's setup.

    from autoservice.web_gateway import create_app
    app = create_app()
    client = TestClient(app)
    r = client.post("/api/auth/dev-login")
    assert r.status_code == 200
    return client


def test_publish_without_cr_id_returns_400(app_client: TestClient):
    r = app_client.post("/api/tenants/cinnox/publish", json={})
    assert r.status_code == 400
    assert "cr_id" in r.text.lower()


def test_publish_with_unknown_cr_id_returns_404(app_client: TestClient):
    r = app_client.post(
        "/api/tenants/cinnox/publish",
        json={"cr_id": "cr_unknown"},
    )
    assert r.status_code == 404


def test_publish_with_wrong_tenant_cr_returns_409(app_client: TestClient):
    # Make a CR for cinnox
    r1 = app_client.post(
        "/api/crs",
        json={"tenant_id": "cinnox", "source": "manual", "title": "A"},
    )
    cr_id = r1.json()["id"]
    # Try to publish it under a different tenant
    r2 = app_client.post(
        "/api/tenants/acme/publish",
        json={"cr_id": cr_id},
    )
    assert r2.status_code == 409


def test_publish_with_draft_cr_returns_409(app_client: TestClient):
    r1 = app_client.post(
        "/api/crs",
        json={"tenant_id": "cinnox", "source": "manual", "title": "A"},
    )
    cr_id = r1.json()["id"]
    # Still in draft — must be ready_for_review first
    r2 = app_client.post(
        "/api/tenants/cinnox/publish",
        json={"cr_id": cr_id},
    )
    assert r2.status_code == 409


def test_publish_happy_path_transitions_cr_to_published(app_client: TestClient):
    r1 = app_client.post(
        "/api/crs",
        json={"tenant_id": "cinnox", "source": "manual", "title": "A"},
    )
    cr_id = r1.json()["id"]
    app_client.patch(
        f"/api/crs/{cr_id}/status",
        json={"status": "ready_for_review"},
    )
    r2 = app_client.post(
        "/api/tenants/cinnox/publish",
        json={"cr_id": cr_id},
    )
    assert r2.status_code == 200, r2.text
    body = r2.json()
    assert body["version"] == "v1"
    cr = repo.load_cr(cr_id)
    assert cr.status is CRStatus.PUBLISHED
    assert cr.target_release_ver == "v1"


def test_publish_happy_path_manifest_carries_cr_metadata(
    app_client: TestClient, tmp_path: Path,
):
    r1 = app_client.post(
        "/api/crs",
        json={"tenant_id": "cinnox", "source": "manual", "title": "A"},
    )
    cr_id = r1.json()["id"]
    app_client.patch(
        f"/api/crs/{cr_id}/status", json={"status": "ready_for_review"},
    )
    app_client.post(
        "/api/tenants/cinnox/publish",
        json={"cr_id": cr_id},
    )
    manifest_path = tmp_path / "released" / "cinnox" / "v1" / "manifest.yaml"
    manifest = yaml.safe_load(manifest_path.read_text())
    assert manifest["cr_id"] == cr_id
    assert manifest["cr_source"] == "manual"
    # cr_actor is the dev-login user; check it's present rather than its exact value
    assert manifest.get("cr_actor")
```

- [ ] **Step 2: Run to verify it fails**

```bash
uv run pytest tests/api_routes/test_publish_with_cr.py -v
```

Expected: most tests 200/422 instead of expected 400/404/409 — current publish handler ignores cr_id.

- [ ] **Step 3: Modify `publish_tenant` handler in api_routes.py**

Find the existing `publish_tenant` function in `autoservice/api_routes.py` (around line 2714). Modify it as follows:

```python
@api_router.post("/tenants/{tenant_id}/publish")
async def publish_tenant(
    tenant_id: str,
    request: Request,
    auth_ctx: dict = Depends(_MASTER_AUTH_DEP),
):
    actor = (auth_ctx.get("email") if isinstance(auth_ctx, dict) else None) or "unknown"

    body = await request.json()
    cr_id = body.get("cr_id")
    if not cr_id:
        raise HTTPException(400, "cr_id is required (V2 publish path)")

    # === CR validation BEFORE gate ===
    from autoservice.change_request import repository as _cr_repo
    from autoservice.change_request import state_machine as _cr_sm
    from autoservice.change_request.models import CRStatus

    cr = _cr_repo.load_cr(cr_id)
    if cr is None:
        raise HTTPException(404, f"CR {cr_id} not found")
    if cr.tenant_id != tenant_id:
        raise HTTPException(
            409,
            f"CR {cr_id} belongs to tenant {cr.tenant_id!r}, not {tenant_id!r}",
        )
    if cr.status not in (CRStatus.READY_FOR_REVIEW, CRStatus.PUBLISHING):
        raise HTTPException(
            409,
            f"CR {cr_id} status is {cr.status.value!r}; "
            "must be ready_for_review to publish",
        )

    # === 1. publish gate ===
    gate = _publish_legacy.check_publish_gate(tenant_id)
    if not gate.passed:
        # CR stays in ready_for_review for retry
        raise HTTPException(status_code=422, detail=gate.to_record())

    # === 2. transition CR -> publishing ===
    _cr_repo.update_status(cr_id, new_status=CRStatus.PUBLISHING, actor=actor)

    # === 3. publish lock ===
    token = _publish_lock.acquire(tenant_id, actor=actor)
    if token is None:
        holder = _publish_lock.get_holder(tenant_id)
        holder_actor = holder["actor"] if holder else "unknown"
        # roll CR back to ready_for_review
        _cr_repo.update_status(
            cr_id, new_status=CRStatus.READY_FOR_REVIEW, actor="system",
            extra_audit_payload={"reason": "publish_lock_held", "by": holder_actor},
        )
        raise HTTPException(
            status_code=409,
            detail=f"publish in progress (held by {holder_actor})",
        )

    try:
        # === 4. compute next version + build snapshot ===
        version = _next_version(tenant_id)
        out = _release_snapshot.build_release_snapshot(
            tenant_id=tenant_id,
            version=version,
            framework_ver=_git_rev(),
            gate_results=gate.to_record(),
            cr_id=cr_id,
            cr_source=cr.source.value,
            cr_actor=actor,
        )

        # === 5. flip pointer atomically ===
        _tenant_pointer.flip_pointer(tenant_id, version, actor=actor)

        # === 6. notify runtime ===
        await _notify_runtime_after_pointer_flip(tenant_id)

        # === 7. CR -> published + write target_release_ver ===
        _cr_repo.update_status(
            cr_id, new_status=CRStatus.PUBLISHED, actor=actor,
            extra_audit_payload={"version": version},
        )
        _cr_repo.set_target_release_ver(cr_id, version)

        return {
            "tenant_id": tenant_id,
            "version": version,
            "cr_id": cr_id,
            "snapshot_path": str(out),
            "actor": actor,
        }
    except Exception:
        # Roll CR back to ready_for_review so the admin can retry
        try:
            _cr_repo.update_status(
                cr_id, new_status=CRStatus.READY_FOR_REVIEW, actor="system",
                extra_audit_payload={"reason": "publish_failure"},
            )
        except Exception:
            pass
        raise
    finally:
        _publish_lock.release(tenant_id, token)
```

- [ ] **Step 4: Add `set_target_release_ver` to repository.py**

Append to `autoservice/change_request/repository.py`:

```python
def set_target_release_ver(cr_id: str, version: str) -> None:
    """Stamp the published release version on a CR — called immediately
    after a successful pointer flip."""
    with closing(_connect()) as conn, conn:
        conn.execute(
            "UPDATE change_requests SET target_release_ver=?, updated_at=? "
            "WHERE id=?",
            (version, _now_iso(), cr_id),
        )
```

- [ ] **Step 5: Run to verify it passes**

```bash
uv run pytest tests/api_routes/test_publish_with_cr.py -v
```

Expected: 6 passed.

- [ ] **Step 6: Run the pre-existing publish e2e to confirm regression**

```bash
uv run pytest tests/ -k "publish_v1_v2_rollback" -v
```

Expected: this test **will now fail** because it called `/api/tenants/cinnox/publish` with `body: {}` — that's exactly the V1 PublishPanel behavior we're moving to legacy in Task 12. Leave this test broken for now; it gets fixed by Task 12's legacy wrapper or rewritten in Task 14.

- [ ] **Step 7: Commit**

```bash
git add autoservice/api_routes.py autoservice/change_request/repository.py tests/api_routes/test_publish_with_cr.py
git commit -m "feat(publish): /api/tenants/:tid/publish requires cr_id, transitions CR through state machine"
```

Note in the commit body: "Existing e2e test_e2e_publish_v1_v2_rollback temporarily broken — fixed in next commit (legacy wrapper)."

---

### Task 11: Rollback handler creates inverse CR

**Files:**
- Modify: `autoservice/api_routes.py` (rollback_tenant handler)
- Modify: `autoservice/change_request/repository.py` (add `mark_rolled_back`)
- Create: `tests/api_routes/test_rollback_inverse_cr.py`

- [ ] **Step 1: Write failing rollback tests**

Create `tests/api_routes/test_rollback_inverse_cr.py`:

```python
"""Rollback creates a source='rollback' CR and marks the rolled-back CR
as rolled_back."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from autoservice.change_request import repository as repo
from autoservice.change_request.models import CRSource, CRStatus


@pytest.fixture
def app_client(isolated_audit_db: Path, tmp_path: Path,
               monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("AUTH_DEV_MODE", "1")
    monkeypatch.setenv("AUTOSERVICE_SANDBOX_DIR", str(tmp_path / "sandbox"))
    monkeypatch.setenv("AUTOSERVICE_RELEASES_DIR", str(tmp_path / "released"))
    monkeypatch.setenv("AUTOSERVICE_CURRENT_DIR", str(tmp_path / "current"))
    sandbox = tmp_path / "sandbox" / "cinnox"
    (sandbox / "souls").mkdir(parents=True)
    for role in ("customer", "translate", "lead", "triage"):
        (sandbox / "souls" / f"{role}_soul.md").write_text(f"# {role}\n")
    (sandbox / "kb").mkdir()
    (sandbox / "config.json").write_text('{"tenant_id":"cinnox"}\n')
    from autoservice.web_gateway import create_app
    app = create_app()
    client = TestClient(app)
    client.post("/api/auth/dev-login")
    return client


def _make_published_cr(client: TestClient, tenant_id: str = "cinnox") -> tuple[str, str]:
    """Helper — create -> ready -> publish, returns (cr_id, version)."""
    r1 = client.post("/api/crs",
                     json={"tenant_id": tenant_id, "source": "manual", "title": "T"})
    cr_id = r1.json()["id"]
    client.patch(f"/api/crs/{cr_id}/status",
                 json={"status": "ready_for_review"})
    r2 = client.post(f"/api/tenants/{tenant_id}/publish", json={"cr_id": cr_id})
    return cr_id, r2.json()["version"]


def test_rollback_creates_inverse_cr(app_client: TestClient):
    cr_v1, v1 = _make_published_cr(app_client)
    cr_v2, v2 = _make_published_cr(app_client)
    r = app_client.post(
        "/api/tenants/cinnox/rollback",
        json={"version": v1, "reason": "v2 was broken"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    # Response carries the new inverse CR id
    assert "rollback_cr_id" in body
    inverse_cr_id = body["rollback_cr_id"]
    inverse = repo.load_cr(inverse_cr_id)
    assert inverse.source is CRSource.ROLLBACK
    assert inverse.status is CRStatus.PUBLISHED
    assert inverse.tenant_id == "cinnox"


def test_rollback_marks_old_cr_rolled_back(app_client: TestClient):
    cr_v1, v1 = _make_published_cr(app_client)
    cr_v2, v2 = _make_published_cr(app_client)
    app_client.post(
        "/api/tenants/cinnox/rollback",
        json={"version": v1, "reason": "v2 was broken"},
    )
    cr_v2_after = repo.load_cr(cr_v2)
    assert cr_v2_after.status is CRStatus.ROLLED_BACK
    assert cr_v2_after.rolled_back_to_ver == v1


def test_rollback_metadata_carries_reason(app_client: TestClient):
    cr_v1, v1 = _make_published_cr(app_client)
    _ = _make_published_cr(app_client)
    r = app_client.post(
        "/api/tenants/cinnox/rollback",
        json={"version": v1, "reason": "v2 was broken"},
    )
    inverse_cr = repo.load_cr(r.json()["rollback_cr_id"])
    import json as _json
    meta = _json.loads(inverse_cr.metadata_json)
    assert meta["reason"] == "v2 was broken"
    assert meta["to_version"] == v1
```

- [ ] **Step 2: Run to verify it fails**

```bash
uv run pytest tests/api_routes/test_rollback_inverse_cr.py -v
```

Expected: rollback succeeds but no `rollback_cr_id` in response.

- [ ] **Step 3: Add `mark_rolled_back` helper to repository.py**

Append to `autoservice/change_request/repository.py`:

```python
def mark_rolled_back(cr_id: str, *, to_version: str, actor: str) -> None:
    """Transition a published CR -> rolled_back and stamp the target version.

    Called by the rollback API handler after the inverse CR has been created.
    """
    cr = load_cr(cr_id)
    if cr is None:
        raise _sm.CRNotFound(cr_id)
    _sm.validate_transition(cr.status, CRStatus.ROLLED_BACK, cr_id=cr_id)

    now = _now_iso()
    with closing(_connect()) as conn, conn:
        conn.execute(
            "UPDATE change_requests "
            "SET status=?, rolled_back_to_ver=?, updated_at=?, "
            "    closed_at=COALESCE(closed_at, ?) "
            "WHERE id=?",
            (CRStatus.ROLLED_BACK.value, to_version, now, now, cr_id),
        )
        conn.execute(
            "INSERT INTO cr_audit (cr_id, ts, actor, action, payload) "
            "VALUES (?, ?, ?, 'rolled_back', ?)",
            (cr_id, now, actor,
             json.dumps({"to_version": to_version})),
        )


def find_published_cr_for_version(tenant_id: str, version: str) -> Optional[CR]:
    """Look up the CR that published this version (uses target_release_ver)."""
    with closing(_connect()) as conn, conn:
        row = conn.execute(
            "SELECT id FROM change_requests "
            "WHERE tenant_id=? AND target_release_ver=? AND status='published' "
            "LIMIT 1",
            (tenant_id, version),
        ).fetchone()
    return load_cr(row[0]) if row else None
```

- [ ] **Step 4: Modify `rollback_tenant` handler in api_routes.py**

Find the existing `rollback_tenant` function (around line 2763). Modify:

```python
@api_router.post("/tenants/{tenant_id}/rollback")
async def rollback_tenant(
    tenant_id: str,
    request: Request,
    auth_ctx: dict = Depends(_MASTER_AUTH_DEP),
):
    body = await request.json()
    target = body.get("version")
    reason = body.get("reason", "")
    actor = (auth_ctx.get("email") if isinstance(auth_ctx, dict) else None) or "unknown"

    if not target:
        raise HTTPException(400, "version required")
    if target not in _tenant_paths.list_release_versions(tenant_id):
        raise HTTPException(404, f"version {target!r} not found in release history")

    current = _tenant_pointer.get_current_version(tenant_id)

    # === 1. Flip pointer ===
    _tenant_pointer.flip_pointer(
        tenant_id, target, actor=actor, rolled_back_from=current,
    )

    # === 2. Create inverse CR ===
    from autoservice.change_request import repository as _cr_repo
    from autoservice.change_request.models import CRSource, CRStatus

    inverse_cr_id = _cr_repo.create_cr(
        tenant_id=tenant_id,
        source=CRSource.ROLLBACK,
        actor=actor,
        title=f"Rollback to {target}",
        description=reason,
        initial_status=CRStatus.PUBLISHED,
        metadata={
            "from_version": current,
            "to_version": target,
            "reason": reason,
        },
    )

    # === 3. Mark the rolled-back CR (if findable) ===
    if current is not None:
        old_cr = _cr_repo.find_published_cr_for_version(tenant_id, current)
        if old_cr is not None:
            _cr_repo.mark_rolled_back(old_cr.id, to_version=target, actor=actor)

    # === 4. Notify runtime ===
    await _notify_runtime_after_pointer_flip(tenant_id)

    return {
        "tenant_id": tenant_id,
        "version": target,
        "rolled_back_from": current,
        "reason": reason,
        "rollback_cr_id": inverse_cr_id,
    }
```

- [ ] **Step 5: Run to verify it passes**

```bash
uv run pytest tests/api_routes/test_rollback_inverse_cr.py -v
```

Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add autoservice/api_routes.py autoservice/change_request/repository.py tests/api_routes/test_rollback_inverse_cr.py
git commit -m "feat(rollback): create inverse CR + mark old CR rolled_back"
```

---

### Task 12: Legacy publish wrapper — `/api/legacy/tenants/:tid/publish`

**Files:**
- Create: `autoservice/legacy_routes.py`
- Modify: `autoservice/api_routes.py` (mount legacy_router)
- Modify: `frontend/apps/admin-portal/src/components/PublishPanel.tsx` (URL change)
- Modify: existing e2e test (rename URL)
- Create: `tests/api_routes/test_legacy_publish_wrapper.py`

- [ ] **Step 1: Write failing legacy wrapper test**

Create `tests/api_routes/test_legacy_publish_wrapper.py`:

```python
"""POST /api/legacy/tenants/:tid/publish auto-creates a source='legacy_publish'
CR and runs the standard V2 publish flow inside the same request."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from autoservice.change_request import repository as repo
from autoservice.change_request.models import CRSource, CRStatus


@pytest.fixture
def app_client(isolated_audit_db: Path, tmp_path: Path,
               monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("AUTH_DEV_MODE", "1")
    monkeypatch.setenv("AUTOSERVICE_SANDBOX_DIR", str(tmp_path / "sandbox"))
    monkeypatch.setenv("AUTOSERVICE_RELEASES_DIR", str(tmp_path / "released"))
    monkeypatch.setenv("AUTOSERVICE_CURRENT_DIR", str(tmp_path / "current"))
    sandbox = tmp_path / "sandbox" / "cinnox"
    (sandbox / "souls").mkdir(parents=True)
    for role in ("customer", "translate", "lead", "triage"):
        (sandbox / "souls" / f"{role}_soul.md").write_text(f"# {role}\n")
    (sandbox / "kb").mkdir()
    (sandbox / "config.json").write_text('{"tenant_id":"cinnox"}\n')
    from autoservice.web_gateway import create_app
    app = create_app()
    client = TestClient(app)
    client.post("/api/auth/dev-login")
    return client


def test_legacy_publish_creates_legacy_cr_and_publishes(app_client: TestClient):
    r = app_client.post("/api/legacy/tenants/cinnox/publish", json={})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["version"] == "v1"
    # Look up the auto-created CR
    crs = repo.list_crs(tenant_id="cinnox", source=CRSource.LEGACY_PUBLISH)
    assert len(crs) == 1
    legacy_cr = crs[0]
    assert legacy_cr.status is CRStatus.PUBLISHED
    assert legacy_cr.target_release_ver == "v1"
    assert legacy_cr.actor == "legacy-apply-wrapper"


def test_legacy_publish_does_not_trip_active_cr_constraint(app_client: TestClient):
    """legacy_publish CRs start at READY_FOR_REVIEW then immediately move to
    PUBLISHED inside the same handler, so they shouldn't keep the slot."""
    # First legacy publish
    app_client.post("/api/legacy/tenants/cinnox/publish", json={})
    # Should be able to immediately make a manual CR
    r = app_client.post(
        "/api/crs",
        json={"tenant_id": "cinnox", "source": "manual", "title": "next"},
    )
    assert r.status_code == 201


def test_legacy_publish_handler_actor_string(app_client: TestClient):
    app_client.post("/api/legacy/tenants/cinnox/publish", json={})
    crs = repo.list_crs(tenant_id="cinnox", source=CRSource.LEGACY_PUBLISH)
    assert crs[0].actor == "legacy-apply-wrapper"
```

- [ ] **Step 2: Run to verify it fails**

```bash
uv run pytest tests/api_routes/test_legacy_publish_wrapper.py -v
```

Expected: 404 on `/api/legacy/tenants/cinnox/publish`.

- [ ] **Step 3: Write the legacy_routes module**

Create `autoservice/legacy_routes.py`:

```python
"""V1 endpoints relocated to /api/legacy/* for deprecation tracking.

See docs/superpowers/specs/2026-05-11-admin-v2-design.md §2.8 + §8.

Each handler in here is slated for removal in §8 V1 retirement; new code
should target /api/* (V2) instead.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from autoservice import auth as _auth
from autoservice.change_request import repository as cr_repo
from autoservice.change_request.models import CRSource, CRStatus


legacy_router = APIRouter(prefix="/legacy")


_LEGACY_ACTOR = "legacy-apply-wrapper"


@legacy_router.post("/tenants/{tenant_id}/publish")
async def legacy_publish(
    tenant_id: str,
    request: Request,
    auth_ctx: dict = Depends(_auth.require_tenant_access_for("_master")),
):
    """V1 publish path — auto-creates a legacy_publish CR + runs V2 publish.

    Preserves the behavior expected by V1 PublishPanel (POST with empty body
    returns {version, snapshot_path, ...}) while routing the audit trail
    through the new CR layer.
    """
    real_actor = (auth_ctx.get("email") if isinstance(auth_ctx, dict) else None) or _LEGACY_ACTOR

    # Step A — create the legacy_publish CR in READY_FOR_REVIEW.
    cr_id = cr_repo.create_cr(
        tenant_id=tenant_id,
        source=CRSource.LEGACY_PUBLISH,
        actor=_LEGACY_ACTOR,
        title=f"V1 legacy publish ({real_actor})",
        description=f"Created by V1 PublishPanel call. Real actor: {real_actor}",
        initial_status=CRStatus.READY_FOR_REVIEW,
        metadata={"real_actor": real_actor},
    )

    # Step B — delegate to the V2 publish handler.
    from autoservice.api_routes import publish_tenant

    # Re-package as if a V2 caller passed cr_id.
    class _FakeRequest:
        def __init__(self, body: dict):
            self._body = body
        async def json(self):
            return self._body

    return await publish_tenant(
        tenant_id=tenant_id,
        request=_FakeRequest({"cr_id": cr_id}),     # type: ignore[arg-type]
        auth_ctx=auth_ctx,
    )
```

- [ ] **Step 4: Mount `legacy_router` in api_routes.py**

In `autoservice/api_routes.py`, near the bottom where `_operator_router` is included:

```python
from autoservice.legacy_routes import legacy_router as _legacy_router  # noqa: E402

api_router.include_router(_legacy_router)
```

- [ ] **Step 5: Run new test to verify it passes**

```bash
uv run pytest tests/api_routes/test_legacy_publish_wrapper.py -v
```

Expected: 3 passed.

- [ ] **Step 6: Update V1 PublishPanel to call the new URL**

Modify `frontend/apps/admin-portal/src/components/PublishPanel.tsx`:

Replace the `onPublish` URL:
```typescript
// BEFORE
const r = await fetch(`/api/tenants/${encodeURIComponent(tenantId)}/publish`, {

// AFTER
const r = await fetch(`/api/legacy/tenants/${encodeURIComponent(tenantId)}/publish`, {
```

And the doc comment at top:
```typescript
/**
 * Minimal admin UI for the snapshot+pointer publish/rollback flow.
 *
 * V1 deprecation: this component now targets /api/legacy/tenants/:tid/publish
 * which auto-creates a legacy_publish CR for audit. The non-legacy /api/tenants/
 * /:tid/publish URL is reserved for V2 admin UI (requires cr_id).
 *
 * Spec: docs/superpowers/specs/2026-05-11-admin-v2-design.md §2.8 + §7.
 */
```

(Leave the rollback URL as-is — rollback still works under `/api/tenants/:tid/rollback` since it doesn't require cr_id.)

- [ ] **Step 7: Update the broken e2e test to use the legacy URL**

Locate `tests/e2e/test_publish_v1_v2_rollback.py` (or wherever commit `5aaa42a` placed the e2e). Replace the URL it POSTs to from `/api/tenants/cinnox/publish` to `/api/legacy/tenants/cinnox/publish`. Add a comment:

```python
# Uses the V1 legacy publish path (PublishPanel calls it). V2 path
# requires cr_id and is exercised by tests/api_routes/test_publish_with_cr.py.
```

- [ ] **Step 8: Run the e2e test to confirm it's green again**

```bash
uv run pytest tests/e2e/test_publish_v1_v2_rollback.py -v
```

Expected: passes.

- [ ] **Step 9: Run the full P1 suite for regression**

```bash
uv run pytest tests/change_request/ tests/release_snapshot/ tests/api_routes/test_publish_with_cr.py tests/api_routes/test_rollback_inverse_cr.py tests/api_routes/test_legacy_publish_wrapper.py tests/e2e/test_publish_v1_v2_rollback.py -v
```

Expected: all pass.

- [ ] **Step 10: Commit**

```bash
git add autoservice/legacy_routes.py autoservice/api_routes.py frontend/apps/admin-portal/src/components/PublishPanel.tsx tests/api_routes/test_legacy_publish_wrapper.py tests/e2e/test_publish_v1_v2_rollback.py
git commit -m "feat(legacy_routes): POST /api/legacy/tenants/:tid/publish wraps V1 PublishPanel call in a legacy_publish CR"
```

---

## Phase E — Backfill + final E2E

### Task 13: Backfill script — migration CRs for pre-existing release versions

**Files:**
- Create: `scripts/backfill_cr_for_releases.py`
- Modify: `Makefile` (add `migrate-cr-backfill` target)
- Create: `tests/scripts/__init__.py`
- Create: `tests/scripts/test_backfill_cr_for_releases.py`

- [ ] **Step 1: Write failing backfill test**

Create `tests/scripts/test_backfill_cr_for_releases.py`:

```python
"""Backfill script creates one migration CR per existing release version."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from autoservice.change_request import repository as repo
from autoservice.change_request.models import CRSource


def _seed_release(releases_dir: Path, tenant_id: str, version: str) -> None:
    d = releases_dir / tenant_id / version
    d.mkdir(parents=True, exist_ok=True)
    (d / "manifest.yaml").write_text(
        yaml.safe_dump({
            "version": version,
            "framework_ver": "deadbeef",
            "published_at": "2026-05-01T00:00:00+00:00",
            "gate_results": {"passed": True},
        }),
    )


def test_backfill_creates_one_cr_per_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, isolated_audit_db: Path,
):
    monkeypatch.setenv("AUTOSERVICE_RELEASES_DIR", str(tmp_path / "released"))
    _seed_release(tmp_path / "released", "cinnox", "v1")
    _seed_release(tmp_path / "released", "cinnox", "v2")
    _seed_release(tmp_path / "released", "acme", "v1")

    from scripts.backfill_cr_for_releases import main
    main(dry_run=False)

    cinnox_crs = repo.list_crs(tenant_id="cinnox", source=CRSource.MIGRATION)
    assert len(cinnox_crs) == 2
    acme_crs = repo.list_crs(tenant_id="acme", source=CRSource.MIGRATION)
    assert len(acme_crs) == 1


def test_backfill_is_idempotent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, isolated_audit_db: Path,
):
    monkeypatch.setenv("AUTOSERVICE_RELEASES_DIR", str(tmp_path / "released"))
    _seed_release(tmp_path / "released", "cinnox", "v1")

    from scripts.backfill_cr_for_releases import main
    main(dry_run=False)
    main(dry_run=False)       # second run no-op
    crs = repo.list_crs(tenant_id="cinnox", source=CRSource.MIGRATION)
    assert len(crs) == 1


def test_backfill_dry_run_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, isolated_audit_db: Path,
):
    monkeypatch.setenv("AUTOSERVICE_RELEASES_DIR", str(tmp_path / "released"))
    _seed_release(tmp_path / "released", "cinnox", "v1")

    from scripts.backfill_cr_for_releases import main
    main(dry_run=True)
    assert repo.list_crs(tenant_id="cinnox") == []


def test_backfill_stamps_target_release_ver(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, isolated_audit_db: Path,
):
    monkeypatch.setenv("AUTOSERVICE_RELEASES_DIR", str(tmp_path / "released"))
    _seed_release(tmp_path / "released", "cinnox", "v3")

    from scripts.backfill_cr_for_releases import main
    main(dry_run=False)
    cr = repo.list_crs(tenant_id="cinnox")[0]
    assert cr.target_release_ver == "v3"
```

- [ ] **Step 2: Run to verify it fails**

```bash
uv run pytest tests/scripts/test_backfill_cr_for_releases.py -v
```

Expected: `ModuleNotFoundError: No module named 'scripts.backfill_cr_for_releases'`.

- [ ] **Step 3: Write the backfill script**

Create `scripts/backfill_cr_for_releases.py`:

```python
"""One-shot backfill: create one source='migration' CR per pre-existing
release version directory.

Runs once after Phase 1 of admin V2 deploys. Subsequent runs are no-ops
(detects already-backfilled versions via target_release_ver lookup).

Usage:
    uv run python -m scripts.backfill_cr_for_releases [--dry-run]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from autoservice import tenant_paths
from autoservice.change_request import repository as repo
from autoservice.change_request.models import CRSource, CRStatus


def _enumerate_versions() -> list[tuple[str, str, Path]]:
    """Walk AUTOSERVICE_RELEASES_DIR and yield (tenant_id, version, dir)."""
    root = tenant_paths._resolve("AUTOSERVICE_RELEASES_DIR", ".autoservice/released")  # type: ignore[attr-defined]
    if not root.exists():
        return []
    out: list[tuple[str, str, Path]] = []
    for tenant_dir in sorted(root.iterdir()):
        if not tenant_dir.is_dir():
            continue
        for ver_dir in sorted(tenant_dir.iterdir()):
            if not ver_dir.is_dir():
                continue
            if not ver_dir.name.startswith("v"):
                continue
            out.append((tenant_dir.name, ver_dir.name, ver_dir))
    return out


def _already_backfilled(tenant_id: str, version: str) -> bool:
    found = repo.find_published_cr_for_version(tenant_id, version)
    return found is not None


def main(*, dry_run: bool = False) -> int:
    versions = _enumerate_versions()
    created = 0
    skipped = 0
    for tenant_id, version, ver_dir in versions:
        if _already_backfilled(tenant_id, version):
            print(f"  skip  {tenant_id}/{version} (already backfilled)")
            skipped += 1
            continue
        if dry_run:
            print(f"  DRY-RUN would create migration CR for {tenant_id}/{version}")
            continue

        manifest_path = ver_dir / "manifest.yaml"
        published_at = None
        if manifest_path.is_file():
            try:
                manifest = yaml.safe_load(manifest_path.read_text())
                published_at = manifest.get("published_at")
            except Exception:
                pass

        cr_id = repo.create_cr(
            tenant_id=tenant_id,
            source=CRSource.MIGRATION,
            actor="system",
            title=f"Migration backfill for {version}",
            description=(
                "Auto-generated by scripts/backfill_cr_for_releases.py to "
                "give pre-existing release versions a CR audit entry "
                "(spec §2.3 / §9.5)."
            ),
            initial_status=CRStatus.PUBLISHED,
            metadata={
                "backfill": True,
                "version": version,
                "original_published_at": published_at,
            },
        )
        repo.set_target_release_ver(cr_id, version)
        print(f"  created  {tenant_id}/{version} -> {cr_id}")
        created += 1

    print(f"\nbackfill: {created} created, {skipped} skipped")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    sys.exit(main(dry_run=args.dry_run))
```

- [ ] **Step 4: Add `scripts/__init__.py` if missing**

Check whether `scripts/__init__.py` exists. If not, create an empty file so `from scripts.backfill_cr_for_releases import main` works under pytest.

- [ ] **Step 5: Create `tests/scripts/__init__.py`**

Create empty `tests/scripts/__init__.py`.

- [ ] **Step 6: Run to verify it passes**

```bash
uv run pytest tests/scripts/test_backfill_cr_for_releases.py -v
```

Expected: 4 passed.

- [ ] **Step 7: Add Makefile target**

Append to `Makefile`:

```makefile
.PHONY: migrate-cr-backfill migrate-cr-backfill-dry-run
migrate-cr-backfill:
	uv run python -m scripts.backfill_cr_for_releases

migrate-cr-backfill-dry-run:
	uv run python -m scripts.backfill_cr_for_releases --dry-run
```

- [ ] **Step 8: Commit**

```bash
git add scripts/backfill_cr_for_releases.py scripts/__init__.py tests/scripts/__init__.py tests/scripts/test_backfill_cr_for_releases.py Makefile
git commit -m "feat(scripts): backfill_cr_for_releases — migration CRs for pre-existing release versions"
```

---

### Task 14: P1 E2E — V2 publish + rollback + audit round-trip

**Files:**
- Create: `tests/e2e/test_p1_cr_round_trip.py`

- [ ] **Step 1: Write the end-to-end test**

Create `tests/e2e/test_p1_cr_round_trip.py`:

```python
"""End-to-end: V2 publish v1 -> publish v2 -> rollback -> publish v3,
with full CR audit chain visible at each step."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from autoservice.change_request import repository as repo
from autoservice.change_request.models import CRSource, CRStatus


@pytest.fixture
def app_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("AUTH_DEV_MODE", "1")
    monkeypatch.setenv("AUTOSERVICE_SANDBOX_DIR", str(tmp_path / "sandbox"))
    monkeypatch.setenv("AUTOSERVICE_RELEASES_DIR", str(tmp_path / "released"))
    monkeypatch.setenv("AUTOSERVICE_CURRENT_DIR", str(tmp_path / "current"))
    monkeypatch.setenv("AUTOSERVICE_RUNTIME_DATA_DIR", str(tmp_path / "database"))
    sandbox = tmp_path / "sandbox" / "cinnox"
    (sandbox / "souls").mkdir(parents=True)
    for role in ("customer", "translate", "lead", "triage"):
        (sandbox / "souls" / f"{role}_soul.md").write_text(f"# {role}\n")
    (sandbox / "kb").mkdir()
    (sandbox / "config.json").write_text('{"tenant_id":"cinnox"}\n')
    from autoservice.web_gateway import create_app
    app = create_app()
    client = TestClient(app)
    client.post("/api/auth/dev-login")
    return client


def _create_and_publish(client: TestClient, title: str) -> tuple[str, str]:
    r1 = client.post("/api/crs",
                     json={"tenant_id": "cinnox", "source": "manual", "title": title})
    cr_id = r1.json()["id"]
    client.patch(f"/api/crs/{cr_id}/status",
                 json={"status": "ready_for_review"})
    r2 = client.post("/api/tenants/cinnox/publish", json={"cr_id": cr_id})
    return cr_id, r2.json()["version"]


def test_v2_full_round_trip(app_client: TestClient):
    # Publish v1
    cr1, v1 = _create_and_publish(app_client, "v1: initial soul")
    assert v1 == "v1"
    assert repo.load_cr(cr1).status is CRStatus.PUBLISHED
    assert repo.load_cr(cr1).target_release_ver == "v1"

    # Publish v2
    cr2, v2 = _create_and_publish(app_client, "v2: tone tweak")
    assert v2 == "v2"
    assert repo.load_cr(cr2).status is CRStatus.PUBLISHED

    # Rollback to v1
    r = app_client.post(
        "/api/tenants/cinnox/rollback",
        json={"version": v1, "reason": "v2 regressed sentiment"},
    )
    assert r.status_code == 200
    rb_cr_id = r.json()["rollback_cr_id"]
    rb_cr = repo.load_cr(rb_cr_id)
    assert rb_cr.source is CRSource.ROLLBACK
    assert rb_cr.status is CRStatus.PUBLISHED
    # v2 CR marked rolled_back
    cr2_after = repo.load_cr(cr2)
    assert cr2_after.status is CRStatus.ROLLED_BACK
    assert cr2_after.rolled_back_to_ver == v1

    # Publish v3
    cr3, v3 = _create_and_publish(app_client, "v3: re-tone")
    assert v3 == "v3"

    # Tenant CR history should now have v1 (published), v2 (rolled_back),
    # the inverse rollback (published), and v3 (published).
    all_crs = repo.list_crs(tenant_id="cinnox")
    by_source = {}
    for c in all_crs:
        by_source.setdefault(c.source, []).append(c)
    assert len(by_source[CRSource.MANUAL]) == 3
    assert len(by_source[CRSource.ROLLBACK]) == 1
    # state counts
    statuses = [c.status for c in all_crs]
    assert statuses.count(CRStatus.PUBLISHED) == 3   # v1, v3, rollback
    assert statuses.count(CRStatus.ROLLED_BACK) == 1 # v2

    # Audit chain on the rollback CR has 'created' at minimum
    rb_audit = repo.list_audit(rb_cr_id)
    actions = [a.action for a in rb_audit]
    assert "created" in actions


def test_v1_and_v2_paths_coexist(app_client: TestClient):
    """A legacy_publish CR and a V2 manual CR for the same tenant must not
    collide on the partial unique index, because legacy_publish lands directly
    in PUBLISHED state (terminal)."""
    # V1 legacy publish first
    r1 = app_client.post("/api/legacy/tenants/cinnox/publish", json={})
    assert r1.status_code == 200
    v1 = r1.json()["version"]

    # Then a V2 manual CR on the same tenant — must succeed
    r2 = app_client.post(
        "/api/crs",
        json={"tenant_id": "cinnox", "source": "manual", "title": "V2 follow-up"},
    )
    assert r2.status_code == 201

    legacy_crs = repo.list_crs(tenant_id="cinnox", source=CRSource.LEGACY_PUBLISH)
    manual_crs = repo.list_crs(tenant_id="cinnox", source=CRSource.MANUAL)
    assert len(legacy_crs) == 1
    assert len(manual_crs) == 1
    assert legacy_crs[0].target_release_ver == v1
```

- [ ] **Step 2: Run to verify it passes**

```bash
uv run pytest tests/e2e/test_p1_cr_round_trip.py -v
```

Expected: 2 passed.

- [ ] **Step 3: Run the entire P1 test suite for full regression**

```bash
uv run pytest tests/change_request/ tests/release_snapshot/ tests/api_routes/test_publish_with_cr.py tests/api_routes/test_rollback_inverse_cr.py tests/api_routes/test_legacy_publish_wrapper.py tests/scripts/ tests/e2e/test_p1_cr_round_trip.py tests/e2e/test_publish_v1_v2_rollback.py -v
```

Expected: all pass.

- [ ] **Step 4: Run the whole repo test suite for regression**

```bash
uv run pytest -x -q
```

Expected: all pre-existing tests still pass. If any test other than the originally-broken e2e fails, investigate before committing.

- [ ] **Step 5: Commit**

```bash
git add tests/e2e/test_p1_cr_round_trip.py
git commit -m "test(e2e): V2 CR round-trip — publish v1 -> v2 -> rollback -> v3, with legacy+V2 coexistence"
```

---

## SLO Verification (final checklist before declaring P1 done)

After Task 14 commits, run the spec §9.3 P1 SLO checklist manually:

- [ ] `database/audit.db` contains `change_requests` + `cr_audit` tables — verify with `sqlite3 .autoservice/database/audit.db '.schema'`
- [ ] Partial unique index returns 409 on second active CR — covered by `test_second_active_cr_same_tenant_raises_cr_conflict`
- [ ] State machine illegal transitions raise — covered by `test_state_machine.py`
- [ ] `POST /api/tenants/:tid/publish` requires cr_id, 400 otherwise — `test_publish_without_cr_id_returns_400`
- [ ] `POST /api/legacy/tenants/:tid/publish` auto-creates legacy_publish CR — `test_legacy_publish_creates_legacy_cr_and_publishes`
- [ ] Rollback creates source='rollback' CR + marks old CR rolled_back — `test_rollback_creates_inverse_cr` + `test_rollback_marks_old_cr_rolled_back`
- [ ] `manifest.yaml` carries `cr_id` / `cr_source` / `cr_actor` — `test_publish_happy_path_manifest_carries_cr_metadata`
- [ ] Backfill creates migration CRs for pre-existing release versions — `test_backfill_creates_one_cr_per_version` + idempotent
- [ ] E2E: publish v1 → v2 → rollback → v3 with CR audit at every step — `test_v2_full_round_trip`

When all 9 boxes are ticked, P1 is done.

---

## Out of scope for P1 (deferred to subsequent plans)

These spec items intentionally land in later plans:

- §2.x sandbox_diff auto-population (depends on §3 ingest jobs and §5 patch_spec writes)
- §3 content generators (P4)
- §4 PV2 turn-end hook (P2)
- §5 Dream → CR bridge + `from-proposal` endpoint (P5)
- §6 PV2 prompt overlays (P3)
- §7 Admin V2 UI (P6) — V1 PublishPanel keeps working via Task 12 legacy wrapper
- §10.1 ETag-based CR edit conflict UX (P6 frontend concern)

V1 endpoint physical cleanup (§8 retirement) does **not** happen in P1 — only the rename to `/api/legacy/*` is in P1.
