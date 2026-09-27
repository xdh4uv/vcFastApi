# Development Guide

> **Just want to run the app?** Use Docker Compose. It starts the database, migrations, backend and frontend with one command, and needs no local Python, Node or PostgreSQL. See **[Running vCHITR Locally](local-runner.md)**. The rest of this page covers running the backend directly on your host, which is useful for debuggers and IDE integration.

## Prerequisites

- **Python 3.11 or 3.12.** The Dockerfile uses 3.11 and the pinned dependency versions in `requirements.txt` are known to install cleanly there. Newer interpreters may lack prebuilt wheels for some pinned packages.
- **PostgreSQL 17** reachable via a connection string, for running the real app. Not needed for the test suite. The simplest option is the Compose database: `docker compose up -d db flyway seed` gives you a migrated, seeded database on `localhost:5432` (user/password/db `vchitr`).

## First-time setup

```bash
# 1. Create and activate a virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
#    then edit .env: at minimum set DATABASE_URL and a real JWT_SECRET
#    (for the Compose database: DATABASE_URL=postgresql://vchitr:vchitr@localhost:5432/vchitr)
```

`.env` is git-ignored. Never commit real credentials.

## Running the server

```bash
uvicorn app.main:app --reload
```

- Serves on `http://127.0.0.1:8000`.
- `--reload` restarts on file changes (development only).
- The app does **not** create any tables. The database must already be migrated by Flyway (see below).

Open `http://127.0.0.1:8000/docs` to browse and call the API.

### Preparing a database

1. **Schema: Flyway.** Every table comes from `db/migration/`. With Compose, `docker compose up flyway` applies them to the Compose database. For any other empty database, run the Flyway container against it, including `db/dev` for the local `Maths` subject row:

```bash
psql "$DATABASE_URL" -f db/init/00-roles.sql      # the `admin` role V2/V3 grant to
docker run --rm --network host \
  -v "$PWD/db/migration:/flyway/sql:ro,z" -v "$PWD/db/dev:/flyway/dev:ro,z" \
  -e FLYWAY_URL=jdbc:postgresql://localhost:5432/<db> -e FLYWAY_USER=<user> -e FLYWAY_PASSWORD=<password> \
  -e FLYWAY_LOCATIONS=filesystem:/flyway/sql,filesystem:/flyway/dev \
  flyway/flyway:11 migrate
```

2. **Course content.** Publish the course and the 14 practice banks:

```bash
python -m scripts.seed_learning --content-only
python -m scripts.seed_adaptive --bank all --content-only
python -m scripts.verify_learning_db
python -m scripts.verify_adaptive_db --bank all
```

`seed_adaptive` requires `DATABASE_URL_UNPOOLED`, and `seed_learning` uses it when set, falling back to `DATABASE_URL`. It must be a direct, non-`-pooler` host; for a local database, set it to the same value as `DATABASE_URL`. Re-running is safe: a published course or question whose stored document differs from the file makes the seed fail instead of overwriting it. To regenerate the JSON banks after editing a builder, run `python -m scripts.build_class10_banks` (chapters 3–14), `build_polynomials_bank` or `build_real_numbers_bank`, then run the tests before publishing. Details: [ADAPTIVE.md](../ADAPTIVE.md), [CLASS10_CONTENT.md](../CLASS10_CONTENT.md).

3. **Adapted lessons** (optional; leave `CONTENT_PIPELINE_ENABLED=false` otherwise). With V3 applied by Flyway, inspect the source, then generate:

```bash
python -m scripts.generate_content --chapter all --tier both --dry-run
python -m scripts.generate_content --chapter ch-01 --tier beginner --max-generations 1
```

`generate_content` needs `DATABASE_URL_UNPOOLED` and the `CONTENT_*` provider variables. Each run makes at most `--max-generations` provider calls (default 1; 28 covers every chapter at both depths), reuses matching generations and stops at the first failure. After a crash, `--recover-pending` marks interrupted jobs failed. Full rollout procedure: [CONTENT_PIPELINE.md](../CONTENT_PIPELINE.md).

## Tests

```bash
python -m unittest discover -s tests -v
# or, without a local virtualenv:
docker compose exec api python -m unittest discover -s tests
```

- Uses the standard-library `unittest` runner; no pytest.
- **Runs entirely offline.** Each test file sets `DATABASE_URL=sqlite://` before importing `app`, builds an in-memory SQLite engine, and mocks the Google token verifier. No `.env` is needed.
- Tests call router functions directly with an explicit `db=` session rather than sending HTTP requests. This means they exercise business logic and database behaviour but not request parsing, `Depends` resolution or middleware. If you want end-to-end HTTP tests, FastAPI's `TestClient` (from `fastapi.testclient`, requires the `httpx` package) can call the app in-process; you would override `get_db` with `app.dependency_overrides[get_db] = lambda: test_session`.
- `tests/test_learning.py` imports `create_test_engine` from `test_auth`, so run tests from the repository root with the discover command above (which puts `tests/` on the import path) rather than by invoking files individually from elsewhere.

- The adaptive and content test files reuse `test_learning.py`'s setup (`import test_learning as baseline`) and import from `scripts/`, so they also rely on running from the repository root.
- `test_content.py` mocks the provider HTTP call; no model is ever contacted.

| File | Tests | Covers |
| --- | --- | --- |
| `test_auth.py` | 8 | Signup/login/Google linking, onboarding and profile validation, avatar rules |
| `test_learning.py` | 13 | Preferences, level switching, course loading, corrupt content, answer redaction, snapshots, ownership, revision conflicts, grading, idempotent submit, final eligibility, retakes, resets, seeded course counts |
| `test_adaptive.py` | 13 | First-answer evidence, difficulty transitions, draft uniqueness, fresh-set exhaustion and labelled revision, short sets, unpublished/corrupt banks, isolation from official history |
| `test_polynomials.py` | 4 | Polynomials bank shape and independent answer keys |
| `test_class10_adaptive.py` | 5 | Chapters 3–14: label coverage, ID uniqueness, 45 questions per chapter, generated artifacts match builders, answer keys (`class10_answer_keys.py`), end-to-end flow |
| `test_content.py` | 13 | Source redaction, persistence before generation, cache reuse/invalidation, pending de-duplication, refusals/truncation, provider request contracts, result-derived depth, cross-user isolation, reset, disabled rollout |

56 tests in total.

## Docker

```bash
docker build -t vcfastapi .
docker run --rm -p 8080:8080 --env-file .env vcfastapi
```

The image installs `requirements.txt`, copies the source, and runs Uvicorn on port 8080 with a single worker. `.dockerignore` excludes `.env`, `uploads/` and `.git`, so configuration must be supplied at runtime with `--env-file` or `-e`.

Avatar uploads are written to `UPLOADS_DIR` (default `uploads/` inside the container) and are lost when the container is replaced. Mount a volume and point `UPLOADS_DIR` at it, or move avatar storage to object storage, before relying on it in production.

## Common tasks

### Add an endpoint to an existing feature

1. If it accepts a body, add a Pydantic model to the relevant file in `app/schemas/`.
2. Add a decorated function to the router in `app/routers/`. Declare `db: Session = Depends(get_db)` if it touches the database and `user: User = Depends(get_current_user)` if it needs authentication.
3. Set `response_model=` so the response is typed and filtered.
4. Add a test in `tests/` calling the function directly, following the existing style.

### Add a new feature area

1. Create `app/models/<name>.py`, `app/schemas/<name>.py`, `app/routers/<name>.py`.
2. In the router: `router = APIRouter(prefix="/<name>", tags=["<name>"])`.
3. Register in `app/main.py`: `app.include_router(<name>.router)`.
4. Add the tables as the next Flyway migration, `db/migration/V<next>__<name>.sql`, and apply it with `docker compose up flyway`. CI applies it to remote after merge; see [03 – Database](03-database.md#5-schema-changes-and-migrations).
5. If the logic is large or shared with a script, put it in `app/services/<name>.py` and call it from the router.

### Change the schema (e.g. add a column to `users`)

1. Add `db/migration/V<next>__<description>.sql` with the DDL, for example `ALTER TABLE public.users ADD COLUMN timezone VARCHAR(64);`. Never edit an existing migration.
2. Run `docker compose up flyway` and check the table in `psql`.
3. Add the matching `Column` to the model in `app/models/`.
4. Open a PR. CI replays all migrations on a fresh database; merging to `master` applies the new one to remote.

Keep it compatible with the currently deployed backend (see [local-runner.md](local-runner.md#6-changing-the-database-schema)).

### Change a setting

Add a typed attribute to `Settings` in `app/core/config.py`, document it in `.env.example`, and read it via `settings.<name>`.

## Debugging tips

- **Startup fails with a validation error mentioning `database_url` or `jwt_secret`** → the `.env` file is missing or not in the current working directory. Uvicorn must be run from the repository root.
- **`401 Could not validate credentials` on every protected call** → token expired, wrong `JWT_SECRET` between the process that issued and the one verifying, or the header is not exactly `Authorization: Bearer <token>`.
- **`422` on `POST /auth/login`** → the body was sent as JSON. It must be form-encoded (`username=...&password=...`).
- **`503 Learning is temporarily unavailable`** → a database exception occurred inside a learning endpoint; check the server log for the underlying SQLAlchemy error. Often a missing `modules.*` table or missing grant.
- **`404 This course has not been published yet`** → `learning_courses` is empty for that id; run the seed.
- **`404 Focused practice is not published for this chapter yet`** → no rows in `learning_concepts` for that chapter; run `scripts.seed_adaptive` for its bank.
- **`contentVariant` is always `null`** → `CONTENT_PIPELINE_ENABLED` is false. **`status: "unavailable"`** → no ready generation matches the current source hash and `PROMPT_VERSION`; run `scripts.generate_content` for that chapter and tier.
- **`410` from `/learning/content/{id}`** → the chapter or its revision cards changed, or `PROMPT_VERSION` was bumped, after that lesson was generated. Regenerate.
- **Changes to a model do not appear in the database** → models never create or alter tables; add a Flyway migration in `db/migration/`.
- **`relation "public.users" does not exist`** (or any other table) → the database has not been migrated. Run Flyway (`docker compose up flyway`).
- Set `--log-level debug` on Uvicorn, or `echo=True` on `create_engine`, to see SQL statements.

## Dependency overview

| Package | Purpose |
| --- | --- |
| `fastapi` | Web framework |
| `uvicorn[standard]` | ASGI server |
| `sqlalchemy` | ORM and connection pooling |
| `psycopg2-binary` | PostgreSQL driver |
| `pydantic`, `pydantic-settings` | Validation; settings from environment |
| `passlib`, `bcrypt` | Password hashing (versions pinned together; see [04 – Authentication](04-authentication.md#2-password-storage)) |
| `python-jose[cryptography]` | JWT encode/decode |
| `python-multipart` | Form and file-upload parsing |
| `python-dotenv` | `.env` loading in the scripts (`pydantic-settings` handles it for the app) |
| `email-validator` | Backs Pydantic's `EmailStr` |
| `google-auth`, `requests` | Verifying Google ID tokens; `requests` also makes the lesson-generation provider calls |

Next: [07 – Adaptive Learning](07-adaptive-learning.md).
