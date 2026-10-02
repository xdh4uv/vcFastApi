# Phase 1 engagement, tutor, Notes and aptitude

Migrations V4–V6 add seven tables without changing existing coursework or test snapshots.
The code defaults disabled (`ENGAGEMENT_ENABLED=false`, `TUTOR_ENABLED=false`).
Enable engagement only after all three migrations are applied. Tutor generation is independently gated;
reading, tests, existing conversations and Notes do not require the provider to be online.
`CONTENT_PIPELINE_ENABLED` still controls only cached adapted lessons, never tutor calls.

## Student behavior

- Existing students retain access to currently published subjects through the V6 enrollment backfill.
  New accounts can enroll in published subjects from the learning catalog. Course endpoints enforce enrollment.
- Reading progress is tied to the material hash. Changed material starts fresh progress. A section counts
  after 3 accepted active seconds. A configurable 75% threshold offers a test; direct test access remains.
- The browser records the most visible section/question, only while focused and recently active.
  Requests are batched, limited to 30 seconds, deduplicated by UUID, and capped by elapsed server time.
  This is advisory telemetry, not proof that a student understood content. Network loss/navigation can lose
  a small amount of unsent time. Timing does not affect grading or impose a test time limit.
- Tutor requests are grounded in base chapter/revision content, exclude assessment snapshots/keys and user
  profiles, include only the last four completed turns, and use the course's explanation tier. Questions and
  generated answers are stored in PostgreSQL. Failed answers remain visible without a fabricated response.
  The default cap is 10 requests/hour and 40/day per user, with one pending request across courses.
  Requests have 2048 output tokens and a 45-second provider read timeout. No automatic provider retries.
- Helpfulness is optional and editable; manual flags are recorded once. A flag records a review request;
  it does not notify a person or guarantee a human response. No reviewer dashboard is required in Phase 1.
- Notes copy only a completed answer owned by the current student. Duplicate saves reuse the same note.
  Notes persist across devices, filter by course/chapter and paginate 50 at a time. Deleting a note keeps
  the conversation. Search is explicitly limited to the current page. Editing remains outside Phase 1.

## Aptitude policy

Profiles are per student/course (subject + education level) so changing levels does not mix evidence.
Weights: tests 35%, consistency 15%, reading 20%, helpful resolution 15%, review avoidance 15%.
Tests use first answers to distinct question IDs with 30-day exponential decay; fixed-question retakes
cannot inflate evidence. Consistency counts days with meaningful activity in the last 30 days.
Reading time is capped at each base chapter's estimated reading time. Unrated tutor answers are unknown;
missing tutor signals use a neutral 0.5 rather than assuming resolution. Resolution uses rated successful
answers; flagged answers do not count as resolved. This operational definition is explicit, not an LLM guess.

Fewer than 10 evidence points, no assessment evidence, or signal variance above 0.15 keeps Default.
Confidence scales with evidence and variance. Eligible students are bucketed against the 30th/70th
percentiles of eligible profiles for the same course. Threshold ties and equal-score cohorts stay Default.
Test completion, result resets, helpfulness and flags update the student immediately. A nightly batch
refreshes the entire cohort before assigning tiers. Existing question-bank difficulty selection remains
concept-based; the course profile controls adapted lessons and tutor explanations.

Resetting results removes grading/timing evidence and recomputes aptitude. It preserves reading,
conversations, Notes, enrollment and education level. Other courses are unchanged.

## Rollout

1. Verify the exact target DB and current schema. The connected `vchitr-main` app DB had V1/V2 structures
   but **no Flyway history** and **no V3 content table** at the October 2 check. Do not baseline at version 3
   or 6 while those changes are absent. Establish the correct baseline only after auditing existing schema;
   then apply V3–V6 through Flyway. Never edit an already applied migration checksum.
2. V4–V6 were tested on an isolated Neon branch cloned from the actual app DB. SQLite regressions cover
   telemetry, ownership, retries, grading/reset integration, Notes, provider failures and aptitude policies.
   Browser tests use an explicitly disposable SQLite fixture and a stub tutor; they do not prove live model quality.
3. Deploy both code updates with features disabled, verify the frontend is current, then set
   `ENGAGEMENT_ENABLED=true` after migration. Keep
   `TUTOR_ENABLED=false` until the provider passes real grounded-question tests. Existing lesson publishing
   stays separately disabled until its content has been generated and reviewed.
4. Nightly GitHub Actions runs at 19:30 UTC (01:00 IST). Configure production secrets
   `APTITUDE_DATABASE_URL` (runtime pooled connection) and `JWT_SECRET`, then set repository variable
   `APTITUDE_NIGHTLY_ENABLED=true`. The job stays skipped until that variable is set.
   Operators can also run `python -m scripts.recompute_aptitude` with the usual backend environment.

Production migration, deployment flags, nightly secrets, live tutor quality and Phase 1 pilot metrics
must be verified separately. Implemented code is not evidence of completed production rollout.
