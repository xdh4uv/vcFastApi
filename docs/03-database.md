# Database

The app uses **PostgreSQL** (hosted on Neon) through **SQLAlchemy 2.0** with the synchronous `psycopg2` driver. Tests substitute an in-memory SQLite database. This document covers how the ORM is set up, what tables exist, how sessions and transactions work, and how schema changes are applied.

## 1. Engine, session, Base

Everything starts in [app/core/database.py](../app/core/database.py):

```python
engine = create_engine(settings.database_url, pool_pre_ping=True, **pool_options)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
```

| Object | Role |
| --- | --- |
| `engine` | One per process. Owns the connection pool. Created once at import. |
| `SessionLocal` | A factory. Calling `SessionLocal()` gives a new `Session`, the unit-of-work object you query and commit through. |
| `Base` | The parent class for every ORM model. `Base.metadata` collects every table defined by subclassing it. |

### Session per request

```python
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

Endpoints receive a session through `db: Session = Depends(get_db)`. One session is opened per request and closed when the response is done, returning its connection to the pool. Endpoints commit explicitly (`db.commit()`); nothing commits automatically. If an endpoint raises before committing, `close()` discards the uncommitted work.

`autoflush=False` means pending changes are sent to the database only on `commit()`, `flush()`, or when a query needs them. `autocommit=False` (the default and only supported mode in SQLAlchemy 2.0) means you are always inside a transaction.

### Connection pooling

```python
pool_options = {
    "pool_size": 5, "max_overflow": 5, "pool_timeout": 10,
    "pool_recycle": 300, "pool_use_lifo": True,
} if settings.database_url.startswith(("postgresql", "postgres:")) else {}
```

- Up to 5 connections are kept open, with 5 more allowed under burst (10 concurrent max). A request waits up to 10 s for a free connection, then fails.
- Connections are recycled after 5 minutes and pre-pinged before use, so a dropped server-side connection is replaced transparently.
- `pool_use_lifo=True` reuses the most recently returned connection, which keeps the working set of warm TLS connections small.
- These limits are **per process**. Running several Uvicorn workers multiplies them.
- SQLite (tests) gets no pool options; the test files configure their own engine.

## 2. Models

Models live in [app/models/](../app/models/). Each is a class that subclasses `Base`, names its table, and declares columns as class attributes.

```python
class User(Base):
    __tablename__ = "users"
    __table_args__ = {"schema": "public"}

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    ...
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
```

Notes on the column options you will see:

- `server_default=func.now()` – the database fills the value (`DEFAULT now()`). `default=lambda: datetime.now(timezone.utc)` – Python fills it before INSERT. Both patterns appear in the codebase.
- `onupdate=func.now()` – SQLAlchemy sets the column on every UPDATE it issues. This is not a DB trigger; direct SQL updates bypass it.
- `UUID(as_uuid=True)` – PostgreSQL-native UUID column, exposed as `uuid.UUID` in Python.
- `JSON().with_variant(JSONB, "postgresql")` – generic JSON type that becomes `JSONB` on PostgreSQL and plain JSON text on SQLite. This is what lets the same model run in tests.

### Two PostgreSQL schemas

Tables are split across two namespaces in the same database:

```mermaid
erDiagram
    users {
        int id PK
        string email UK
        string username UK
        string hashed_password "nullable (Google-only accounts)"
        string google_sub UK "nullable"
        string full_name
        date date_of_birth
        string gender
        text bio
        string phone_country_code
        string phone_number
        string avatar_url
        bool onboarding_completed
        timestamptz created_at
        timestamptz updated_at
    }
    modules_master {
        uuid module_id PK
        string module_name
        text module_description
        timestamptz created_at
    }
    sub_modules_master {
        uuid sub_module_id PK
        string sub_module_name
        text sub_module_description
        timestamptz created_at
    }
    learning_courses {
        string course_id PK
        uuid subject_id FK
        string level
        jsonb content
    }
    learning_preferences {
        int user_id PK_FK
        uuid subject_id PK_FK
        string level
    }
    learning_progress {
        int user_id PK_FK
        string course_id PK_FK
        jsonb read "list of chapter ids"
    }
    learning_attempts {
        uuid id PK
        int user_id FK
        string course_id FK
        string test_id "chapter id or 'final'"
        string kind "chapter | final | adaptive"
        jsonb selection_metadata "adaptive policy details"
        jsonb questions "frozen snapshot"
        jsonb answers
        int revision
        int correct
        int total
        timestamptz created_at
        timestamptz submitted_at "null while draft"
    }
    learning_concepts {
        string course_id PK_FK
        string chapter_id PK
        string concept_id PK
        jsonb material "revision card"
    }
    learning_practice_questions {
        string id PK
        string course_id FK
        string chapter_id FK
        string concept_id FK
        string difficulty "foundation | standard | challenge"
        string status "draft | approved"
        string source
        jsonb content
    }
    learning_content_generations {
        uuid id PK
        string course_id FK
        string chapter_id
        string tier "beginner | advanced"
        string source_hash
        string cache_key
        string prompt_version
        string provider
        string model
        string status "pending | ready | failed"
        jsonb content "validated lesson"
        bool verified
    }

    sub_modules_master ||--o{ learning_courses : "subject_id"
    sub_modules_master ||--o{ learning_preferences : "subject_id"
    users ||--o{ learning_preferences : "user_id"
    users ||--o{ learning_progress : "user_id"
    users ||--o{ learning_attempts : "user_id"
    learning_courses ||--o{ learning_progress : "course_id"
    learning_courses ||--o{ learning_attempts : "course_id"
    learning_courses ||--o{ learning_concepts : "course_id"
    learning_concepts ||--o{ learning_practice_questions : "course_id, chapter_id, concept_id"
    learning_courses ||--o{ learning_content_generations : "course_id"
```

| Schema | Tables | Managed by |
| --- | --- | --- |
| `public` | `users` | Flyway `V0` |
| `modules` | `modules_master`, `sub_modules_master` | Flyway `V0`. On remote these pre-date the repo; the app only reads them. |
| `modules` | `learning_courses`, `learning_preferences`, `learning_progress`, `learning_attempts` | Flyway `V1` |
| `modules` | `learning_concepts`, `learning_practice_questions` (+ `kind`, `selection_metadata` on `learning_attempts`) | Flyway `V2` |
| `modules` | `learning_content_generations` | Flyway `V3` |

`modules_master` and `sub_modules_master` are not linked by a foreign key in the models; they are independent lookup tables. `sub_modules_master` rows are the "subjects" (e.g. Maths) that the learning feature keys on.

Cross-schema foreign keys are written with the schema prefix: `ForeignKey("public.users.id")`, `ForeignKey("modules.sub_modules_master.sub_module_id")`.

**Import ordering matters for foreign keys.** `learningCourseModel.py` has

```python
from .subModuleMasterModel import SubModuleMaster  # Register the FK target.
```

SQLAlchemy resolves `ForeignKey("modules.sub_modules_master.sub_module_id")` by name at table-creation time, so the target table's model must have been imported (and therefore registered on `Base.metadata`) first.

## 3. Querying

The codebase uses the classic `Session.query` API plus a few 2.0-style helpers. Patterns you will see:

```python
# Primary-key lookup (works with composite keys as a tuple)
db.get(LearningCourse, course_id)
db.get(LearningPreference, (user.id, subject.sub_module_id))

# Filter and fetch one / all
db.query(User).filter(User.email == form_data.username).first()
db.query(ModuleMaster).all()

# Select specific columns instead of whole rows
db.query(LearningCourse.level, LearningCourse.course_id).filter_by(subject_id=...).all()

# Insert
db.add(user); db.commit(); db.refresh(user)   # refresh reloads server-generated columns (id, created_at)

# Update: mutate the attribute, then commit
user.full_name = payload.full_name
db.commit()

# Bulk delete without loading rows
db.query(LearningAttempt).filter_by(user_id=..., course_id=...).delete(synchronize_session=False)
```

`db.refresh(obj)` after a commit re-reads the row so that columns filled by the database (`id`, `created_at`, `updated_at`) are populated on the Python object before it is returned to the client.

## 4. Concurrency control in the learning module

The learning router has to cope with the same user acting from two devices. Three database-level tools are used; they are worth understanding because they are the non-obvious part of the schema.

**Row locks** (`SELECT ... FOR UPDATE`):

```python
db.query(User).filter_by(id=user.id).with_for_update().one()
```

Locks the user's row for the rest of the transaction. Any other transaction trying to lock the same row waits. `set_level` uses this to serialise preference writes; `lock_progress` does the same on the `learning_progress` row so that attempt creation, submission and reset for one user/course cannot interleave.

**Savepoints** (`begin_nested`):

```python
try:
    with db.begin_nested():
        db.add(LearningProgress(user_id=user_id, course_id=course_id, read=[]))
        db.flush()
except IntegrityError:
    pass  # Another request created the same row.
```

Inserting a row that might already exist would abort the whole transaction on a primary-key violation. Wrapping the insert in a savepoint means only the savepoint is rolled back, and the outer transaction carries on.

**Partial unique index**:

```sql
CREATE UNIQUE INDEX uq_learning_active_draft
    ON modules.learning_attempts(user_id, course_id, test_id, kind)
    WHERE submitted_at IS NULL;
```

Enforces "at most one unsubmitted draft per user/course/test/kind" while still allowing unlimited submitted attempts for retakes. Including `kind` (added by V2) lets a chapter test draft and an adaptive practice draft for the same chapter coexist. The model declares the same index with `postgresql_where=`/`sqlite_where=` so it exists in both databases.

**Optimistic concurrency** (`revision`): every draft save must include the revision the client last saw. A mismatch returns `409`, so a stale device cannot overwrite newer answers.

**Advisory locks** serialise the operator scripts rather than requests. `seed_adaptive.py` takes a transaction-scoped `pg_advisory_xact_lock` before publishing banks. `generate_content.py` holds a session advisory lock on its direct connection so only one lesson publisher runs at a time. The content table also has a partial unique index, `uq_content_active_key ON (cache_key) WHERE status IN ('pending','ready')`, so two publishers can never both start the same generation.

## 5. Schema changes and migrations

The whole schema is managed by **[Flyway](https://documentation.red-gate.com/fd)**. The app never creates or alters tables at startup.

```
db/
├── migration/                    # Versioned migrations: run everywhere, including remote
│   ├── V0__existing_tables.sql   # public.users, modules.modules_master, modules.sub_modules_master
│   ├── V1__learning_courses.sql  # courses, preferences, progress, attempts
│   ├── V2__adaptive_practice.sql # attempts.kind + selection_metadata, concepts, practice questions
│   └── V3__content_pipeline.sql  # learning_content_generations
├── dev/
│   └── R__dev_catalogue.sql      # Local/CI-only repeatable seed: the Maths subject row
└── init/
    └── 00-roles.sql              # Local/CI-only: creates the `admin` role that V2/V3 grant to
```

| Version | What it does |
| --- | --- |
| V0 | Tables that predate Flyway. `users` used to be created by `create_all`; the catalogue tables were created outside this repo. Reconstructed from the models, so it only ever runs on fresh databases. |
| V1 | Learning courses, preferences, progress and attempts, including the `CHECK` constraints the ORM does not know about. |
| V2 | Adds `kind` and `selection_metadata` to attempts, back-fills `kind='final'`, rebuilds the draft index with `kind`, creates `learning_concepts` and `learning_practice_questions`, grants `SELECT` to `admin`. |
| V3 | Additive: `learning_content_generations`, its indexes and a `SELECT` grant to `admin`. |
| V4 | Reading progress, engagement events and question timing. |
| V5 | Tutor conversations and saved Notes. |
| V6 | Enrollment backfill and aptitude profiles. |
| V7 | Corrects the reviewed elevation/depression justification, assigns revised question IDs and retires old questions from future selection while preserving snapshots. |

Flyway records applied versions in `public.flyway_schema_history` and checksums each file. Rules:

- **New change → new file**, `V<next>__<description>.sql`. Never edit, rename or delete a merged migration; the checksum check makes Flyway refuse to run.
- **Keep the model in sync.** SQLAlchemy models do not generate DDL. After adding a migration, update the matching class in `app/models/`. The SQL files are the source of truth for the PostgreSQL schema.
- **Backward compatible.** Remote migrations run before the new backend is deployed, so the currently running backend must keep working with the new schema: add nullable columns and new tables first, and remove old ones in a later release.
- **Data fixtures for developers go in `db/dev/`**, never in `db/migration/`.

### Where migrations run

| Environment | How | Locations |
| --- | --- | --- |
| Local | `flyway` service in `docker-compose.yaml`, on every `docker compose up` | `db/migration` + `db/dev` |
| CI (pull requests and `master`) | `verify` job in `.github/workflows/db-migrate.yml`: empty Postgres 17 → all migrations → publish course and banks → verify | `db/migration` + `db/dev` |
| Remote (Neon) | `migrate` job in the same workflow, only on pushes to `master`, after `verify` passes | `db/migration` only |

The remote job requires repository variable `DATABASE_MIGRATIONS_ENABLED=true` and secrets `NEON_FLYWAY_URL` (JDBC URL of the **direct**, non-`-pooler` host, with `?sslmode=require`), `NEON_FLYWAY_USER` and `NEON_FLYWAY_PASSWORD` (the schema owner). It refuses a pooler URL and runs `info`, `migrate`, `info`. Verification and regressions still run when remote migrations are disabled. Runs are serialised; the `production` environment can have a required reviewer.

### One-time: baseline the remote database

Never assume an existing database is at V3. On 2 October 2026, `vchitr-main` on the `development` Neon branch had V1/V2 but no V3 or Flyway history. Its V1/V2 columns, defaults, constraints, indexes and runtime grants were audited against migrations replayed into a fresh PostgreSQL 17 reference. Only then was it baselined at version 2 and migrated through V6. The procedure was rehearsed on a fresh Neon clone; existing user/course/attempt data fingerprints were unchanged on both targets.

For another unmanaged database, determine its real schema version and use that audited version. Example for the audited V2 state, with credentials supplied through environment variables:

```bash
docker run --rm -v "$PWD/db/migration:/flyway/sql:ro,z" \
  -e FLYWAY_URL -e FLYWAY_USER -e FLYWAY_PASSWORD \
  flyway/flyway:11 baseline -baselineVersion=2 -baselineDescription="audited V1-V2 schema"
```

Baseline excludes migrations at or below its version; the V2 baseline allows V3 onwards to run. Do not baseline at 3 if V3 is absent. Do not rerun baseline on a managed database or repair checksums to hide drift. The workflow leaves `baselineOnMigrate` disabled. [Flyway baseline reference](https://documentation.red-gate.com/flyway/reference/commands/baseline).

The migration owner also needs `CREATE` on `public` for history and `CREATE` on `modules` for feature tables. On this app database, its existing database owner granted `USAGE, CREATE ON SCHEMA public TO neondb_owner` after rehearsal; the migration owner already held module-create and user-reference privileges. Runtime role `admin` remains read-only on generated content.

Audit legacy schema drift separately. Never edit an already-applied migration to reconcile it; use a new versioned migration when necessary.

### Scripts and DDL

The seed scripts pre-date Flyway and can still apply their migration file. On a Flyway-managed database, always use the content-only mode:

| Script | Flyway-era usage |
| --- | --- |
| `scripts.seed_learning` | `--content-only`: publish `data/ncert-maths-10-v1.json` without running V1 |
| `scripts.seed_adaptive` | `--bank all --content-only`: publish all practice banks without running V2 |
| `scripts.generate_content` | Omit `--migrate` / `--migrate-only`; V3 is applied by Flyway |

Database roles and grants are described in [LEARNING.md](../LEARNING.md#database-ownership-and-migration). The historical rollout notes for V2 and V3 are in [ADAPTIVE.md](../ADAPTIVE.md) and [CONTENT_PIPELINE.md](../CONTENT_PIPELINE.md).

## 6. Course content as a JSON document

`learning_courses.content` stores the whole course (chapters, lessons, question banks, answers) as one JSONB document rather than normalised tables. The shape is defined by the Pydantic `Course` model in [app/schemas/learning.py](../app/schemas/learning.py); `load_course` validates the stored document against it on every read and returns 503 if it does not match. The same model validates `data/ncert-maths-10-v1.json` before seeding, so the file, the database and the API all agree on one schema.

Attempts copy the questions into `learning_attempts.questions` when created. Grading uses that snapshot, so republishing a course never changes the score of an existing attempt.

The adaptive tables follow the same idea at a finer grain. Each `learning_concepts.material` row is one revision card and each `learning_practice_questions.content` row is one question, both validated by the Pydantic models in [app/schemas/adaptive.py](../app/schemas/adaptive.py). Published question documents are treated as immutable: re-running the seed with a changed document fails rather than overwriting it, so a corrected question gets a new ID. Adaptive attempts snapshot their selected questions and store the selection policy details in `selection_metadata`.

`learning_content_generations` stores one row per generated lesson, including the source snapshot it was generated from, `source_hash`, prompt version, provider/model, provider usage, raw response and the validated `content`. Failed rows are kept for diagnosis. See [07 – Adaptive Learning](07-adaptive-learning.md#3-adapted-lesson-content).

## 7. How tests use SQLite

The tests never touch PostgreSQL. `tests/test_auth.py` builds an engine with:

```python
create_engine("sqlite://", ..., execution_options={"schema_translate_map": {"public": None}})
```

`schema_translate_map` rewrites `public.users` to plain `users` because SQLite has no schemas. `test_learning.py` extends the map with `"modules": None`; the adaptive and content test files reuse its setup (`import test_learning as baseline`). A couple of PostgreSQL-isms need manual patching (the quoted boolean default on `onboarding_completed`), and `JSONB`/`UUID` columns fall back to their generic variants. Everything else in the models runs unchanged.

Tests call router functions directly (`auth.signup(UserCreate(...), self.db)`) instead of going through HTTP, passing the session explicitly in place of the `Depends(get_db)` default. That keeps them fast and free of network setup, at the cost of not exercising request parsing, dependency resolution, or middleware. See [06 – Development](06-development.md#tests).

Next: [04 – Authentication](04-authentication.md).
