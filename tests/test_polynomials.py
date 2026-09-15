import unittest
from collections import Counter
from uuid import UUID

import test_learning as baseline
from app.models.learningCourseModel import LearningConcept, PracticeQuestion
from app.routers import learning
from app.schemas.learning import AnswerSubmission, ResetRequest
from scripts.seed_adaptive import read_bank
from scripts.build_polynomials_bank import build

BANK = read_bank('polynomials')
COURSE = BANK.courseId


class PolynomialsTests(unittest.TestCase):
    call = baseline.LearningTests.call
    start = baseline.LearningTests.start
    submit = baseline.LearningTests.submit
    assert_status = baseline.LearningTests.assert_status
    tearDown = baseline.LearningTests.tearDown

    def setUp(self):
        baseline.LearningTests.setUp(self)
        for bank in [read_bank(), BANK]:
            for c in bank.concepts:
                self.db.add(LearningConcept(course_id=COURSE, chapter_id=bank.chapterId, concept_id=c.id, material=c.model_dump()))
            for q in bank.questions:
                self.db.add(PracticeQuestion(id=q.id, course_id=COURSE, chapter_id=bank.chapterId, concept_id=q.conceptId,
                                            difficulty=q.difficulty, status='approved', content=q.model_dump()))
        self.db.commit()

    def practice(self, chapter='ch-02'):
        return self.call(learning.start_practice, COURSE, chapter)

    def insights(self, chapter='ch-02'):
        return self.call(learning.get_insights, COURSE, chapter)

    def test_bank_coverage_and_independent_answer_key(self):
        self.assertEqual(BANK.model_dump(), build())
        counts = Counter((q.conceptId, q.difficulty) for q in BANK.questions)
        self.assertEqual(len(counts), 15)
        self.assertEqual(set(counts.values()), {3})
        self.assertEqual(len({q.prompt for q in BANK.questions}), 45)
        self.assertFalse({q.id for q in BANK.questions} & {q.id for q in read_bank().questions})
        # Independently worked answers; do not derive these from generator helpers.
        answers = ['4','-2','7','2 and 5','-3 and 2','-4 and -1','-2','-2','3',
                   '3','2','1','2','1','0','2','1','0',
                   '6','-5','9/2','6','4','-5','-10','12','-12',
                   '12','-3','4/3','5','4','-1','20','-12','20',
                   'x² - 5x + 4','x² - 5x + 6','x² - 3x - 10','x² + 5x + 6','x² + 2x - 8','x² - 5x',
                   '2x² - 8x + 6','3x² - 6x - 24','2x² + 8x + 6']
        self.assertEqual(len(answers), len(BANK.questions))
        for question, answer in zip(BANK.questions, answers):
            self.assertEqual(question.options[question.answer], answer, question.id)

    def test_legacy_feedback_maps_every_baseline_concept_and_stays_in_chapter(self):
        before = self.insights('ch-01')
        self.submit(self.start('ch-02'), correct=False)
        insights = self.insights()
        self.assertTrue(all(c['evidenceCount'] == 1 and c['correct'] == 0 and c['nextDifficulty'] == 'foundation' for c in insights['concepts']))
        self.assertEqual(before, self.insights('ch-01'))
        review = self.call(learning.get_test, COURSE, 'ch-02')
        self.assertTrue(review['adaptiveAvailable'])
        self.assertEqual(review['insights'], insights)
        self.assertTrue(self.call(learning.get_chapter, COURSE, 'ch-02')['adaptiveAvailable'])
        self.assertFalse(self.call(learning.get_chapter, COURSE, 'ch-03')['adaptiveAvailable'])
        attempt = self.practice()
        self.assertEqual(len(attempt['questions']), 5)
        self.assertTrue(all(q['difficulty'] == 'foundation' and q['id'].startswith('poly-v1-') for q in attempt['questions']))

    def test_drafts_grades_history_and_reset_with_two_adaptive_chapters(self):
        real = self.practice('ch-01')
        official = self.start('ch-02')
        attempt = self.practice()
        self.assertEqual(attempt['id'], self.practice()['id'])
        self.assertEqual(len({a['id'] for a in [real, official, attempt]}), 3)
        self.assertTrue(all('answer' not in q and 'explanation' not in q for q in attempt['questions']))
        saved = self.call(learning.save_draft, COURSE, UUID(attempt['id']), AnswerSubmission(answers={attempt['questions'][0]['id']: 1}, revision=0))
        self.db.expire_all()
        self.assertEqual(self.call(learning.get_practice, COURSE, 'ch-02')['attempt'], saved)
        result = self.submit(saved)
        self.assertEqual(result['percent'], 100)
        self.assertEqual(len(self.call(learning.get_practice, COURSE, 'ch-02')['history']), 1)
        self.assertEqual(self.call(learning.get_practice, COURSE, 'ch-01')['history'], [])
        self.assertEqual(self.call(learning.get_course, COURSE)['progress']['history'], [])
        self.assert_status(403, lambda: self.start('final'))
        self.assertTrue(all(c['evidenceCount'] == 0 for c in self.insights('ch-01')['concepts']))
        self.call(learning.reset_results, COURSE, ResetRequest(confirm=True))
        for chapter in ['ch-01','ch-02']:
            self.assertIsNone(self.call(learning.get_practice, COURSE, chapter)['attempt'])
            self.assertTrue(all(c['evidenceCount'] == 0 for c in self.insights(chapter)['concepts']))

    def test_fresh_sets_exhaust_only_polynomial_bank_then_revision(self):
        seen = set()
        for _ in range(9):
            attempt = self.practice()
            ids = {q['id'] for q in attempt['questions']}
            self.assertFalse(seen & ids)
            self.assertTrue(all(id_.startswith('poly-v1-') for id_ in ids))
            seen |= ids
            self.submit(attempt)
        self.assertEqual(len(seen), 45)
        before = self.insights()
        revision = self.practice()
        self.assertEqual(revision['selection']['mode'], 'revision')
        self.submit(revision, correct=False)
        self.assertEqual(before, self.insights())
        self.assertEqual(self.practice('ch-01')['selection']['freshCount'], 5)
