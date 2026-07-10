# Flaremailer Backend

FastAPI control plane and durable database-backed delivery worker for Cloudflare Email
Service. The API exposes a stable OpenAPI contract at `/openapi.json` for the dashboard's
Orval client generation.

## Runtime model

- PostgreSQL is the supported runtime database. The default `DATABASE_URL` points to a
  local PostgreSQL `flaremailer` database.
- SQLite support and `database_auto_create` exist for isolated tests only.
- The API inserts immutable, rendered email content into the database outbox.
- A separate worker claims due rows, calls Cloudflare's REST endpoint, and persists every
  delivery attempt.
- Status `sent` means Cloudflare accepted the send request. It does **not** claim inbox
  delivery, opens, or clicks.

## Local setup

Python 3.12, [uv](https://docs.astral.sh/uv/), Node.js, pnpm, and PostgreSQL are
required. Use the repository-level environment and commands from the project root:

```bash
make env
make install
make migrate
make backend
```

In another terminal, start the durable delivery worker:

```bash
make worker
```

Platform settings are read only from the process environment. The root `Makefile` exports
the private `apps/backend/.env`. Cloudflare account IDs and API tokens are configured per
project through the dashboard/API and stored in PostgreSQL; tokens are encrypted at rest.
Run one currently available batch and exit after exporting the platform settings:

```bash
set -a
source apps/backend/.env
set +a
cd apps/backend && uv run python -m app.worker --once
```

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | `postgresql+asyncpg://flaremailer:flaremailer@localhost:5432/flaremailer` | Async SQLAlchemy PostgreSQL URL |
| `SESSION_SECRET` | development-only value | Cookie signature secret; set a random 32+ byte value in production |
| `COOKIE_SECURE` | `false` | Must be `true` in production |
| `COOKIE_DOMAIN` | unset | Optional session cookie domain |
| `CORS_ORIGINS` | `http://localhost:3000` | Comma-separated credentialed origins |
| `CREDENTIAL_ENCRYPTION_KEY` | development-only value | Master secret for project API-token encryption; set a random 32+ byte value in production |
| `CLOUDFLARE_API_BASE_URL` | Cloudflare v4 API | Override for tests/proxies |
| `CLOUDFLARE_TIMEOUT_SECONDS` | `15` | REST request timeout |
| `WORKER_BATCH_SIZE` | `20` | Rows claimed per polling batch |
| `WORKER_POLL_SECONDS` | `1` | Idle poll interval |
| `WORKER_MAX_ATTEMPTS` | `4` | Maximum provider attempts per message |
| `WORKER_BACKOFF_SECONDS` | `5,30,120` | Retry delays; the final value is reused if needed |
| `WORKER_LOCK_TIMEOUT_SECONDS` | `300` | Reclaim age for a worker interrupted while sending |

`ENVIRONMENT=production` rejects development session/encryption secrets, a non-PostgreSQL
URL, or an insecure cookie configuration. Keep the encryption key stable: changing it
makes previously stored project tokens unreadable until each project saves a new token.

## Authentication

Dashboard routes use a signed, `HttpOnly`, `SameSite=Lax` session cookie. Register or log
in through `/api/v1/auth/register` and `/api/v1/auth/login`.

Project API keys can enqueue and inspect project email activity. The complete key is
returned only by the create endpoint; only its SHA-256 hash and lookup prefix are stored.
Use either header:

```http
Authorization: Bearer fm_live_...
```

```http
X-API-Key: fm_live_...
```

## Primary endpoints

All application routes use `/api/v1`. Every OpenAPI operation has a unique explicit
`operationId`.

| Area | Endpoints |
| --- | --- |
| Auth | `POST /auth/register`, `POST /auth/login`, `POST /auth/logout`, `GET /auth/me` |
| Projects | `GET/POST /projects`, `GET/PATCH/DELETE /projects/{project_id}` |
| Cloudflare credentials | `GET/PUT/DELETE /projects/{project_id}/credentials` |
| API keys | `GET/POST /projects/{project_id}/api-keys`, `DELETE .../{key_id}` |
| Domains | `GET/POST /projects/{project_id}/domains`, `PATCH/DELETE .../{domain_id}` |
| Templates | CRUD under `/projects/{project_id}/templates`, plus `POST .../{template_id}/preview` |
| Suppressions | `GET/POST /projects/{project_id}/suppressions`, `DELETE .../{suppression_id}` |
| Email | `POST/GET /emails`, `GET /emails/{email_id}`, `POST /emails/{email_id}/resend` |
| Metrics | `GET /metrics` |
| Operations | `GET /healthz`, `GET /readyz`, `GET /openapi.json` |

Session-authenticated email and metrics requests require `project_id`. API-key requests
infer the project and reject a conflicting `project_id`.

## Enqueue example

Record an active, verified sender domain before enqueueing. Domain onboarding and DNS
verification happen in Cloudflare; Flaremailer stores the resulting local send gate.

```bash
curl http://localhost:8000/api/v1/emails \
  -H 'Authorization: Bearer fm_live_...' \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: welcome-user-123' \
  -d '{
    "from": {"email": "hello@example.com", "name": "Example"},
    "to": [{"email": "reader@example.net"}],
    "reply_to": {"email": "support@example.com"},
    "subject": "Welcome",
    "html": "<strong>Hello!</strong>",
    "text": "Hello!",
    "tags": ["welcome"]
  }'
```

The API accepts up to 50 combined `to`, `cc`, and `bcc` recipients. It rejects unverified
senders, oversized content, and locally suppressed recipients. A message containing any
suppressed recipient is recorded as `suppressed` and is never handed to the provider.

`Idempotency-Key` is unique per project. Repeating the same request returns the original
message; reusing a key with a different canonical payload returns `409`.

## Templates

Templates use Jinja's sandbox with strict undefined variables and HTML autoescaping.
Imports, includes, inheritance, macros, callable expressions, the `safe` filter, and the
`attr` filter are disabled. Preview renders through the same path used at enqueue time.
Rendered content is stored on the outbox row, so later template changes cannot mutate an
already queued message.

## Worker and delivery guarantees

The PostgreSQL claim query uses `FOR UPDATE SKIP LOCKED`; conditional updates preserve the
same behavior in SQLite tests. Failures classified as transient (network errors, timeouts,
HTTP 408/409/425/429/5xx) are retried with configured backoff. Permanent provider failures
and exhausted attempts become `failed`.

Cloudflare does not document an idempotency key for this endpoint. The database worker is
therefore **at least once**: a process crash after Cloudflare accepts a request but before
the success transaction commits can cause a duplicate retry. Application-level enqueue
idempotency prevents duplicate outbox rows but cannot close that provider-side crash
window.

Cloudflare responses are retained for diagnostics. If every recipient appears only in
`permanent_bounces`, the worker records a terminal failure; mixed accepted/bounced results
retain the raw response and are marked accepted (`sent`).

## Database migrations

Apply migrations before starting either process:

```bash
make migrate
```

Create future migrations from `apps/backend` after exporting `apps/backend/.env`, and
inspect generated operations before applying them. Do not enable
`DATABASE_AUTO_CREATE` in deployed environments.

## Verification

```bash
uv run pytest
uv run ruff format --check .
uv run ruff check .
uv run mypy app
```

The tests run against an isolated SQLite database and mock Cloudflare. They cover auth,
project/key/domain flows, encrypted per-project provider credentials, safe template
rendering, suppressions, idempotency, activity, metrics, resend, worker
success/retry/failure, provider payloads, permanent bounces, and OpenAPI operation ID
uniqueness.
