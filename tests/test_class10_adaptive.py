import unittest
from collections import Counter
from fractions import Fraction
from uuid import UUID

import test_learning as baseline
from class10_answer_keys import ANSWERS
from app.models.learningCourseModel import LearningConcept, PracticeQuestion
from app.routers import learning
from app.schemas.learning import AnswerSubmission, ResetRequest
from scripts.seed_adaptive import BANKS, read_bank
from scripts.build_class10_banks import build_all

ALL = [read_bank(name) for name in BANKS]
COURSE = ALL[0].courseId


class AllChapterTests(unittest.TestCase):
    call = baseline.LearningTests.call
    start = baseline.LearningTests.start
    submit = baseline.LearningTests.submit
    assert_status = baseline.LearningTests.assert_status
    tearDown = baseline.LearningTests.tearDown

    def setUp(self):
        baseline.LearningTests.setUp(self)
        for bank in ALL:
            for c in bank.concepts:
                self.db.add(LearningConcept(course_id=COURSE,chapter_id=bank.chapterId,concept_id=c.id,material=c.model_dump()))
            for q in bank.questions:
                self.db.add(PracticeQuestion(id=q.id,course_id=COURSE,chapter_id=bank.chapterId,concept_id=q.conceptId,
                                            difficulty=q.difficulty,status='approved',content=q.model_dump()))
        self.db.commit()

    def practice(self, chapter):
        return self.call(learning.start_practice,COURSE,chapter)

    def insights(self, chapter):
        return self.call(learning.get_insights,COURSE,chapter)

    def test_all_chapters_content_coverage_keys_and_legacy_mapping(self):
        self.assertEqual({b.chapterId for b in ALL},{c['id'] for c in baseline.CONTENT['chapters']})
        all_ids = [q.id for bank in ALL for q in bank.questions]
        self.assertEqual(len(all_ids),630)
        self.assertEqual(len(set(all_ids)),630)
        generated = {b['chapterId']:b for b in build_all()}
        for bank, chapter in zip(ALL,baseline.CONTENT['chapters']):
            with self.subTest(chapter=bank.chapterId):
                self.assertEqual(bank.chapterId,chapter['id'])
                self.assertEqual(len(bank.concepts),5)
                counts = Counter((q.conceptId,q.difficulty) for q in bank.questions)
                self.assertEqual(len(counts),15)
                self.assertEqual(set(counts.values()),{3})
                self.assertEqual(len({q.prompt for q in bank.questions}),45)
                aliases = {label:c.id for c in bank.concepts for label in c.legacyLabels}
                self.assertTrue(all(q['concept'] in aliases for q in chapter['questions']))
                if bank.chapterId in generated:
                    self.assertEqual(bank.model_dump(),generated[bank.chapterId])
                    keys = [answer for row in ANSWERS[int(bank.chapterId[-2:])] for answer in row.split('|')]
                    self.assertEqual(len(keys),45)
                    for q,expected in zip(bank.questions,keys):
                        self.assertEqual(q.options[q.answer],expected,q.id)

    def test_probability_distractors_are_valid_probabilities(self):
        for q in ALL[-1].questions:
            if 'P(' in q.prompt and 'How many' not in q.prompt:
                self.assertTrue(all(0 <= Fraction(option) <= 1 for option in q.options),q.id)

    def test_every_baseline_feeds_only_its_own_chapter_and_repeats_do_not_inflate(self):
        before = {b.chapterId:self.insights(b.chapterId) for b in ALL}
        for bank,chapter in zip(ALL,baseline.CONTENT['chapters']):
            with self.subTest(chapter=bank.chapterId):
                self.submit(self.start(bank.chapterId),correct=False)
                now = self.insights(bank.chapterId)
                aliases = {label:c.id for c in bank.concepts for label in c.legacyLabels}
                expected = Counter(aliases[q['concept']] for q in chapter['questions'])
                for c in now['concepts']:
                    self.assertEqual(c['evidenceCount'],expected[c['id']])
                    if c['evidenceCount']:
                        self.assertEqual(c['nextDifficulty'],'foundation')
                self.submit(self.start(bank.chapterId),correct=True)
                self.assertEqual(now,self.insights(bank.chapterId))
                self.assertEqual(self.call(learning.get_test,COURSE,bank.chapterId)['insights'],now)
                before[bank.chapterId]=now
                for other in ALL:
                    self.assertEqual(before[other.chapterId],self.insights(other.chapterId))

    def test_every_chapter_draft_grading_and_final_gate(self):
        for bank in ALL:
            with self.subTest(chapter=bank.chapterId):
                self.assertTrue(self.call(learning.get_chapter,COURSE,bank.chapterId)['adaptiveAvailable'])
                a = self.practice(bank.chapterId)
                self.assertEqual(a['id'],self.practice(bank.chapterId)['id'])
                self.assertTrue(all('answer' not in q and 'explanation' not in q for q in a['questions']))
                self.assertTrue({q['id'] for q in a['questions']} <= {q.id for q in bank.questions})
                saved=self.call(learning.save_draft,COURSE,UUID(a['id']),AnswerSubmission(answers={a['questions'][0]['id']:0},revision=0))
                self.db.expire_all()
                self.assertEqual(saved,self.call(learning.get_practice,COURSE,bank.chapterId)['attempt'])
                result=self.submit(saved)
                self.assertEqual(result['percent'],100)
                self.assertEqual(result['insights']['chapterId'],bank.chapterId)
        self.assertEqual(self.call(learning.get_course,COURSE)['progress']['history'],[])
        self.assert_status(403,lambda:self.start('final'))
        for bank in ALL[:-1]: self.submit(self.start(bank.chapterId))
        self.assert_status(403,lambda:self.start('final'))
        self.submit(self.start(ALL[-1].chapterId))
        self.assertEqual(self.submit(self.start('final'))['total'],14)
        self.call(learning.mark_read,COURSE,'ch-14')
        self.call(learning.reset_results,COURSE,ResetRequest(confirm=True))
        self.assert_status(403,lambda:self.start('final'))
        for bank in ALL:
            self.assertEqual(self.call(learning.get_practice,COURSE,bank.chapterId)['history'],[])
            self.assertTrue(all(c['evidenceCount']==0 for c in self.insights(bank.chapterId)['concepts']))
        self.assertIn('ch-14',self.call(learning.get_course,COURSE)['progress']['read'])

    def test_fresh_exhaustion_and_revision_for_every_new_bank(self):
        for bank in ALL[2:]:
            with self.subTest(chapter=bank.chapterId):
                seen=set()
                for _ in range(9):
                    a=self.practice(bank.chapterId)
                    ids={q['id'] for q in a['questions']}
                    self.assertEqual(len(ids),5)
                    self.assertFalse(seen & ids)
                    seen |= ids
                    self.submit(a)
                self.assertEqual(seen,{q.id for q in bank.questions})
                before=self.insights(bank.chapterId)
                repeat=self.practice(bank.chapterId)
                self.assertEqual(repeat['selection']['mode'],'revision')
                self.submit(repeat,correct=False)
                self.assertEqual(before,self.insights(bank.chapterId))
