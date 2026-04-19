# AutoService PRD — Customer Service AI Platform

**Version:** 2.0
**Date:** 2026-03-01

## 1. Overview

AutoService is an AI-powered customer service platform for Feishu IM and web chat.

## 2. User Stories

### US-001 — Customer initiates chat

**As a** website visitor,
**I want** to open a chat widget and send a message,
**So that** I can get help without calling support.

Acceptance Criteria:
- AC-001: Widget loads within 500ms
- AC-002: First message receives a response within 3 seconds

### US-002 — Agent reviews conversation

**As a** customer service agent,
**I want** to see all active conversations in a single dashboard,
**So that** I can prioritize and respond efficiently.

## 3. Non-Functional Requirements

### NFR-001 — Latency

API response time < 200ms at p95.

### NFR-002 — Availability

99.9% uptime during business hours.

## 4. Constraints

- Must use Claude API for AI responses
- Must integrate with existing Feishu workspace
- Python 3.12+ backend
