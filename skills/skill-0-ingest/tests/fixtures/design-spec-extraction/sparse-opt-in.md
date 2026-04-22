# Tenant Notifications — Design

## 1. Goal
Send in-app notifications to tenant admins when a sub-tenant joins.

## 2. Scope
| Surface | Persona | Trigger |
|---------|---------|---------|
| admin-portal notifications panel | tenant admin | sub-tenant onboards |
| email digest | tenant admin | daily rollup |

## 4. Component
A notifications service with in-app + email channels.
