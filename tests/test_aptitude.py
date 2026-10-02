import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from fastapi import HTTPException
import test_learning as fixture
from test_learning import COURSE
from app.models.aptitudeModel import AptitudeProfile, Enrollment
from app.models.tutorModel import DoubtTurn, SavedNote
from app.models.engagementModel import ReadingProgress, LearningEvent, AttemptTiming
from app.services import aptitude
from app.services.access import require_course_access
from app.routers import learning, enrollment


class AptitudeTests(unittest.TestCase):
    def setUp(self):
        fixture.LearningTests.setUp(self)
        for model in (ReadingProgress, LearningEvent, AttemptTiming, DoubtTurn, SavedNote, Enrollment, AptitudeProfile):
            model.__table__.create(self.engine)
        self.flag = patch.object(learning.settings, 'engagement_enabled', True)
        self.flag.start()

    def tearDown(self):
        self.flag.stop()
        fixture.LearningTests.tearDown(self)

    call = fixture.LearningTests.call
    start = fixture.LearningTests.start
    submit = fixture.LearningTests.submit

    def test_cold_start_and_insufficient_evidence_stay_default(self):
        row = aptitude.recompute(self.db, self.user.id, COURSE)
        self.assertEqual(row.tier, 'default')
        self.assertEqual(row.evidence_count, 0)
        self.assertFalse(row.signals['eligible'])
        self.submit(self.start('ch-01'))
        self.assertEqual(aptitude.recompute(self.db, self.user.id, COURSE).tier, 'default')

    def test_retakes_do_not_inflate_evidence_and_reset_clears_test_signal(self):
        self.submit(self.start('ch-01'))
        first = aptitude.recompute(self.db, self.user.id, COURSE).signals['testEvidence']
        self.submit(self.start('ch-01'), correct=False)
        row = aptitude.recompute(self.db, self.user.id, COURSE)
        self.assertEqual(row.signals['testEvidence'], first)
        self.assertEqual(row.signals['testPerformance'], 1)
        from app.schemas.learning import ResetRequest
        self.call(learning.reset_results, COURSE, ResetRequest(confirm=True))
        row = self.db.get(AptitudeProfile, (self.user.id, COURSE))
        self.assertEqual(row.signals['testEvidence'], 0)
        self.assertEqual(row.tier, 'default')

    def test_percentile_extremes_ties_and_low_confidence(self):
        rows = []
        for user_id, score in ((self.user.id, .1), (self.other.id, .9)):
            row = AptitudeProfile(user_id=user_id, course_id=COURSE, score=score, confidence=.9, evidence_count=20, signals={'eligible': True})
            self.db.add(row); rows.append(row)
        self.db.flush()
        self.assertEqual(aptitude.assign(self.db, rows[0]).tier, 'beginner')
        self.assertEqual(aptitude.assign(self.db, rows[1]).tier, 'advanced')
        rows[0].score = rows[1].score = .5
        self.db.flush()
        self.assertEqual(aptitude.assign(self.db, rows[0]).tier, 'default')
        rows[0].signals = {'eligible': False}; rows[0].score = 1
        self.assertEqual(aptitude.assign(self.db, rows[0]).tier, 'default')

    def test_enrollment_is_idempotent_and_enforced_for_private_learning_routes(self):
        with self.assertRaises(HTTPException) as caught:
            require_course_access(self.db, self.user.id, COURSE)
        self.assertEqual(caught.exception.status_code, 403)
        self.call(enrollment.enroll, self.subject.sub_module_id)
        self.call(enrollment.enroll, self.subject.sub_module_id)
        self.assertEqual(self.db.query(Enrollment).count(), 1)
        require_course_access(self.db, self.user.id, COURSE)
        self.assertTrue(self.call(enrollment.subjects)[0]['enrolled'])
        self.assertFalse(self.call(enrollment.subjects, user=self.other)[0]['enrolled'])

    def test_five_signal_weights_and_nightly_batch(self):
        self.call(enrollment.enroll, self.subject.sub_module_id)
        self.call(enrollment.enroll, self.subject.sub_module_id, user=self.other)
        self.submit(self.start('ch-01'))
        self.db.add(ReadingProgress(user_id=self.user.id, course_id=COURSE, chapter_id='ch-01', source_key='0' * 64, sections={'concepts': 1000}))
        self.db.add(DoubtTurn(user_id=self.user.id, course_id=COURSE, chapter_id='ch-01', question='Why?', answer='Explanation', status='ready', tier='default', helpful=True))
        self.db.flush()
        row = aptitude.recompute(self.db, self.user.id, COURSE)
        self.assertAlmostEqual(row.score, .35 + .15 / 30 + .20 + .15 + .15)
        self.assertEqual(aptitude.recompute_all(self.db), 2)
        self.assertEqual(self.db.query(AptitudeProfile).count(), 2)
