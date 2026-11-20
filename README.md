# QS Intelligence USA

**The AI Commercial Operating System for Construction.**

QS Intelligence USA is a multi-tenant SaaS platform for American general contractors, construction managers,
owners, civil contractors and specialty trades. It connects estimating, procurement, contracts, payment
applications, cost control, forecasting and field operations — with an AI Commercial Director that drafts and
recommends, while authorised people approve.

> **Markets:** United States and United Kingdom (USD/GBP, imperial/metric, in-region hosting).
>
> **Status: Phase 1 complete; Phase 2 milestone 2.1 (cost codes, estimating, budgets) complete.** Identity, multi-tenancy with database-enforced isolation, RBAC,
> MFA, projects, company directory, document management, audit trail, design system and the first executive
> dashboard are built and tested. Commercial modules (estimating, budgets, commitments, change orders,
> forecasting…) follow in Phase 2. See [`docs/PROGRESS.md`](docs/PROGRESS.md).

## Repository layout

```
backend/                FastAPI modular monolith (Python 3.13)
  app/core/             config, DB + RLS context, security, money, errors, rate limiting
  app/domains/<domain>/ models · schemas · service · router per bounded context
  alembic/              migrations (alembic_helpers/ holds frozen per-revision SQL)
  tests/                pytest suites against real PostgreSQL (RLS active)
frontend/               Next.js 15 + React 19 + Tailwind 4 web app
  src/app/              routes: (auth) sign-in/registration, (app) authenticated product
  src/components/ui/    design-system primitives
  src/components/domain feature components (project form, documents panel…)
  e2e/                  Playwright end-to-end tests
infra/                  docker-compose for local dev, Postgres bootstrap
docs/                   architecture, requirements, schema, security, API, roadmap, decisions
.github/workflows/      CI (lint, unit/integration, build, e2e)
```

## Quick start (local, without Docker)

Prerequisites: Python 3.12+, Node 22, PostgreSQL 16 with `pgvector`, Redis 7.

```bash
# 1. Databases and roles (qs_owner = migrations, qs_app = runtime role subject to RLS)
PGUSER=postgres ./backend/scripts/bootstrap_db.sh qs_dev qs_test

# 2. API
cd backend
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
cp .env.example .env
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --reload --port 8000      # docs at http://localhost:8000/api/v1/docs

# 3. Web
cd ../frontend
npm ci
npm run dev                                               # http://localhost:3000
```

Open http://localhost:3000/register to create an organization.

### With Docker

```bash
docker compose -f infra/docker-compose.yml up --build
```

(The compose stack is provided for convenience; it has not yet been exercised in CI — see
[`docs/RISKS_AND_DEPENDENCIES.md`](docs/RISKS_AND_DEPENDENCIES.md).)

## Tests

```bash
cd backend  && .venv/bin/pytest -p no:warnings          # 122 tests: auth, RLS, RBAC, money, estimating, budgets…
cd frontend && npm run typecheck && npm test              # 23 unit/component tests
cd frontend && npx playwright test                        # 7 e2e tests (needs API on :8000 and web on :3000)
```

## Documentation

| Document | Purpose |
|---|---|
| [Product requirements](docs/PRODUCT_REQUIREMENTS.md) | Users, problems, scope, acceptance criteria |
| [Architecture](docs/ARCHITECTURE.md) | System design, domains, request lifecycle, deployment |
| [Database schema](docs/DATABASE_SCHEMA.md) | ER diagram, tables, RLS, money types, planned entities |
| [Security](docs/SECURITY.md) | Threat model, controls, NIST CSF 2.0 mapping |
| [AI architecture](docs/AI_ARCHITECTURE.md) | AI Commercial Director design (Phase 4) |
| [API specification](docs/API_SPECIFICATION.md) | Conventions + generated endpoint list and OpenAPI |
| [Development roadmap](docs/DEVELOPMENT_ROADMAP.md) | Phases 1–6 |
| [Testing strategy](docs/TESTING_STRATEGY.md) | Test pyramid, what is covered, how to run |
| [Decision log](docs/DECISION_LOG.md) | Architecture decision records |
| [Backlog](docs/BACKLOG.md) · [Progress](docs/PROGRESS.md) · [Outstanding decisions](docs/OUTSTANDING_DECISIONS.md) · [Risks](docs/RISKS_AND_DEPENDENCIES.md) | Project management |

## Engineering principles (abridged)

- Money is `Decimal`/`NUMERIC` end-to-end and travels as strings in JSON. No floats, ever.
- Every tenant-owned row is protected by PostgreSQL Row-Level Security **and** application checks.
- Every consequential change writes an append-only audit event with before/after values.
- AI may draft and recommend; authorised humans approve. AI output is always labelled as such.
- No placeholder features: unbuilt modules are shown as "Phase N", never as fake screens.
