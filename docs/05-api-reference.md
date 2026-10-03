# API Reference

Base URL in local development: `http://localhost:8000` (or `:8080` in Docker). Interactive documentation with live "try it" is at `/docs`; this page is the human-readable summary.

Conventions:

- Request and response bodies are JSON unless stated.
- **Auth: Bearer** means the request must carry `Authorization: Bearer <token>`; missing/invalid tokens return `401 {"detail": "Could not validate credentials"}`.
- Validation failures on any body/path/query parameter return `422` with a `detail` array describing each problem.
- Error responses have the shape `{"detail": "<message>"}`.

## Health

### `GET /health`
Auth: none. Returns `{"status": "ok"}`. Use for load-balancer / uptime probes. Does not touch the database.

## Auth — `/auth`

### `POST /auth/signup`
Auth: none. Create a password account.

Request:
```json
{"email": "a@example.com", "username": "alice", "password": "at-least-8-chars"}
```
Constraints: valid email; username 3–64 chars; password 8–128 chars.

Response `201`:
```json
{"id": 1, "email": "a@example.com", "username": "alice", "created_at": "2026-09-14T10:00:00Z"}
```
Errors: `409` email or username already registered.

### `POST /auth/login`
Auth: none. Exchange credentials for a token. **Body is `application/x-www-form-urlencoded`**, not JSON:

```
username=a@example.com&password=...
```
The `username` field carries the **email**.

Response `200`: `{"access_token": "<jwt>", "token_type": "bearer"}`
Errors: `401` invalid credentials (also returned for Google-only accounts with no password).

### `POST /auth/google`
Auth: none. Sign in or register with a Google ID token.

Request: `{"credential": "<Google ID token from the browser SDK>"}`
Response `200`: same `Token` shape as login.
Errors: `503` Google sign-in not configured; `401` invalid credential or unverified Google email.

### `GET /auth/me`
Auth: Bearer. Returns the caller's basic account record (same shape as the signup response).

## Profile — `/profile`

Response shape used by every profile endpoint (`ProfileOut`):

```json
{
  "id": 1,
  "email": "a@example.com",
  "username": "alice",
  "full_name": "Alice Example",
  "date_of_birth": "2000-01-31",
  "age": 26,
  "gender": "Female",
  "bio": null,
  "phone_country_code": "+91",
  "phone_number": "9876543210",
  "avatar_url": "/uploads/avatars/1_5f3c....png",
  "initials": "AE",
  "onboarding_completed": true,
  "created_at": "2026-09-14T10:00:00Z",
  "updated_at": "2026-09-14T10:05:00Z"
}
```
`age` and `initials` are computed on the server; `avatar_url` is a relative path served by the static mount.

### `GET /profile/country-codes`
Auth: none. Returns the static list `[{"name": "India", "iso": "IN", "dial_code": "+91"}, ...]` for populating a phone-prefix picker.

### `GET /profile/me`
Auth: Bearer. Returns the caller's full profile.

### `POST /profile/onboarding`
Auth: Bearer. One-time profile completion.

Request:
```json
{
  "full_name": "Alice Example",
  "date_of_birth": "2000-01-31",
  "gender": "Female",
  "bio": "optional, ≤500 chars",
  "phone_country_code": "+91",
  "phone_number": "9876543210"
}
```
Rules: `gender` ∈ `Female | Male | Nonbinary | Prefer not to say | Other`; `date_of_birth` not in the future and not more than 120 years ago; `phone_country_code` must be in the known dial-code list; phone code and number must be both present or both absent.

Response `200`: `ProfileOut` with `onboarding_completed: true`.
Errors: `409` onboarding already completed (use PATCH instead); `422` validation.

### `PATCH /profile/me`
Auth: Bearer. Partial update. Any subset of:

```json
{"username": "...", "full_name": "...", "date_of_birth": "...", "gender": "...", "bio": "...", "phone_country_code": "...", "phone_number": "..."}
```
Only fields present in the body are changed. Sending `"bio": null` clears the bio; omitting `bio` leaves it alone.

Response `200`: `ProfileOut`.
Errors: `400` empty body, or phone code/number no longer form a complete pair after the update; `409` username taken; `422` validation.

### `POST /profile/me/avatar`
Auth: Bearer. **Body is `multipart/form-data`** with one field named `file`.

Rules: content type `image/png`, `image/jpeg` or `image/webp`; size 1 byte – 2 MB. The previous avatar file is deleted from disk.

Response `200`: `ProfileOut` with the new `avatar_url`.
Errors: `415` unsupported type; `400` empty file; `413` over 2 MB.

### `DELETE /profile/me/avatar`
Auth: Bearer. Removes the avatar file and clears `avatar_url`. Response `200`: `ProfileOut`.

## Module catalogue — `/module`

Both endpoints are **unauthenticated** and return raw table rows.

### `GET /module/getModules/`
```json
[{"module_id": "uuid", "module_name": "...", "module_description": "...", "created_at": "..."}]
```

### `GET /module/getSubModules/`
```json
[{"sub_module_id": "uuid", "sub_module_name": "Maths", "sub_module_description": "...", "created_at": "..."}]
```
Sub-modules are the *subjects* referenced by the learning API. Note the trailing slash in both paths.

## Learning — `/learning`

Auth: Bearer on **every** route. Every response carries `Cache-Control: no-store`. Any database failure returns `503 "Learning is temporarily unavailable. Please retry."`. JSON keys are camelCase. Full behavioural rules are in [Backend guide](../README.md); the adaptive practice policy and lesson-depth rules are summarised in [Backend guide](../README.md).

Shared response fragments:

**SubjectView**
```json
{
  "subjectId": "uuid",
  "subjectName": "Maths",
  "selectedLevel": "high-school",
  "courseId": "ncert-maths-10-v1",
  "levels": [{"id": "high-school", "title": "High school", "description": "Class 10 · NCERT", "available": true}, ...]
}
```
`selectedLevel` and `courseId` are `null` until the user picks a level. `available` is true only when a course is published for that level.

**ProgressView**
```json
{"read": ["ch-01", "ch-03"], "history": [AttemptSummary, ...], "finalUnlocked": false}
```

**AttemptSummary**
```json
{"id": "uuid", "testId": "ch-01", "kind": "chapter", "selection": {}, "submittedAt": "...", "correct": 5, "total": 6, "percent": 83}
```
`kind` is `chapter`, `final` or `adaptive`. `selection` is `{}` for chapter/final attempts; for adaptive attempts it is the selection metadata (see **PracticeSelection**). `ProgressView.history` and test `history` only ever contain `chapter`/`final` attempts.

**AttemptView** — a draft or submitted attempt
```json
{
  "id": "uuid", "testId": "ch-01", "kind": "chapter", "selection": {}, "revision": 3,
  "answers": {"q-01-1": 2, "q-01-2": 0},
  "submittedAt": null,
  "questions": [{"id": "...", "concept": "...", "difficulty": "standard", "prompt": "...", "options": ["a","b","c","d"]}]
}
```
While unsubmitted, each question omits `answer` and `explanation`. After submission the full questions (including `answer` and `explanation`) and the `AttemptSummary` fields are included. Adaptive questions additionally carry `conceptId`.

**Insights** — per-concept evidence for one chapter
```json
{
  "chapterId": "ch-01",
  "policyVersion": "concept-practice-v1",
  "concepts": [{
    "id": "prime-factorisation", "title": "...", "explanation": "...",
    "example": {"problem": "...", "steps": ["..."]}, "commonMistake": "...", "checklist": ["..."],
    "evidenceCount": 4, "correct": 2, "percent": 50,
    "status": "revise", "priority": 0, "nextDifficulty": "foundation"
  }]
}
```
`status` is `insufficient` (< 3 answers), `revise` (< 60%), `practise` (< 80%) or `positive`. Concepts are sorted by `priority` (0 = revise first). `nextDifficulty` is `foundation`, `standard` or `challenge`.

**PracticeSelection** — stored on each adaptive attempt as `selection`
```json
{"policyVersion": "concept-practice-v1", "focusConcepts": ["..."], "difficultyMix": {"foundation": 3, "standard": 2},
 "repeatedQuestionIds": [], "freshCount": 5, "mode": "fresh"}
```
`mode` becomes `revision` once the chapter's bank is exhausted and questions are repeated; repeated questions do not count as new evidence.

### `GET /learning/subjects/{subject_name}`
Look up a subject by name (case-insensitive; `math`, `maths`, `mathematics` are aliases). Query `include_course=true` additionally embeds the course overview (see `GET /courses/{id}`) under `course`, or `null` if no level is selected.
Response: `SubjectView`. Errors: `404` subject not found.

### `GET /learning/preferences`
All subjects with the caller's saved level for each. Response: `[SubjectView, ...]` ordered by subject name.

### `PUT /learning/subjects/{subject_id}/level`
Save the caller's level for a subject. `subject_id` is the sub-module UUID.
Request: `{"level": "high-school"}`
Response: `SubjectView`. Errors: `404` subject not found; `422` no course published for that level.

### `GET /learning/courses/{course_id}`
Course outline plus the caller's progress.
```json
{"id": "ncert-maths-10-v1", "title": "Class 10 Mathematics", "chapters": [{"id": "ch-01", "title": "Real Numbers"}, ...], "progress": ProgressView}
```
Errors: `404` course not published; `503` stored course document fails validation.

### `GET /learning/courses/{course_id}/chapters/{chapter_id}`
Lesson content for one chapter. Practice questions are **not** included, only the count.
```json
{
  "id": "ch-01", "title": "...", "goal": "...", "concepts": ["..."],
  "example": {"problem": "...", "steps": ["..."]}, "watchFor": "...", "questionCount": 6,
  "adaptiveAvailable": true,
  "contentVariant": ContentVariant | null
}
```
`adaptiveAvailable` is true when revision concepts are published for this chapter. `contentVariant` is `null` unless `CONTENT_PIPELINE_ENABLED=true`; then it is:
```json
{
  "requestedTier": "beginner", "servedTier": "beginner", "status": "ready",
  "generationId": "uuid", "verified": false,
  "generated": {"summary": "...", "sections": [{"title": "...", "explanation": ["..."], "example": {"problem": "...", "steps": ["..."]}, "checkYourself": "..."}], "takeaways": ["..."]},
  "selection": {"tier": "beginner", "evidenceCount": 12, "percent": 42, "reason": "chapter-results"}
}
```
`status` is `base` (default depth; show the original lesson), `ready` (serve `generated`) or `unavailable` (no valid stored lesson for this depth; fall back to the original). The tier is chosen on the server from the caller's results; the client cannot request one.
Errors: `404` course or chapter not found.

### `PUT /learning/courses/{course_id}/chapters/{chapter_id}/read`
Mark a chapter as read. No body. Response: `ProgressView`.

### `GET /learning/courses/{course_id}/tests/{test_id}`
Test overview. `test_id` is a chapter id (`ch-01`) or the literal `final`.
```json
{"testId": "ch-01", "title": "Real Numbers · Practice", "questionCount": 6, "attempt": AttemptView | null, "history": [AttemptSummary, ...]}
```
`attempt` is the current draft if one exists, else the most recent submitted attempt, else `null`. Adaptive attempts are excluded. The response also has `adaptiveAvailable`, and `insights` (an **Insights** object) when adaptive content exists, the chapter test has at least one submitted attempt and no chapter draft is open; otherwise `insights` is `null`.
Errors: `403` final test requested before every chapter test has been submitted (adaptive practice never counts towards this); `404` unknown chapter.

### `POST /learning/courses/{course_id}/tests/{test_id}/attempts`
Start a new draft, or return the existing unsubmitted draft. Freezes the question set into the attempt. No body.
Response: `AttemptView`. Errors: `403` final locked; `404`.

### `PUT /learning/courses/{course_id}/attempts/{attempt_id}/draft`
Save partial answers.
Request: `{"answers": {"q-01-1": 2}, "revision": 3}` — `revision` must equal the attempt's current revision.
Response: `AttemptView` with `revision` incremented.
Errors: `404` attempt not owned / not found (possibly reset); `409` already submitted, or revision mismatch; `422` unknown question id or option index out of range.

### `POST /learning/courses/{course_id}/attempts/{attempt_id}/submit`
Grade the attempt. Same body as draft, but every question must be answered.
Response: `AttemptView` with `submittedAt`, `correct`, `total`, `percent` and full questions. For an adaptive attempt the response also includes updated `insights`.
The draft and submit endpoints serve chapter, final and adaptive attempts alike.
Idempotent: resubmitting identical answers to an already-submitted attempt returns the existing result; different answers return `409`.
Errors: `403` final locked; `409` revision mismatch / already submitted with different answers; `422` incomplete or invalid answers.

### `POST /learning/courses/{course_id}/reset`
Delete all of the caller's attempts (drafts and results, chapter, final and adaptive) for this course. This also clears the derived concept evidence and explanation depth. Read markers and level preference are kept.
Request: `{"confirm": true}` (must be literally `true`).
Response: `ProgressView`.

### `GET /learning/courses/{course_id}/chapters/{chapter_id}/insights`
Revision cards plus the caller's per-concept evidence and next difficulty.
Response: **Insights**. Errors: `404` course/chapter not found, or focused practice not published for this chapter; `503` stored revision material fails validation.

### `GET /learning/courses/{course_id}/chapters/{chapter_id}/practice`
Adaptive practice overview. Never creates an attempt.
```json
{"testId": "ch-01", "kind": "adaptive", "title": "Real Numbers · Focused practice", "questionCount": 5,
 "attempt": AttemptView | null, "history": [AttemptSummary, ...], "insights": Insights}
```
`attempt` is the open adaptive draft, else the latest submitted adaptive attempt. `history` contains adaptive attempts only.
Errors: `404` as for insights.

### `POST /learning/courses/{course_id}/chapters/{chapter_id}/practice`
Start a new adaptive practice set, or return the open one. The server picks up to five questions from the approved bank based on the caller's insights, snapshots them into a `kind: "adaptive"` attempt with `selection` metadata, and returns it. No body; the client cannot influence difficulty or question choice.
Response: `AttemptView`. Save and submit it with the draft/submit endpoints above.
Errors: `404` as for insights; `409` no approved practice questions; `503` a stored question fails validation.

### `GET /learning/content/{generation_id}`
Fetch a specific stored adapted lesson (e.g. from `contentVariant.generationId`).
```json
{"id": "uuid", "courseId": "ncert-maths-10-v1", "chapterId": "ch-01", "tier": "beginner", "verified": true, "generated": GeneratedLesson}
```
Errors: `404` pipeline disabled, or generation missing / not `ready`; `410` the chapter source or prompt version has changed since generation (reopen the chapter); `503` stored content fails validation. Raw provider output, source snapshots and usage are never returned.

## Static files

### `GET /uploads/avatars/{filename}`
Auth: none. Serves uploaded avatar images from `UPLOADS_DIR`.

## Generated documentation

| URL | Description |
| --- | --- |
| `/docs` | Swagger UI (interactive) |
| `/redoc` | ReDoc (read-only) |
| `/openapi.json` | OpenAPI 3 document |

Next: [06 – Development](06-development.md).

## Automatic explanations

`POST /learning/courses/{course_id}/chapters/{chapter_id}/explanation` starts or reuses a missing explanation at server-derived depth. Requires authentication, enrollment, engagement and automatic/pipeline flags. No tier in the request body. Returns `{status, generationId, retryAfterSeconds?}`; status is `available`, `pending`, `awaiting-review` or `failed`. Draft content and provider metadata are excluded. `429` supplies `Retry-After` for quota/cooldown; `503` indicates disabled/unavailable generation. Existing lessons remain readable.

`GET` on the same path checks current-source/current-tier generation status without inference. It may also return `unavailable`. It never returns unreviewed content. `GET /learning/content/{generation_id}` serves only verified, ready and current versions to enrolled students.

When tiered tests are enabled, chapter attempts snapshot five approved questions at server-selected difficulty. `selection` includes `tier`, `policyVersion`, focus concepts and fresh/repeated counts. Draft reuse preserves the snapshot. Final tests retain one authored question per chapter and the same eligibility rule.
