import unittest
from copy import deepcopy
from collections import Counter
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import UUID

import test_learning as baseline
from app.models.learningCourseModel import LearningAttempt, LearningConcept, PracticeQuestion
from app.routers import learning
from app.schemas.learning import AnswerSubmission, ResetRequest
from app.services.adaptive import concept_evidence
from scripts.seed_adaptive import read_bank
from scripts.build_real_numbers_bank import build

BANK = read_bank()
COURSE = BANK.courseId


class AdaptiveTests(unittest.TestCase):
    call = baseline.LearningTests.call
    submit = baseline.LearningTests.submit
    start = baseline.LearningTests.start
    assert_status = baseline.LearningTests.assert_status
    tearDown = baseline.LearningTests.tearDown

    def setUp(self):
        baseline.LearningTests.setUp(self)
        for c in BANK.concepts:
            self.db.add(LearningConcept(course_id=COURSE, chapter_id="ch-01", concept_id=c.id, material=c.model_dump()))
        for q in BANK.questions:
            self.db.add(PracticeQuestion(id=q.id, course_id=COURSE, chapter_id="ch-01", concept_id=q.conceptId,
                                        difficulty=q.difficulty, status="approved", content=q.model_dump()))
        self.db.commit()

    def practice(self, user=None):
        return self.call(learning.start_practice, COURSE, "ch-01", user=user)

    def insights(self, user=None):
        return self.call(learning.get_insights, COURSE, "ch-01", user=user)

    def test_bank_coverage_and_generated_artifact(self):
        self.assertEqual(BANK.model_dump(), build())
        counts = Counter((q.conceptId, q.difficulty) for q in BANK.questions)
        self.assertEqual(len(counts), 15)
        self.assertEqual(set(counts.values()), {3})
        self.assertEqual(len({q.prompt for q in BANK.questions}), 45)

    def test_checked_answer_key_for_every_arithmetic_question(self):
        # Independently calculated solutions, separate from the bank constructor.
        expected = {1:'2³ × 3²',2:'2² × 3³',3:'2³ × 5²',4:2,5:3,6:2,7:3,8:2,9:5,
                    10:12,11:18,12:40,13:12,14:32,15:35,16:48,17:18,18:84,
                    19:24,20:45,21:42,22:36,23:60,24:48,25:72,26:60,27:180,
                    28:'√2',29:'√3',30:'√7',31:'√2 + 1',32:'√3 + 1',33:'√7 + 1',
                    37:36,38:24,39:40,40:90,41:120,42:84,43:'18 and 30',44:'12 and 28',45:'20 and 45'}
        for number, answer in expected.items():
            q = BANK.questions[number-1]
            self.assertEqual(q.options[q.answer], str(answer), q.id)
        for number, prime in [(34,2),(35,3),(36,7)]:
            q = BANK.questions[number-1]
            self.assertEqual(q.options[q.answer], f'Prime {prime} divides a, and substitution then shows it divides b, contradicting lowest terms.')

    def test_sparse_evidence_and_wrong_baseline_target_foundation(self):
        self.assertTrue(all(c["evidenceCount"] == 0 for c in self.insights()["concepts"]))
        attempt = self.start("ch-01")
        snapshot = self.db.get(LearningAttempt, UUID(attempt["id"]))
        answers = {q["id"]: (q["answer"]+1)%4 if q["concept"] in ("HCF", "LCM") else q["answer"] for q in snapshot.questions}
        self.call(learning.submit_attempt, COURSE, snapshot.id, AnswerSubmission(answers=answers, revision=0))
        concepts = {c["id"]: c for c in self.insights()["concepts"]}
        self.assertEqual(concepts["hcf"]["nextDifficulty"], "foundation")
        self.assertEqual(concepts["hcf"]["status"], "insufficient")
        practice = self.practice()
        self.assertGreaterEqual(sum(q["conceptId"] in ("hcf", "lcm") for q in practice["questions"]), 3)
        self.assertTrue(all(q["difficulty"] == "foundation" for q in practice["questions"] if q["conceptId"] in ("hcf", "lcm")))

    def test_duplicate_start_snapshot_redaction_and_separate_official_draft(self):
        official = self.start("ch-01")
        first = self.practice()
        self.assertEqual(first["id"], self.practice()["id"])
        self.assertNotEqual(official["id"], first["id"])
        self.assertEqual(len({q["id"] for q in first["questions"]}), 5)
        self.assertTrue(all("answer" not in q and "explanation" not in q for q in first["questions"]))
        self.assertEqual(self.call(learning.get_test, COURSE, "ch-01")["attempt"]["id"], official["id"])
        self.db.expire_all()
        self.assertEqual(self.call(learning.get_practice, COURSE, "ch-01")["attempt"], first)

    def test_adaptive_scores_do_not_complete_chapter_or_pollute_official_history(self):
        result = self.submit(self.practice())
        self.assertEqual(result["percent"], 100)
        self.assertIn("insights", result)
        progress = self.call(learning.get_course, COURSE)["progress"]
        self.assertEqual(progress["history"], [])
        self.assertFalse(progress["finalUnlocked"])
        self.assert_status(403, lambda: self.start("final"))

    def test_saved_draft_snapshot_survives_bank_changes(self):
        attempt = self.practice()
        q = attempt["questions"][0]
        saved = self.call(learning.save_draft, COURSE, UUID(attempt["id"]), AnswerSubmission(answers={q["id"]: 1}, revision=0))
        bank_row = self.db.get(PracticeQuestion, q["id"])
        bank_row.content = {**bank_row.content, "answer": (bank_row.content["answer"]+1)%4}
        self.db.commit()
        loaded = self.call(learning.get_practice, COURSE, "ch-01")["attempt"]
        self.assertEqual(saved, loaded)
        self.assert_status(409, lambda: self.call(learning.save_draft, COURSE, UUID(attempt["id"]), AnswerSubmission(answers={}, revision=0)))
        self.assertEqual(self.submit(saved)["percent"], 100)

    def test_repeat_baseline_does_not_inflate_evidence(self):
        self.submit(self.start("ch-01"), correct=False)
        before = self.insights()
        self.submit(self.start("ch-01"), correct=True)
        self.assertEqual(before, self.insights())

    def test_bank_exhaustion_short_set_then_labeled_revision(self):
        seen = set()
        for _ in range(9):
            attempt = self.practice()
            ids = {q["id"] for q in attempt["questions"]}
            self.assertFalse(seen & ids)
            seen |= ids
            self.submit(attempt)
        self.assertEqual(len(seen), 45)
        before = self.insights()
        revision = self.practice()
        self.assertEqual(revision["selection"]["mode"], "revision")
        self.assertEqual(revision["selection"]["freshCount"], 0)
        self.submit(revision, correct=False)
        self.assertEqual(before, self.insights())

    def test_short_fresh_set_and_unpublished_questions(self):
        ids = [q.id for q in BANK.questions[:2]]
        for row in self.db.query(PracticeQuestion).all():
            row.status = "approved" if row.id in ids else "draft"
        self.db.commit()
        attempt = self.practice()
        self.assertEqual(len(attempt["questions"]), 2)
        self.assertEqual(self.submit(attempt)["total"], 2)
        self.db.query(PracticeQuestion).update({"status": "draft"})
        self.db.commit()
        self.assert_status(409, self.practice)

    def test_reset_isolated_and_stale_attempt_cannot_return(self):
        self.submit(self.practice())
        other = self.practice(user=self.other)
        self.submit(other, user=self.other)
        stale = self.practice()
        self.call(learning.mark_read, COURSE, "ch-01")
        self.call(learning.reset_results, COURSE, ResetRequest(confirm=True))
        self.assertTrue(all(c["evidenceCount"] == 0 for c in self.insights()["concepts"]))
        self.assertTrue(any(c["evidenceCount"] for c in self.insights(user=self.other)["concepts"]))
        self.assertIn("ch-01", self.call(learning.get_course, COURSE)["progress"]["read"])
        self.assert_status(404, lambda: self.call(learning.save_draft, COURSE, UUID(stale["id"]), AnswerSubmission(answers={}, revision=0)))

    def test_ownership_and_idempotent_adaptive_submission(self):
        attempt = self.practice()
        self.assert_status(404, lambda: self.call(learning.save_draft, COURSE, UUID(attempt["id"]), AnswerSubmission(answers={}, revision=0), user=self.other))
        result = self.submit(attempt)
        retry = self.call(learning.submit_attempt, COURSE, UUID(attempt["id"]), AnswerSubmission(answers=result["answers"], revision=0))
        self.assertEqual(result, retry)
        self.assertEqual(len(self.call(learning.get_practice, COURSE, "ch-01")["history"]), 1)

    def test_difficulty_changes_one_step_using_fresh_evidence(self):
        concept = next(c for c in BANK.concepts if c.id == "hcf")
        def record(i, correct, difficulty):
            return SimpleNamespace(id=str(i), submitted_at=datetime(2026,1,1,tzinfo=timezone.utc)+timedelta(seconds=i),
                selection_metadata={}, questions=[dict(id=str(i), conceptId="hcf", answer=0, difficulty=difficulty)], answers={str(i): 0 if correct else 1})
        records = [record(0, False, "standard")] + [record(i, True, "foundation") for i in range(1,4)]
        self.assertEqual(concept_evidence([concept], records)[0]["nextDifficulty"], "standard")
        records += [record(i, True, "standard") for i in range(4,7)]
        self.assertEqual(concept_evidence([concept], records)[0]["nextDifficulty"], "challenge")
        records += [record(i, False, "challenge") for i in range(7,9)]
        self.assertEqual(concept_evidence([concept], records)[0]["nextDifficulty"], "standard")

    def test_unavailable_chapter_and_corrupt_bank_fail_cleanly(self):
        self.assert_status(404, lambda: self.call(learning.get_practice, COURSE, "ch-02"))
        for q in self.db.query(PracticeQuestion).all():
            q.content = {**q.content, "answer": 7}
        self.db.commit()
        self.assert_status(503, self.practice)
