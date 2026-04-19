# User Stories — AutoService Onboarding

Collected from stakeholder interviews, 2026-03-15.

## Onboarding Flow

**US-010** — As a new tenant admin, I want to register my company profile so that the system knows my industry and compliance requirements.

Acceptance Criteria:
- AC-010-1: Admin can submit company name, country, and industry
- AC-010-2: System stores compliance_profile derived from country

**US-011** — As a tenant admin, I want to upload my product catalog so that the AI can answer product-related questions.

Acceptance Criteria:
- AC-011-1: Supports CSV and Excel upload
- AC-011-2: Validation errors shown inline

**US-012** — As a tenant admin, I want to run a sandbox rehearsal before going live so that I can verify AI quality without affecting real customers.

Acceptance Criteria:
- AC-012-1: Rehearsal uses mock customer messages
- AC-012-2: AI responses shown with confidence scores
- AC-012-3: Admin can approve or reject each response

## Daily Operations

**US-020** — As a customer service agent, I want to receive an alert when the AI confidence drops below threshold so that I can take over the conversation.

**US-021** — As a customer service agent, I want to send a suggested reply as a copilot suggestion so that the human agent can approve or edit before sending.
