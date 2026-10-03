# vCHITR backend

FastAPI backend for NCERT Class 10 maths. Courses, approved question banks, preferences, test snapshots, results, reading activity, tutor conversations and saved notes live in PostgreSQL. All 14 chapters support focused practice. Chapter tests match server-selected learning depth when enabled; final eligibility requires every chapter test.

## Run

```bash
python -m venv .venv
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Set `DATABASE_URL` and `JWT_SECRET`; apply Flyway migrations before running. Runtime uses the pooled `vchitr_runtime` connection. Migrations and reviewed-content publication use a direct schema-owner connection. For the full local stack, follow [Docker instructions](docs/local-runner.md).

```bash
python -m unittest discover -s tests
```

## Features and flags

| Flag | Behavior |
| --- | --- |
| `ENGAGEMENT_ENABLED` | Enrollment, reading/timing events, learning profiles, tutor history and Notes |
| `TUTOR_ENABLED` | Live chapter-focused tutor answers |
| `CONTENT_PIPELINE_ENABLED` | Current, explicitly reviewed adapted explanations |
| `AUTOMATIC_LESSONS_ENABLED` | Request-time generation of missing Beginner/Advanced drafts; requires pipeline, engagement, V9 and limited runtime credentials |
| `TIERED_TESTS_ENABLED` | Five approved chapter questions at Foundation/Standard/Challenge difficulty |

Flags default off. Education level remains a subject preference. Explanation depth uses reliable chapter results first, eligible course-profile evidence next, otherwise Default. Existing attempts preserve their question snapshots through tier changes. Retakes retain last/best scores and history until a user resets results.

Automatic generation is direct HTTP, with no separate worker. It persists a generation identity before inference, reuses matching drafts, limits requests, applies quota cooldown and recovers interrupted requests. Unreviewed drafts are never served as lessons. Default/authored lessons remain available. Provider credentials are backend-only; adapters support OpenAI-compatible providers and Anthropic.

## Operational documentation

- [Development and provider setup](docs/06-development.md)
- [Database, migrations and runtime permissions](docs/03-database.md)
- [HTTP API reference](docs/05-api-reference.md) and running `/docs`
- [Local Docker stack](docs/local-runner.md)

Production Cloud Run activation remains deferred. Nightly recomputation needs its GitHub variable/secrets configured; pilot outcome targets require real user measurements.
