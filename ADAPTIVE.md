# Class 10 adaptive practice

Supported chapters: Class 10 Real Numbers and Polynomials. Each has five concept revision cards and 45 original MCQs (three variants at each of three difficulties per concept) stored in Neon. Answer keys have independent regression checks. A teacher has not reviewed these starter banks; do not describe them as complete assessments or validated measures of mastery.

## Migration and publishing

Run migration 001 first for new environments. Use the existing schema owner's direct Neon connection in DATABASE_URL_UNPOOLED. The app's admin role receives SELECT on the two new content tables. Existing learning-attempt table grants cover its added columns.

```text
python -m scripts.seed_adaptive
python -m scripts.verify_adaptive_db
python -m scripts.seed_adaptive --bank polynomials --content-only
python -m scripts.verify_adaptive_db --bank polynomials
```

Seed applies migrations/002_adaptive_practice.sql and publishes the immutable versioned bank in one transaction. Existing question snapshots, answers, scores and read markers are preserved. Existing final attempts are classified as final. Repeating the seed is safe; changed published question documents fail instead of being overwritten. Use a new question ID for revised wording or keys. Updating revision cards requires an explicit reviewed migration.

For an existing adaptive installation, `--content-only` publishes a new bank without reapplying migration 002 or replacing indexes. Polynomials needs no new schema or runtime API/frontend code: availability is discovered from the concept table. The default bank remains Real Numbers for compatibility. Each verifier checks its requested bank.

Polynomials covers finding/checking zeroes, degree and graphical zeroes, sum of zeroes, product/coefficient relations, and forming quadratics. Its existing five chapter-test labels map to these five concepts. Signals, drafts and question selection stay scoped to the chapter. New question IDs use `poly-v1-`; existing chapter tests and Real Numbers snapshots are unchanged. All 45 answer keys are checked independently, including negative values, rational results, repeated-zero interpretation and non-monic quadratics. The graph items describe axis contacts in text; there is no graph-drawing exercise. This extends the current starter lesson, not every textbook exercise or topic.

Reference checked 15 September 2026: [NCERT Class X Polynomials, 2026–27 reprint](https://ncert.nic.in/textbook/pdf/jemh102.pdf), for topic alignment. Revision explanations and practice questions are original. Regenerate with `python -m scripts.build_polynomials_bank` and run the tests before publishing.

Migration 002 replaces the active-draft index with user/course/test/kind uniqueness and adds kind plus selection_metadata. Two new tables store concepts and practice questions. This permits separate chapter and adaptive drafts. Test the migration on an isolated Neon branch before applying to the app DB. Deploy the migrated backend before enabling the matching frontend. Reverting to a backend that cannot distinguish adaptive attempts can misinterpret completion; disable adaptive entry points on the current backend instead of rolling back to an incompatible version.

## Runtime flow

- GET /learning/courses/{course}/chapters/{chapter}/insights: revision cards, evidence and next difficulty.
- GET on the same chapter's /practice endpoint: current adaptive draft or latest result, adaptive history and insights. No attempt is created by GET.
- POST /practice: start/resume a snapshot selected by the backend. No client score, difficulty or question-list input is used.
- Existing draft and submit endpoints save and grade the snapshot. Adaptive submission returns updated insights; identical retry returns the same score.
- Chapter-test reviews include concept feedback when this chapter has published concepts. Lessons advertise adaptiveAvailable from the DB.

All endpoints require bearer authentication. Question keys and explanations are hidden before submission. Existing user/course locks serialize start, save, submit and reset. Stale revisions return 409; reset attempt IDs return 404. Snapshots remain gradeable after their source bank changes.

## Policy concept-practice-v1

Use the first submitted answer for each question ID/version, scoped to this user/course/chapter. Old fixed questions map their original concept labels to stable concept IDs. Final-test questions are excluded. Repeated revision questions are explicitly excluded from evidence. The five most recent eligible answers form a displayed concept signal: fewer than three = insufficient evidence; below 60% = revise; below 80% = practise; otherwise positive signals. A recent miss also raises revision priority. These are product heuristics, not validated aptitude thresholds.

Difficulty starts at standard. A first wrong answer starts foundation revision. Three fresh correct answers at the current difficulty move up one level; two misses among up to three current-level answers move down one level. The evidence window restarts after each transition. Education level never changes automatically.

Selection first excludes all question IDs already presented, including drafts. Up to three slots target revision priorities; remaining slots cover other concepts. Prefer the requested difficulty, then the closest available difficulty (ties favor easier). Stable IDs break ties. If only a smaller fresh set exists, return that set. Once the entire approved chapter bank has been presented, return labeled repeated revision. Every selected question and selection-policy metadata is saved before responding. Subsequent openings resume exactly that snapshot.

Adaptive scores stay separate from official chapter/final history and eligibility. Practice sets show focus, difficulty mix and fresh/revision labels; scores across different sets are not ranked as equivalent. Course reset clears all official and adaptive attempts, consequently clearing derived evidence, while retaining level and read markers.

## Validation and limits

Run python -m unittest discover -s tests -v. Regressions cover independent content keys, first-answer evidence, difficulty transitions, draft uniqueness, fresh-set exhaustion, short sets, unpublished/corrupt content, snapshots, ownership, idempotence, resets and official eligibility. PostgreSQL/API verification additionally exercises concurrent starts and reset/submit races.

Requests read Neon; the frontend has no course or result cache. Selection reads metadata once and loads selected documents in one batch. Evidence currently reads chapter attempt history; materialize bounded summaries only if measured history growth requires it. No LLM calls, generation queues, adaptive chapters beyond these two, or automatic Cloud Run deployment are included. Future generators can submit draft questions to this bank after mathematical validation and publication review.
