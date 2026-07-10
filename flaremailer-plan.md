# Flaremailer MVP build plan

## Goal

Build a self-hosted transactional email control plane inspired by Larasend, with a FastAPI backend, a Next.js dashboard, and Cloudflare Email Service as the outbound provider.

## Product assumptions

- This first version is a single-workspace, multi-project MVP.
- Each project owns its Cloudflare account ID and API token. Tokens are encrypted in PostgreSQL with a deployment-level credential-encryption key and are write-only in the dashboard/API.
- Sender domains are onboarded in Cloudflare Email Service first, then recorded in Flaremailer for sender validation.
- Cloudflare's REST send API is the delivery path. It works from FastAPI without requiring the API itself to run in a Worker.
- PostgreSQL is the runtime database in both development and production, accessed through SQLAlchemy 2 and versioned with Alembic.
- Delivery state reflects Cloudflare's send response. Cloudflare Email Service does not expose SES-style delivery/open/click webhooks, so the MVP does not claim downstream open/click tracking.

## Architecture

```text
Next.js dashboard
      |
      | session-authenticated JSON API
      v
FastAPI control plane ---- SQLAlchemy ---- PostgreSQL
      |                            |
      | enqueue                    | durable outbox rows
      v                            v
FastAPI worker ------------ Cloudflare Email Service REST API
```

## Scope

### Backend

- Email/password registration and login using signed HTTP-only session cookies.
- Project CRUD with project-scoped API keys and encrypted, project-scoped Cloudflare sending credentials; show plaintext secrets only at entry/creation time.
- Sender-domain records with an active/verified gate.
- Template CRUD and safe variable rendering.
- `POST /v1/emails` send endpoint supporting direct HTML/text or a template, tags, reply-to, CC/BCC, and idempotency keys.
- Durable database outbox with worker retries and explicit queued, sending, sent, failed, and suppressed states.
- Activity queries, message detail, resend, summary metrics, and local suppression-list management.
- Cloudflare REST provider adapter with timeouts, normalized responses, and test fakes.
- Alembic migrations as the sole production schema-management path.
- Health/readiness endpoints, structured configuration, CORS, and consistent API errors.

### Frontend

- Authentication and onboarding screens.
- Responsive dashboard shell and overview metrics.
- Activity table with status/search filtering and message inspector/HTML preview.
- Compose/test-send flow.
- Template management and preview.
- Project settings, sender domains, API-key creation/revocation, and integration snippet.
- Clear empty, loading, success, and failure states.
- An Orval-generated TypeScript client built from FastAPI's OpenAPI document, with handwritten UI code consuming the generated contract.

### Operations and quality

- Host-native developer commands for PostgreSQL, FastAPI, the worker, and Next.js.
- Per-application environment examples and setup/deployment documentation.
- Backend unit/integration tests, frontend lint/type checks, and production builds.
- Secret-safe defaults, HTML preview sandboxing, hashed credentials, payload limits, and suppression checks.

## Delivery phases

1. Scaffold repository, configuration, data model, and API foundations.
2. Implement authentication, projects, keys, domains, templates, messages, suppressions, and Cloudflare delivery worker.
3. Implement the Next.js dashboard and connect all primary flows.
4. Add host-native developer tooling and complete documentation.
5. Run tests, linters, type checks, and builds; fix all actionable failures.

## Deferred beyond MVP

- Team invitations and role-based workspace membership.
- Cloudflare account/domain onboarding automation.
- Provider-agnostic adapters beyond Cloudflare.
- Campaign/bulk email, marketing automation, and open/click tracking.
- Billing and hosted multi-tenancy.
