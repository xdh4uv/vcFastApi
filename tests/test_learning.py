"""Offline retrieval, ownership, grading, reset and curriculum regressions."""
import json
import os
from copy import deepcopy
from pathlib import Path
import unittest
from uuid import UUID, uuid4

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["JWT_SECRET"] = "local-regression-test-secret"

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session
from test_auth import create_test_engine
from app.models.learningCourseModel import LearningAttempt, LearningCourse, LearningPreference, LearningProgress
from app.models.subModuleMasterModel import SubModuleMaster
from app.models.usersModel import User
from app.routers import learning
from app.schemas.learning import AnswerSubmission, Course, LevelSelection, ResetRequest

CONTENT = json.loads((Path(__file__).resolve().parents[1] / "data/ncert-maths-10-v1.json").read_text(encoding="utf-8"))
COURSE = CONTENT["id"]


class LearningTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_test_engine().execution_options(schema_translate_map={"public": None, "modules": None})
        for model in (SubModuleMaster, LearningCourse, LearningPreference, LearningProgress, LearningAttempt):
            model.__table__.create(self.engine)
        self.db = Session(self.engine)
        self.user = User(email="first@example.com", username="first", onboarding_completed=True)
        self.other = User(email="second@example.com", username="second", onboarding_completed=True)
        self.subject = SubModuleMaster(sub_module_id=uuid4(), sub_module_name="Maths")
        self.db.add_all([self.user, self.other, self.subject])
        self.db.flush()
        self.db.add(LearningCourse(course_id=COURSE, subject_id=self.subject.sub_module_id, level="high-school", content=CONTENT))
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def call(self, fn, *args, user=None):
        try:
            return fn(*args, db=self.db, user=user or self.user)
        except HTTPException:
            self.db.rollback()
            raise

    def start(self, test_id, user=None, course_id=COURSE):
        return self.call(learning.start_attempt, course_id, test_id, user=user)

    def submit(self, attempt, correct=True, user=None, course_id=COURSE):
        stored = self.db.get(LearningAttempt, UUID(attempt["id"]))
        answers = {q["id"]: q["answer"] if correct else (q["answer"] + 1) % 4 for q in stored.questions}
        return self.call(learning.submit_attempt, course_id, UUID(attempt["id"]),
                         AnswerSubmission(answers=answers, revision=attempt["revision"]), user=user)

    def assert_status(self, status, fn):
        with self.assertRaises(HTTPException) as caught:
            fn()
        self.assertEqual(caught.exception.status_code, status)

    def test_first_visit_and_saved_preference_are_per_subject_and_user(self):
        self.assertIsNone(self.call(learning.get_subject, "Mathematics")["selectedLevel"])
        selected = self.call(learning.set_level, self.subject.sub_module_id, LevelSelection(level="high-school"))
        self.assertEqual(selected["courseId"], COURSE)
        self.db.expire_all()
        self.assertEqual(self.call(learning.get_subject, "Maths")["selectedLevel"], "high-school")
        self.assertIsNone(self.call(learning.get_subject, "Maths", user=self.other)["selectedLevel"])
        self.assert_status(422, lambda: self.call(learning.set_level, self.subject.sub_module_id, LevelSelection(level="masters")))

    def test_changing_levels_preserves_previous_course_progress(self):
        self.submit(self.start("ch-01"))
        second = deepcopy(CONTENT)
        second["id"] = "other-level-v1"
        self.db.add(LearningCourse(course_id=second["id"], subject_id=self.subject.sub_module_id, level="masters", content=second))
        self.db.commit()
        self.call(learning.set_level, self.subject.sub_module_id, LevelSelection(level="masters"))
        self.assertEqual(self.call(learning.get_course, second["id"])["progress"]["history"], [])
        self.call(learning.set_level, self.subject.sub_module_id, LevelSelection(level="high-school"))
        self.assertEqual(len(self.call(learning.get_course, COURSE)["progress"]["history"]), 1)

    def test_combined_subject_overview_is_fresh_scoped_and_redacts_questions(self):
        self.assertIsNone(learning.get_subject("Maths", self.db, self.user, True)["course"])
        self.call(learning.set_level, self.subject.sub_module_id, LevelSelection(level="high-school"))
        self.submit(self.start("ch-01"))
        view = learning.get_subject("Maths", self.db, self.user, True)
        self.assertEqual(view["course"], self.call(learning.get_course, COURSE))
        self.assertEqual(len(view["course"]["progress"]["history"]), 1)
        self.assertNotIn("questions", json.dumps(view["course"], default=str))
        self.assertIsNone(learning.get_subject("Maths", self.db, self.other, True)["course"])
        self.assertNotIn("course", self.call(learning.get_subject, "Maths"))

    def test_material_reads_database_and_never_exposes_test_keys(self):
        row = self.db.get(LearningCourse, COURSE)
        content = deepcopy(row.content)
        content["chapters"][0]["goal"] = "Fresh database material"
        row.content = content
        self.db.commit()
        self.assertEqual(self.call(learning.get_chapter, COURSE, "ch-01")["goal"], "Fresh database material")
        self.assertNotIn("questions", self.call(learning.get_chapter, COURSE, "ch-01"))
        self.assertNotIn("questions", self.call(learning.get_course, COURSE)["chapters"][0])
        draft = self.start("ch-01")
        self.assertNotIn("answer", draft["questions"][0])
        self.assertNotIn("explanation", draft["questions"][0])
        self.assertEqual(self.start("ch-01")["id"], draft["id"])

    def test_saved_draft_survives_session_and_rejects_stale_device_revision(self):
        draft = self.start("ch-01")
        body = AnswerSubmission(answers={draft["questions"][0]["id"]: 2}, revision=0)
        saved = self.call(learning.save_draft, COURSE, UUID(draft["id"]), body)
        user_id = self.user.id
        self.db.close()
        self.db = Session(self.engine)
        self.user = self.db.get(User, user_id)
        loaded = self.call(learning.get_test, COURSE, "ch-01")["attempt"]
        self.assertEqual(loaded["answers"], body.answers)
        self.assertEqual(loaded["revision"], 1)
        self.assert_status(409, lambda: self.call(learning.save_draft, COURSE, UUID(draft["id"]), body))
        self.assertEqual(saved["id"], loaded["id"])

    def test_incomplete_invalid_and_forged_score_submissions_fail(self):
        draft = self.start("ch-01")
        for answers in ({}, {"unknown": 0}, {draft["questions"][0]["id"]: 9}):
            self.assert_status(422, lambda: self.call(learning.submit_attempt, COURSE, UUID(draft["id"]), AnswerSubmission(answers=answers, revision=0)))
        with self.assertRaises(ValidationError):
            AnswerSubmission(answers={}, revision=0, correct=5)
        with self.assertRaises(ValidationError):
            AnswerSubmission(answers={"q": True}, revision=0)

    def test_server_grading_idempotent_retry_and_lower_retake(self):
        draft = self.start("ch-01")
        result = self.submit(draft)
        self.assertEqual(result["percent"], 100)
        self.assertIn("answer", result["questions"][0])
        duplicate = self.call(learning.submit_attempt, COURSE, UUID(draft["id"]), AnswerSubmission(answers=result["answers"], revision=0))
        self.assertEqual(duplicate["id"], result["id"])
        self.assertEqual(len(self.call(learning.get_test, COURSE, "ch-01")["history"]), 1)
        self.submit(self.start("ch-01"), correct=False)
        history = self.call(learning.get_test, COURSE, "ch-01")["history"]
        self.assertEqual(history[-1]["percent"], 0)
        self.assertEqual(max(a["percent"] for a in history), 100)

    def test_attempt_uses_immutable_question_snapshot(self):
        draft = self.start("ch-01")
        row = self.db.get(LearningCourse, COURSE)
        changed = deepcopy(row.content)
        changed["chapters"][0]["questions"][0]["answer"] = 1
        row.content = changed
        self.db.commit()
        self.assertEqual(self.submit(draft)["percent"], 100)

    def test_final_requires_distinct_chapters_then_accepts_zero_scores(self):
        for _ in range(14):
            self.submit(self.start("ch-01"), correct=False)
        self.assert_status(403, lambda: self.start("final"))
        for chapter in CONTENT["chapters"][1:-1]:
            self.submit(self.start(chapter["id"]), correct=False)
        self.assert_status(403, lambda: self.call(learning.get_test, COURSE, "final"))
        self.submit(self.start("ch-14"), correct=False)
        final = self.start("final")
        self.assertEqual(len(final["questions"]), 14)
        self.assertEqual(self.submit(final)["percent"], 100)

    def test_other_user_cannot_read_modify_or_submit_attempt(self):
        draft = self.start("ch-01")
        body = AnswerSubmission(answers={}, revision=0)
        self.assert_status(404, lambda: self.call(learning.save_draft, COURSE, UUID(draft["id"]), body, user=self.other))
        self.assert_status(404, lambda: self.call(learning.submit_attempt, COURSE, UUID(draft["id"]), body, user=self.other))
        self.assertIsNone(self.call(learning.get_test, COURSE, "ch-01", user=self.other)["attempt"])

    def test_reset_clears_only_own_course_results_and_invalidates_stale_attempt(self):
        self.call(learning.set_level, self.subject.sub_module_id, LevelSelection(level="high-school"))
        self.call(learning.mark_read, COURSE, "ch-01")
        draft = self.start("ch-01")
        self.submit(draft)
        self.submit(self.start("ch-01", user=self.other), user=self.other)
        reset = self.call(learning.reset_results, COURSE, ResetRequest(confirm=True))
        self.assertEqual(reset["history"], [])
        self.assertEqual(reset["read"], ["ch-01"])
        self.assertFalse(reset["finalUnlocked"])
        self.assertEqual(self.call(learning.get_subject, "Maths")["selectedLevel"], "high-school")
        self.assertEqual(len(self.call(learning.get_test, COURSE, "ch-01", user=self.other)["history"]), 1)
        self.assert_status(404, lambda: self.call(learning.submit_attempt, COURSE, UUID(draft["id"]), AnswerSubmission(answers={}, revision=0)))

    def test_complete_seed_and_unique_final_questions(self):
        course = Course.model_validate(CONTENT)
        self.assertEqual(len(course.chapters), 14)
        questions = [q for c in course.chapters for q in [*c.questions, c.finalQuestion]]
        self.assertEqual(len(questions), 84)
        self.assertEqual(len(set(q.prompt for q in questions)), 84)
        for chapter in course.chapters:
            self.assertEqual(len(chapter.questions), 5)
            self.assertEqual(len(chapter.example.steps), 3)
        expected = ["160", "−8/3", "(5, 3)", "6 and −3", "99", "7", "(6, 3)", "2", "7√3 m", "24 cm", "15π cm²", "54π", "15", "3/4"]
        for chapter, answer in zip(course.chapters, expected):
            self.assertEqual(chapter.finalQuestion.options[chapter.finalQuestion.answer], answer)

    def test_missing_and_corrupt_course(self):
        self.assert_status(404, lambda: self.call(learning.get_course, "missing"))
        self.db.get(LearningCourse, COURSE).content = {"id": COURSE}
        self.db.commit()
        self.assert_status(503, lambda: self.call(learning.get_course, COURSE))


if __name__ == "__main__":
    unittest.main()
