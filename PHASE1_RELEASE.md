# Phase 1 release checks — 2 October 2026

Production Cloud Run deployment and feature activation are deferred at the user's request. The frontend is already deployed from `main`; this release changes backend code and stored curriculum only. Code readiness, database readiness and a successful four-week pilot are separate milestones.

## Database readiness

The actual app target is Neon project `aged-snow-68421859`, database `vchitr-main`, development branch `br-shiny-star-a1aiwpft`. The project's default production branch is a different target; it was not changed.

A fresh clone, `phase1-release-verification` (`br-delicate-fire-a1vo2zk5`), passed first. Both targets matched the V1/V2 reference: columns, types, nullability, defaults, constraints, indexes and required runtime grants. The owner received the missing public-schema USAGE/CREATE permissions. Flyway then baselined at 2, applied V3–V6 and validated successfully. Ordered row fingerprints for users and existing learning tables were unchanged after migration. V6 preserved access through the enrollment backfill.

The subsequent V7 content revision also passed on the clone, then the app database: elevation/depression equality now uses alternate interior angles. Three corrected questions have new IDs; old questions are retained with draft status and old attempt snapshots are unchanged. Flyway validates through V7. Separate fingerprints confirmed student accounts, preferences, progress, attempts, doubts and Notes were unchanged by this revision.

The runtime `admin` role has SELECT on generated content. Publication/approval uses the direct schema-owner connection in an operator process. Owner credentials are not committed or installed in the HTTP-serving environment.

## Lesson and tutor fixes

- `lesson-v4` retains authored example solutions and requires explicit mathematical review before serving. Polynomials checks reject selected invalid monic-scaling claims, unqualified repeated-zero graph claims and methods outside the supplied chapter.
- The reviewer can correct unpublished JSON with `python -m scripts.review_content ID --approve --content-file corrected.json`. Original raw response remains unchanged. Only schema-valid `invalid_lesson` failures can be repaired this way; timeouts, refusals and provider errors cannot be approved. Reviewed versions cannot be edited.
- NIM lesson thinking defaults off when unspecified. Explicit overrides are preserved, and NIM-specific options cannot leak to another provider. The local operator setting is also false.
- Tutor answers normalize common presentation wrappers and supported mathematical commands into readable text. Fraction parentheses preserve precedence. Unsupported commands and HTML still fail safely; this is not a general LaTeX renderer.
- Live tutor retest: two questions answered correctly, including the previously rejected underspecified-polynomial question; two calls returned provider HTTP 503. Provider outages remain a rollout limitation.

### Reviewed curriculum

**28/28 current-source variants are ready and reviewed in the app database**: Beginner and Advanced for all 14 Class 10 Mathematics chapters. The final read-only audit used runtime role `admin` and the actual cache reader, validating current source hashes, `lesson-v4`, schema, authored steps and quality checks. Default lessons remain the authored database content. No student request regenerates a lesson.

Intermittent NIM HTTP 503s stopped several batches. Explicit continuations reused completed variants; the final eight-variant batch succeeded. Failed/stale drafts remain for diagnosis and cannot be served. Successful publication does not prove provider availability for a later live tutor request.

Review checks included every explanation, worked example, self-check and takeaway. Corrections included zero-denominator conditions, rational/irrational zero exceptions, quadratic-only graph claims, exclusion of complex roots, fractional AP differences, AP zero-term existence, valid triangle correspondence, coordinate-axis distance conditions, shared-height assumptions, full-disk boundaries, exposed surfaces, median-frequency direction, continuous class boundaries and independence in probability. This operator review is not a claim of teacher certification.

## Verification evidence

- Backend: **99 tests passed** locally, covering provider contracts/failures, review gating/corrections, normalization, grading/reset, ownership, engagement, aptitude and pilot arithmetic.
- GitHub Actions [verification run](https://github.com/xdh4uv/vcFastApi/actions/runs/37000575870) passed empty PostgreSQL migration replay through V7, all-bank seeding/verification and backend regressions for code commit `6943bb5`. Remote migration was skipped behind its activation variable.
- Enabled API smoke on the isolated Neon clone, with runtime `admin` role: **25 checks passed**. Authentication, enrollment, saved level, chapter retrieval, reviewed generation retrieval, ownership, final-test lock, idempotent reading events, tutor persistence, feedback/flags, duplicate-safe Notes, backend grading, idempotent submission and reset preserving Notes were exercised. The tutor was explicitly stubbed for these API checks.
- Cached lesson benchmark: **20/20 successful HTTP requests, p95 0.987 seconds**, including authentication and Neon retrieval. This is sequential traffic through a local backend against the clone, not production load testing or browser paint latency.
- `python -m scripts.recompute_aptitude` passed on the clone and recomputed three course profiles. This validates the command, not the production scheduler.
- App-database pilot report: one active student, no matured 28-day score pairs and no tutor questions in the reporting window. Insufficient evidence stays unknown; there is no claim that pilot targets are met.

## Activation when Cloud Run access is confirmed

1. Deploy the tested backend revision with current feature flags disabled. Verify the deployed SHA, health, normal login and existing course/test behavior.
2. Confirm the service points to the audited `vchitr-main` branch and Flyway validates through V7. Do not baseline another nonempty database without auditing it.
3. Enable `ENGAGEMENT_ENABLED=true`. Check enrollment, reading progress, grading, tier badges and Notes. Existing conversations/Notes remain usable without the tutor provider.
4. Enable `CONTENT_PIPELINE_ENABLED=true` only after current-source/current-prompt variants are reviewed. Check Beginner/Default/Advanced selection and base fallbacks. The HTTP server does not need a provider key for cached lessons.
5. Enable `TUTOR_ENABLED=true` only after live grounded, underspecified and off-topic questions pass with the deployed provider config. Configure the key as a backend secret. Verify failure states and request limits; never expose the key through VITE variables.
6. Configure GitHub secrets `APTITUDE_DATABASE_URL` and `JWT_SECRET`, then set `APTITUDE_NIGHTLY_ENABLED=true`. The nightly workflow runs at 19:30 UTC (01:00 IST). These production settings have not been configured by this release.
7. For automatic future migrations, configure `NEON_FLYWAY_URL`, `NEON_FLYWAY_USER`, `NEON_FLYWAY_PASSWORD` and set `DATABASE_MIGRATIONS_ENABLED=true`. The URL must use the exact target's direct host. CI always verifies an empty PostgreSQL database and runs regressions; remote migration stays gated until explicitly enabled.
8. Repeat the full flow in the production browser and benchmark production from representative networks before declaring rollout complete. Disable the affected feature flag if checks fail; additive migrations and stored history need not be removed.

## Pilot measurements

Generate an aggregate report without exposing student identities, answers or tutor text:

```powershell
python -m scripts.pilot_report --course ncert-maths-10-v1 --days 35 --output pilot-report.json
```

The reporting window counts active students and students saving Notes; confirmed tutor resolution means a ready, helpful, unflagged answer divided by all questions. Unrated answers are unknown. Score gain compares first/latest official attempts for the same learner/chapter at least 28 days apart, averages chapters within each learner, then gives learners equal weight. Zero-score baselines are excluded from relative gain but included in percentage-point gain. Fixed-question retakes and selection effects limit interpretation: the report is observational and cannot prove the platform caused improvement.

Benchmark a current reviewed UUID with an authenticated enrolled student. Supply `PHASE1_BENCHMARK_TOKEN` securely in the process environment, never in the command or committed files:

```powershell
python -m scripts.benchmark_content --base-url https://YOUR-BACKEND --generation REVIEWED-UUID --samples 20 --output cache-latency.json
```

The benchmark follows no redirects, makes read-only requests, requires verified content and fails if any request fails or p95 is at least three seconds. It measures HTTP response time, not rendering. PRD targets still require actual users: >70% doubt resolution, >10% average four-week score improvement and >30% Notes adoption.
