# vCHITR backend

FastAPI + SQLAlchemy backend for the vCHITR learning platform. It provides account management (password and Google sign-in), user profiles with avatar upload, a module/subject catalogue, and a learning module that serves course content, runs tests, grades attempts and tracks progress per user. On top of the fixed Class 10 Maths course it offers adaptive practice (server-selected question sets driven by per-concept evidence, across all 14 chapters) and an optional pipeline that serves pre-generated Beginner/Advanced versions of each lesson.

## Quick start

Run the full application (Postgres 17, Flyway migrations, backend and the React frontend) with Docker. The [`vchitr-frontend`](../vchitr-frontend) repository must be cloned next to this one:

```bash
cp .env.docker.example .env.docker
docker compose up               # frontend http://localhost:5173 · API http://localhost:8000/docs
```

Step-by-step guide and troubleshooting: **[docs/local-runner.md](docs/local-runner.md)**. To run only the backend on your host instead, see [docs/06-development.md](docs/06-development.md).

Run the offline test suite (no database or network needed):

```bash
python -m unittest discover -s tests -v
```

## Stack

| Concern | Choice |
| --- | --- |
| Web framework | FastAPI 0.115 on Uvicorn |
| Validation / settings | Pydantic v2, pydantic-settings |
| Database | PostgreSQL 17 (Neon) via SQLAlchemy 2.0 + psycopg2; SQLite in tests |
| Migrations | Flyway (`db/migration`), applied to remote by GitHub Actions on merge to `master` |
| Auth | bcrypt password hashes, HS256 JWT bearer tokens, Google ID-token sign-in |
| Packaging | Docker (`python:3.11-slim`, port 8080); Docker Compose for local development |

## Documentation

New to FastAPI? Start with the first guide; it explains the framework's concepts using this project's own code.

| Document | Contents |
| --- | --- |
| [docs/local-runner.md](docs/local-runner.md) | Run the whole stack locally with Docker Compose; schema-change workflow; troubleshooting |
| [docs/01-fastapi-concepts.md](docs/01-fastapi-concepts.md) | Path operations, Pydantic schemas, dependency injection, routers, middleware, sync vs async, auto-generated docs |
| [docs/02-architecture.md](docs/02-architecture.md) | Repository layout, layers, how `main.py` composes the app, configuration, conventions |
| [docs/03-database.md](docs/03-database.md) | Engine/session setup, the two PostgreSQL schemas, all tables (incl. adaptive and content), concurrency controls, Flyway migrations and CI, SQLite in tests |
| [docs/04-authentication.md](docs/04-authentication.md) | Password storage, login flow, JWT format, protecting routes, Google sign-in |
| [docs/05-api-reference.md](docs/05-api-reference.md) | Every endpoint with request/response shapes and error codes |
| [docs/06-development.md](docs/06-development.md) | Setup, running, seeding, tests, Docker, common tasks, debugging |
| [docs/07-adaptive-learning.md](docs/07-adaptive-learning.md) | How adaptive practice and adapted lesson content work: policy, selection, depth, generation, serving |
| [LEARNING.md](LEARNING.md) | Deep dive on the learning module: data ownership, migration procedure, behavioural rules, performance notes |
| [ADAPTIVE.md](ADAPTIVE.md) | Adaptive practice runbook: schema V2, publishing banks, policy details, limits |
| [CLASS10_CONTENT.md](CLASS10_CONTENT.md) | Chapter-by-chapter adaptive coverage, source alignment, validation |
| [CONTENT_PIPELINE.md](CONTENT_PIPELINE.md) | Lesson generation runbook: providers, schema V3, rollout, cache identity |

## Layout at a glance

```
app/main.py        app factory: middleware, routers, static mount, /health
app/core/          config (env), database (engine/session), security (hashing, JWT)
app/models/        SQLAlchemy tables      → public.users, modules.*
app/schemas/       Pydantic request/response models
app/routers/       /auth  /profile  /module  /learning
app/services/      adaptive practice policy, lesson depth/lookup, lesson generation
data/              course document + 14 adaptive practice banks (JSON)
db/migration/      Flyway migrations V0–V3 (db/dev, db/init: local/CI only)
scripts/           seed/verify/build scripts, generate_content.py (operator only)
tests/             unittest suite on SQLite (56 tests, no network)
docker-compose.yaml  local stack: db → flyway → seed → api → web
```

## Environment variables

See `.env.example` for the full list. Required: `DATABASE_URL`, `JWT_SECRET`. Optional: `GOOGLE_CLIENT_ID`, `CORS_ORIGINS`, `CORS_ORIGIN_REGEX`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `UPLOADS_DIR`, `DATABASE_URL_UNPOOLED` (migration/seed scripts only), `CONTENT_PIPELINE_ENABLED` (default `false`), and the operator-only `CONTENT_PROVIDER`, `CONTENT_API_BASE_URL`, `CONTENT_API_KEY`, `CONTENT_MODEL`, `CONTENT_OUTPUT_MODE`. Details in [docs/02-architecture.md](docs/02-architecture.md#configuration).
