# Order Sync Service — Product Requirements Document

## 1. Background

A small SaaS that lets merchants sync orders between their store backend and a downstream fulfillment system. Internal tool, not customer-facing.

## 2. Goals

- Reduce sync latency from 15 min (current cron) to under 60s
- Support both single-tenant deployments (own infra) and multi-tenant SaaS

## 3. User stories

### US-1: Single-tenant deployment
As an on-prem merchant, I deploy one instance and it serves only my store.
- No tenant_id field anywhere
- All config in a single env file

### US-2: Multi-tenant SaaS
As the SaaS operator, I run one instance serving multiple merchant stores.
- Every API request carries tenant_id
- Per-tenant config in a database table

### US-3: Sync triggered by order webhook
As a merchant, when my store creates an order, the downstream fulfillment system is notified within 60s.

### US-4: Manual resync
As an operator, I can trigger a full resync of all unsynced orders for a tenant.
- Endpoint: POST /api/resync
- Returns 202 with a job id

## 4. Non-functional requirements

- **NFR-1**: P95 sync latency under 60 seconds
- **NFR-2**: Every state-changing action must be audited synchronously to an append-only audit log before returning success
- **NFR-3**: Operates on networks with up to 5% packet loss

## 5. Constraints

- Audit log lives in a Postgres table the security team owns; we cannot change its schema.
- The downstream fulfillment system has rate limits we don't fully document.

## 6. Out of scope

- Customer-facing UI
- Order modification (sync only, no edit)
