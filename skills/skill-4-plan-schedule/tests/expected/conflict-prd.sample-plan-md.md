# Order Sync Service — T-CONFLICT.1: order webhook receiver Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the HTTP endpoint that receives order-created webhooks from the merchant's store and queues a sync job for the downstream fulfillment system, honoring the multi-tenant deployment mode resolved during PRD ambiguity detection.

**Architecture:** A FastAPI route at `POST /api/webhook/order_created` validates the webhook signature, extracts `tenant_id` (when `SINGLE_TENANT_MODE=0`) or uses the singleton-tenant config (when `SINGLE_TENANT_MODE=1`), persists a sync_job row, and returns 202 with the job id. The actual sync to the fulfillment HTTP API is owned by T-CONFLICT.2 (downstream sync worker).

**Tech Stack:**
- Python 3.13+
- FastAPI + pydantic
- Postgres via SQLAlchemy 2.x (existing in repo)
- pytest + pytest-asyncio + httpx (for FastAPI TestClient)

**File Structure:**

```
# New
ordersvc/webhook/order_created.py
tests/webhook/test_order_created.py

# Modified
ordersvc/api_routes.py    ← mount the new route
```

---

## Phase A — Endpoint + handler

### Task 1: Failing webhook receiver test

**Files:**
- Create: `tests/webhook/test_order_created.py`
- Modify: `ordersvc/api_routes.py:1-30` (router init only)

- [ ] **Step 1: Write the failing test**

```python
# tests/webhook/test_order_created.py
from fastapi.testclient import TestClient
from ordersvc.api_routes import app

client = TestClient(app)


def test_order_created_webhook_returns_202_with_job_id():
    payload = {"order_id": "ord_123", "tenant_id": "tnt_a", "items": []}
    headers = {"X-Webhook-Signature": "valid-sig-for-test"}
    r = client.post("/api/webhook/order_created", json=payload, headers=headers)
    assert r.status_code == 202
    body = r.json()
    assert "job_id" in body
    assert body["job_id"].startswith("job_")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/webhook/test_order_created.py::test_order_created_webhook_returns_202_with_job_id -v`
Expected: FAIL with `404 Not Found` (route doesn't exist yet).

- [ ] **Step 3: Write the route handler**

```python
# ordersvc/webhook/order_created.py
import secrets
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

router = APIRouter()


class OrderCreatedPayload(BaseModel):
    order_id: str
    tenant_id: str
    items: list


@router.post("/api/webhook/order_created", status_code=202)
async def order_created(payload: OrderCreatedPayload, x_webhook_signature: str = Header(None)):
    if not x_webhook_signature:
        raise HTTPException(status_code=401, detail="missing signature")
    job_id = "job_" + secrets.token_urlsafe(16)
    # TODO Task 2: persist sync_job row with tenant scoping
    return {"job_id": job_id}
```

And wire it into the existing app:

```python
# ordersvc/api_routes.py (modified head)
from fastapi import FastAPI
from ordersvc.webhook.order_created import router as order_created_router

app = FastAPI()
app.include_router(order_created_router)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/webhook/test_order_created.py::test_order_created_webhook_returns_202_with_job_id -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/webhook/test_order_created.py ordersvc/webhook/order_created.py ordersvc/api_routes.py
git commit -m "feat(webhook): order_created receiver returns 202 with job_id"
```

---

### Task 2: Persist sync_job row with tenant scoping

(Plan continues for the second plan-task; structure mirrors Task 1.)
