# Production Readiness Guide

## Mandatory Environment Settings

Set these before deploying to production:

- `ENVIRONMENT=prod`
- `ENABLE_DOCS=false`
- `REQUIRE_API_KEY=true`
- `API_KEY=<strong-random-secret>`
- `ENFORCE_NUDGE_CONSENT=true` (recommended for regulated environments)
- `AUTO_CREATE_SCHEMA=false`
- `DATABASE_URL=postgresql+psycopg://...`
- `TRUSTED_HOSTS=api.yourdomain.com`
- `ALLOWED_ORIGINS=https://app.yourdomain.com`

The app validates these values and fails fast on startup if unsafe production defaults are used.

## Security Controls Included

- API key enforcement for all non-health endpoints.
- Trusted host validation.
- Security headers (`nosniff`, `DENY`, referrer policy, permissions policy).
- Request rate limiting (per client/IP, in-memory process scope).
- Request ID propagation and process time headers.

## Reliability Controls Included

- Liveness and readiness endpoints:
  - `GET /api/v1/health/live`
  - `GET /api/v1/health/ready`
- Database pre-ping and pooled connections.
- Consistent JSON error format with request IDs.
- GZip response compression for larger payloads.

## Preflight

Run preflight before deployment:

```bash
cd backend
make preflight
```

## Production Run Example

```bash
cd backend
export ENVIRONMENT=prod
export ENABLE_DOCS=false
export REQUIRE_API_KEY=true
export API_KEY='replace-with-random-secret'
export AUTO_CREATE_SCHEMA=false
export DATABASE_URL='postgresql+psycopg://user:pass@db:5432/dattamsha'
export TRUSTED_HOSTS='api.company.com'
export ALLOWED_ORIGINS='https://app.company.com'

uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
```

## Remaining Enterprise Steps (Outside Codebase)

- Move API key to secret manager (AWS Secrets Manager / Vault).
- Add mTLS or OAuth2/JWT for user-level access control.
- Put API behind managed WAF + load balancer.
- Configure centralized logging and metrics retention.
- Replace in-memory rate limiting with Redis for distributed enforcement.
- Add migration workflow (Alembic) and deployment rollback automation.
