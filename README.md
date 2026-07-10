# Flaremailer

Flaremailer is a self-hosted transactional email control plane inspired by
[Larasend](https://github.com/savvyagents/larasend). It keeps projects, API
keys, templates, suppressions, message history, and retry state in PostgreSQL
while a durable worker sends through
[Cloudflare Email Service](https://developers.cloudflare.com/email-service/).

The application is intentionally focused on transactional mail. It is not a
bulk campaign system, and it does not claim open, click, or inbox-delivery
events that Cloudflare does not expose through the send API.

## Architecture

```text
Browser
  │ same-origin /api/* requests
  ▼
Next.js ───────────────► FastAPI ─────────► PostgreSQL
                           │                   ▲
                           │ durable outbox    │ row locking and retries
                           ▼                   │
                      delivery worker ─────────┘
                           │
                           ▼
                Cloudflare Email Service REST API
```

- **FastAPI** owns authentication, project resources, the public send API, and
  the OpenAPI contract.
- **SQLAlchemy 2** is the application data-access layer.
- **Alembic** is the production schema-management path.
- **PostgreSQL** is required for development and production. SQLite is used
  only by isolated backend tests.
- **Next.js** proxies `/api/*` to FastAPI so browser requests and signed,
  HTTP-only session cookies remain same-origin.
- **Orval** generates the typed React Query client from FastAPI OpenAPI.
- The **worker** claims outbox rows with PostgreSQL locking and records every
  attempt, failure, and retry.

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- Node.js 22+ and Corepack
- PostgreSQL 15+; PostgreSQL 17 is recommended
- `psql`, `createuser`, and `createdb` for local database administration

## Quick start

### 1. Configure the environment

Create private environment files for both applications:

```bash
make env
```

Edit `apps/backend/.env` and set:

- `PGPASSWORD` and the matching password inside `DATABASE_URL`.
- A strong `SESSION_SECRET`.
- A unique `CREDENTIAL_ENCRYPTION_KEY`; keep it stable and backed up because it
  protects every project token stored in PostgreSQL.

Edit `apps/frontend/.env` when the Next.js port or internal FastAPI origin
differs from the local defaults. The checked-in examples live beside each
application. Both real `.env` files are ignored by Git and remain mode `600`.

### 2. Create the PostgreSQL database

The local example uses `postgres:postgres` for development. On a typical Linux
installation, align that local password and create the database when it does not
already exist:

```bash
sudo -u postgres psql -c "ALTER ROLE postgres WITH PASSWORD 'postgres';"
sudo -u postgres createdb --owner=postgres flaremailer
```

Do not use the PostgreSQL superuser or this password outside local development.
For a managed PostgreSQL instance, replace the host, port, credentials, and
database in `apps/backend/.env`.

Confirm connectivity:

```bash
make db-check
```

### 3. Install and migrate

```bash
make install
make migrate
```

### 4. Start the application

Run FastAPI, the delivery worker, and Next.js together:

```bash
make dev
```

Open <http://localhost:3000>. FastAPI is available at
<http://localhost:8000>, with interactive docs at
<http://localhost:8000/docs> and OpenAPI at
<http://localhost:8000/openapi.json>.

For separate terminals, use:

```bash
make backend
make worker
make frontend
```

## First-time application setup

1. Register the first dashboard user.
2. Create a project.
3. Open **Settings > Projects > Cloudflare sending** and save that project's
   Cloudflare account ID and API token.
4. Onboard a sending domain in Cloudflare Email Service.
5. Record that domain in Flaremailer and mark it verified only after Cloudflare
   reports it ready.
6. Create a project API key and copy it immediately. Only its SHA-256 hash is
   retained.
7. Send a test message and inspect its attempts under Activity.

## Cloudflare Email Service

The sender domain must use Cloudflare DNS and be onboarded under **Compute >
Email Service > Email Sending**. Cloudflare creates the required bounce, SPF,
DKIM, and DMARC records.

Create a least-privilege API token with:

```text
Permission:        Account > Email Sending > Edit
Account resources: Include > the sending account only
```

Select the project in the dashboard and save its account ID and token under
**Settings > Projects > Cloudflare sending**. The token is write-only in the UI,
encrypted before it is stored in PostgreSQL, and resolved by the worker for each
project at send time. Updating one project never changes another project's
sending credentials.

Useful current references:

- [Send using the REST API](https://developers.cloudflare.com/email-service/api/send-emails/rest-api/)
- [Configure a sending domain](https://developers.cloudflare.com/email-service/configuration/domains/)
- [Limits](https://developers.cloudflare.com/email-service/platform/limits/)
- [Pricing](https://developers.cloudflare.com/email-service/platform/pricing/)

Cloudflare accepts at most 50 combined `to`, `cc`, and `bcc` recipients and a
5 MiB message. A Flaremailer `sent` state means Cloudflare accepted the send
request; it is not proof of inbox placement.

## Sending over HTTP

Use a project API key as a bearer token. Supply a unique idempotency key for
every logical transactional event:

```bash
curl --request POST http://localhost:8000/api/v1/emails \
  --header "Authorization: Bearer fm_live_your_project_key" \
  --header "Idempotency-Key: order-1842-receipt-v1" \
  --header "Content-Type: application/json" \
  --data '{
    "from": {
      "email": "receipts@mail.example.com",
      "name": "Acme Billing"
    },
    "to": [
      {"email": "customer@example.net", "name": "Taylor"}
    ],
    "subject": "Receipt for order 1842",
    "html": "<h1>Thanks, Taylor</h1><p>Your payment was received.</p>",
    "text": "Thanks, Taylor. Your payment was received.",
    "tags": ["receipt", "production"]
  }'
```

The API returns `202 Accepted` with a public message ID and an initial `queued`
or `suppressed` state. Delivery is asynchronous.

### Templates

To send a stored template, omit `subject`, `html`, and `text`, then provide its
ID and variables:

```json
{
  "from": {"email": "hello@mail.example.com", "name": "Acme"},
  "to": [{"email": "customer@example.net"}],
  "template_id": "00000000-0000-0000-0000-000000000000",
  "variables": {
    "first_name": "Taylor",
    "login_url": "https://example.com/login"
  },
  "tags": ["welcome"]
}
```

Templates use strict Jinja-style `{{ variable }}` expressions inside a
sandboxed renderer. Missing variables fail the enqueue request.

## Database and Alembic

Apply migrations:

```bash
make migrate
```

Create and review a model migration from `apps/backend`:

```bash
set -a
source apps/backend/.env
set +a
cd apps/backend
uv run alembic revision --autogenerate -m "describe the schema change"
cd ../..
make migrate
```

Review every autogenerated revision before applying it. Back up production
PostgreSQL before schema changes.

Open a database shell with:

```bash
make db-shell
```

## Regenerating the Orval client

Start only the backend with `make backend`, then run this in another terminal:

```bash
make orval
```

The command derives the OpenAPI URL from `API_INTERNAL_URL` in
`apps/frontend/.env`. Set `ORVAL_INPUT` there only when the OpenAPI document is
available at a different URL.
Orval owns `apps/frontend/src/generated`; do not hand-edit generated modules. The
generated output is committed so frontend builds do not require a running API.

## Verification

Run the complete backend and frontend suite:

```bash
make check
```

This runs backend integration tests, Ruff, formatting verification, strict
mypy, ESLint, TypeScript, Vitest, and a production Next.js build.

Health endpoints:

```bash
curl --fail http://localhost:8000/healthz
curl --fail http://localhost:8000/readyz
```

## Production operation

Use a managed PostgreSQL database or a PostgreSQL service with tested backups.
Build the frontend release from the repository root so `API_INTERNAL_URL` is applied:

```bash
make frontend-build
```

Then run the following as three independently supervised processes from one
immutable release. Supply each process's environment through the supervisor:

```bash
# Backend
cd apps/backend
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --proxy-headers

# Worker
cd apps/backend
uv run python -m app.worker

# Frontend
cd apps/frontend
corepack pnpm start
```

Before replacing application processes, run `make migrate` once as a release
step. Put an HTTPS reverse proxy in front of Next.js and keep the API and
PostgreSQL private.

Production environment requirements:

- Set `ENVIRONMENT=production` and `COOKIE_SECURE=true`.
- Use a fresh, high-entropy `SESSION_SECRET`.
- Generate a separate high-entropy `CREDENTIAL_ENCRYPTION_KEY`, back it up, and
  do not rotate it without re-encrypting stored project tokens.
- Set `CORS_ORIGINS` to the exact public HTTPS origin.
- Store the PostgreSQL password and credential-encryption key in a secret
  manager; restrict database access because encrypted project tokens live there.
- Monitor API readiness, worker restarts, queued/failed growth, PostgreSQL
  capacity, and Cloudflare throttling.

## Troubleshooting

**`make db-check` fails:** confirm PostgreSQL is running and that `PGHOST`,
`PGPORT`, `PGDATABASE`, and `PGUSER` match the server.

**Migrations cannot authenticate:** keep `PGPASSWORD` and the credentials inside
`DATABASE_URL` synchronized.

**Messages fail with `provider_not_configured`:** select the message's project,
open **Settings > Projects > Cloudflare sending**, and save an account ID and API
token with the required permission. The worker does not need a restart.

**Sender domain rejected:** the local verified flag is only a guardrail. The
domain must also be onboarded and ready in the same Cloudflare account as the
token.

**The dashboard cannot reach the API:** verify FastAPI is listening on port
`8000`, `API_INTERNAL_URL=http://127.0.0.1:8000` in `apps/frontend/.env`, and
the configured Next.js port matches `CORS_ORIGINS` in `apps/backend/.env`.

**Generated client is stale:** run FastAPI, execute `make orval`, review the
generated changes, then run `make check`.
