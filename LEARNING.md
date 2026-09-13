# Learning courses and results

The frontend opens Learning → subject. GET /learning/subjects/{subject_name} returns the user's saved level and the available course for it. If no level is saved, the frontend prompts once and PUTs the selection. Profile lists the same preferences and changes them through the same endpoint. Only levels with published coursework are selectable.

## Database ownership and migration

The configured app database is vchitr-main on the Neon development branch, not the project's default production branch. Check the configured endpoint before running a migration.

Existing modules schema belongs to neondb_owner; public.users belongs to admin. Before the initial migration, execute this narrow prerequisite as admin in the target database:

```sql
GRANT REFERENCES ON TABLE public.users TO neondb_owner;
```

Then, with the app's neondb_owner direct connection in DATABASE_URL_UNPOOLED, run from the repository root:

```text
python -m scripts.seed_learning
```

The app's configured runtime role is `admin`. After seeding, execute these scoped grants as `neondb_owner` in the same database, then run verification with the app's normal `DATABASE_URL`:

```sql
GRANT SELECT ON modules.learning_courses TO admin;
GRANT SELECT, INSERT, UPDATE, DELETE ON modules.learning_preferences, modules.learning_progress, modules.learning_attempts TO admin;
```

Keep migration credentials separate from runtime credentials. The runtime cannot edit the course bank through these grants.

```text
python -m scripts.verify_learning_db
```

The seed applies migrations/001_learning_courses.sql and publishes data/ncert-maths-10-v1.json in one transaction. It preserves existing rows and fails if an existing course version differs. Repeating it is safe. No migration runs automatically during application startup. No database credential belongs in source control.

Tables, all in modules:

- learning_courses: course ID, subject ID, level and a JSONB document containing the complete short lessons, worked examples, practice question banks and final questions. One published course per subject/level in this release.
- learning_preferences: user ID + subject ID → selected level.
- learning_progress: user ID + course ID → lesson read markers.
- learning_attempts: server UUID, user/course/test IDs, immutable question snapshot, saved answers, revision, server-computed score and timestamps. A partial unique index permits only one active draft for a user/course/test.

## API

All routes require the existing bearer authentication. User IDs are taken from the authenticated session. Successful responses use Cache-Control: no-store. Every material or test request reads PostgreSQL; there is no runtime file fallback.

| Method | Route under /learning | Behavior |
| --- | --- | --- |
| GET | /subjects/{name} | Subject, available levels and saved preference; Math/Maths/Mathematics aliases supported |
| GET | /preferences | Per-subject preferences for Profile |
| PUT | /subjects/{subject_id}/level | Save an available level; body: level |
| GET | /courses/{course_id} | Chapter headings and the user's progress/score history |
| GET | /courses/{course_id}/chapters/{chapter_id} | Lesson, example and practice count; no test keys |
| PUT | /courses/{course_id}/chapters/{chapter_id}/read | Mark lesson read |
| GET | /courses/{course_id}/tests/{test_id} | Test overview, current draft or latest result, history |
| POST | /courses/{course_id}/tests/{test_id}/attempts | Start/resume a draft; test_id is a chapter ID or final |
| PUT | /courses/{course_id}/attempts/{attempt_id}/draft | Save answers with current revision |
| POST | /courses/{course_id}/attempts/{attempt_id}/submit | Grade complete answers with current revision |
| POST | /courses/{course_id}/reset | Confirmed reset; body: confirm=true |

Question keys and explanations are excluded until submission. The server freezes questions when creating an attempt and grades that snapshot. Clients submit answer indexes, never scores. An identical retry of an already-submitted attempt returns its existing result; a different payload is rejected. Stale draft revisions return 409.

Attempt and reset writes lock the same user/course progress row. Reset deletes only that user's drafts and results for that course, invalidates stale attempt IDs and relocks the final test. Read markers, subject preferences, other users and other courses remain intact. Retakes keep history with separate latest/best scores. Changing level never deletes old course progress.

Final eligibility requires a submitted test for every distinct chapter, regardless of score. The server checks this when opening, starting and submitting the final. No browser-local results are imported as authoritative completion.

## Loading performance

PostgreSQL uses SQLAlchemy's QueuePool with 5 retained connections, up to 5 overflow connections, a 10-second checkout timeout, 5-minute recycling and pre-ping. Limits apply per worker/process; account for instance and worker counts when sizing Cloud Run. Normal requests continue using the configured pooled Neon URL. SQLite regression fixtures keep their own pool settings.

`GET /learning/subjects/{name}?include_course=true` returns the saved subject level plus the authenticated user's course overview and progress in one response. Omit the flag for the original response. This reads the database on every request; it does not cache coursework. Level listings select only course IDs and levels, without fetching the complete question bank.

The frontend shares session verification for 60 seconds in memory, preloads public subject metadata with a 30-second memory lifetime, and retains server authentication on all protected routes. Region alignment remains a deployment task: verify Cloud Run's actual DB endpoint, then place the backend near the database. No minimum-instance or region settings are changed by this patch.

Read-only local-to-Neon comparison on 13 September 2026 (four requests per mode): warm median 817 ms with NullPool versus 471 ms with connection reuse. This measures the connection/query path from the developer machine, not production end-to-end latency.

## Verification checks

```text
python -m unittest discover -s tests -v
```

Tests use SQLite without reaching the configured database. They cover preferences, level switching, missing/corrupt content, key redaction, snapshots, ownership, draft revision conflicts, grading, idempotent submission, distinct-chapter eligibility, retakes, resets and the 14-chapter/84-question seed.

For PostgreSQL checks, use an isolated Neon branch and the explicit seed/verification commands above. Deploy this backend before deploying the matching frontend. No LLM generation is implemented yet; a future generator can supply validated snapshots to the existing attempt lifecycle.
