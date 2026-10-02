import unittest
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4
from unittest.mock import patch
from fastapi import HTTPException
from pydantic import ValidationError
import test_learning as fixture
from test_learning import COURSE
from sqlalchemy import text
from app.models.aptitudeModel import AptitudeProfile, Enrollment
from app.models.tutorModel import DoubtTurn, SavedNote
from app.models.engagementModel import ReadingProgress, LearningEvent, AttemptTiming
from app.routers import learning, engagement
from app.schemas.engagement import ReadingUpdate, TimingUpdate
from app.schemas.learning import AnswerSubmission, ResetRequest


class EngagementTests(unittest.TestCase):
    def setUp(self):
        fixture.LearningTests.setUp(self)
        self.db.execute(text('PRAGMA foreign_keys=ON'))
        self.flag = patch.object(learning.settings, 'engagement_enabled', True)
        self.flag.start()
        for model in (ReadingProgress, LearningEvent, AttemptTiming, DoubtTurn, SavedNote, AptitudeProfile, Enrollment):
            model.__table__.create(self.engine)

    def tearDown(self):
        self.flag.stop()
        fixture.LearningTests.tearDown(self)

    call = fixture.LearningTests.call
    start = fixture.LearningTests.start

    def read(self, section='concepts', seconds=15, event_id=None):
        source = self.call(engagement.get_progress, COURSE, 'ch-01')
        row = self.db.get(ReadingProgress, (self.user.id, COURSE, 'ch-01'))
        if row:
            row.updated_at = datetime.now(timezone.utc) - timedelta(seconds=30)
            self.db.flush()
        body = ReadingUpdate(eventId=event_id or uuid4(), sourceKey=source['sourceKey'], section=section, seconds=seconds)
        return self.call(engagement.save_progress, COURSE, 'ch-01', body), body

    def test_initial_open_claims_no_time_then_completion_persists(self):
        first, _ = self.read(seconds=0)
        self.assertEqual(first['percent'], 0)
        for section in ('concepts', 'example', 'watch-for'):
            result, _ = self.read(section)
        self.assertEqual(result['percent'], 100)
        self.assertTrue(result['testReady'])
        self.db.expire_all()
        self.assertEqual(self.call(engagement.get_progress, COURSE, 'ch-01')['percent'], 100)
        self.assertEqual(self.db.query(LearningEvent).filter_by(event_type='CHAPTER_COMPLETED').count(), 1)

    def test_idempotency_and_owner_isolation(self):
        self.read(seconds=0)
        first, body = self.read()
        retry = self.call(engagement.save_progress, COURSE, 'ch-01', body)
        self.assertEqual(first, retry)
        self.assertEqual(self.call(engagement.get_progress, COURSE, 'ch-01', user=self.other)['percent'], 0)
        with self.assertRaises(HTTPException) as caught:
            self.call(engagement.save_progress, COURSE, 'ch-01', body, user=self.other)
        self.assertEqual(caught.exception.status_code, 409)

    def test_clock_caps_credit_and_rejects_invalid_sections_stale_content(self):
        self.read(seconds=0)
        source = self.call(engagement.get_progress, COURSE, 'ch-01')
        for key, section in ((source['sourceKey'], 'forged'), ('0' * 64, 'concepts')):
            with self.assertRaises(HTTPException):
                self.call(engagement.save_progress, COURSE, 'ch-01', ReadingUpdate(eventId=uuid4(), sourceKey=key, section=section, seconds=30))
        result = self.call(engagement.save_progress, COURSE, 'ch-01', ReadingUpdate(eventId=uuid4(), sourceKey=source['sourceKey'], section='concepts', seconds=30))
        self.assertLess(result['seconds']['concepts'], 3)
        with self.assertRaises(ValidationError):
            ReadingUpdate(eventId=uuid4(), sourceKey=source['sourceKey'], section='concepts', seconds=1000)

    def test_question_timing_is_snapshot_scoped_and_submit_logs_once(self):
        attempt = self.start('ch-01')
        timing = self.db.get(AttemptTiming, UUID(attempt['id']))
        timing.updated_at = datetime.now(timezone.utc) - timedelta(seconds=30)
        self.db.flush()
        body = TimingUpdate(eventId=uuid4(), questionId=attempt['questions'][0]['id'], seconds=15)
        self.call(engagement.save_timing, COURSE, UUID(attempt['id']), body)
        self.call(engagement.save_timing, COURSE, UUID(attempt['id']), body)
        self.assertEqual(timing.seconds[body.questionId], 15)
        with self.assertRaises(HTTPException):
            self.call(engagement.save_timing, COURSE, UUID(attempt['id']), body, user=self.other)
        result = fixture.LearningTests.submit(self, attempt)
        self.call(learning.submit_attempt, COURSE, UUID(attempt['id']), AnswerSubmission(answers=result['answers'], revision=0))
        events = self.db.query(LearningEvent).filter_by(event_type='TEST_COMPLETED').all()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].payload['questionSeconds'][body.questionId], 15)
        self.read(seconds=0)
        self.call(learning.reset_results, COURSE, ResetRequest(confirm=True))
        self.assertEqual(self.db.query(LearningEvent).filter_by(event_type='TEST_COMPLETED').count(), 0)
        self.assertEqual(self.db.query(AttemptTiming).count(), 0)
        self.assertEqual(self.db.query(ReadingProgress).count(), 1)
