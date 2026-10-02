import unittest
from uuid import UUID, uuid4
from unittest.mock import patch
import test_learning as fixture
from test_learning import COURSE
from app.models.tutorModel import DoubtTurn, SavedNote
from app.models.engagementModel import LearningEvent, ReadingProgress, AttemptTiming
from app.routers import tutor, learning
from app.schemas.tutor import DoubtRequest, FeedbackRequest, NoteRequest
from app.services.content_generation import GenerationError
from fastapi import HTTPException


class TutorTests(unittest.TestCase):
    def setUp(self):
        fixture.LearningTests.setUp(self)
        for model in (LearningEvent, ReadingProgress, AttemptTiming, DoubtTurn, SavedNote):
            model.__table__.create(self.engine)
        self.enabled = patch.object(learning.settings, 'tutor_enabled', True)
        self.enabled.start()

    def tearDown(self):
        self.enabled.stop()
        fixture.LearningTests.tearDown(self)

    call = fixture.LearningTests.call

    def ask(self):
        body = DoubtRequest(requestId=uuid4(), question='Explain Euclid’s division lemma')
        with patch.object(tutor, 'answer_question', return_value=('Divide a by b to obtain a = bq + r, with 0 ≤ r < b.', {'tokens': 20})) as provider:
            result = self.call(tutor.ask, COURSE, 'ch-01', body)
            source, tier, history, question = provider.call_args.args
            self.assertNotIn('questions', str(source))
            self.assertNotIn('finalQuestion', str(source))
            self.assertEqual(tier, 'default')
        return result, body

    def test_generation_persistence_redaction_and_retry(self):
        result, body = self.ask()
        self.assertEqual(result['status'], 'ready')
        with patch.object(tutor, 'answer_question') as provider:
            retried = self.call(tutor.ask, COURSE, 'ch-01', body)
            provider.assert_not_called()
        self.assertEqual(result['id'], retried['id'])
        self.assertEqual(len(self.call(tutor.history, COURSE, 'ch-01')['turns']), 1)
        self.assertEqual(self.call(tutor.history, COURSE, 'ch-01', user=self.other)['turns'], [])

    def test_feedback_flag_and_notes_are_owned_and_idempotent(self):
        result, _ = self.ask()
        turn_id = UUID(result['id'])
        for fn, args in ((tutor.feedback, (turn_id, FeedbackRequest(helpful=True))), (tutor.flag, (turn_id,)), (tutor.save_note, (NoteRequest(turnId=turn_id),))):
            with self.assertRaises(HTTPException) as caught:
                self.call(fn, *args, user=self.other)
            self.assertEqual(caught.exception.status_code, 404)
        self.call(tutor.feedback, turn_id, FeedbackRequest(helpful=True))
        self.call(tutor.flag, turn_id)
        self.call(tutor.flag, turn_id)
        self.assertEqual(self.db.query(LearningEvent).filter_by(event_type='REVIEW_REQUESTED').count(), 1)
        note = self.call(tutor.save_note, NoteRequest(turnId=turn_id))
        second = self.call(tutor.save_note, NoteRequest(turnId=turn_id))
        self.assertEqual(note['id'], second['id'])
        self.assertEqual(tutor.notes(db=self.db, user=self.user, offset=0)['notes'][0]['question'], result['question'])
        self.assertEqual(tutor.notes(db=self.db, user=self.other, offset=0)['notes'], [])
        with self.assertRaises(HTTPException):
            self.call(tutor.delete_note, UUID(note['id']), user=self.other)
        self.call(tutor.delete_note, UUID(note['id']))
        self.assertEqual(self.db.query(SavedNote).count(), 0)
        self.assertEqual(self.db.query(DoubtTurn).count(), 1)

    def test_provider_failure_is_saved_without_fake_answer_and_cannot_be_saved(self):
        body = DoubtRequest(requestId=uuid4(), question='Explain this chapter')
        with patch.object(tutor, 'answer_question', side_effect=GenerationError('provider_http_503')):
            result = self.call(tutor.ask, COURSE, 'ch-01', body)
        self.assertEqual(result['status'], 'failed')
        self.assertIsNone(result['answer'])
        with self.assertRaises(HTTPException):
            self.call(tutor.save_note, NoteRequest(turnId=UUID(result['id'])))

    def test_rate_limit_and_disabled_provider_do_not_call_api(self):
        for i in range(10):
            self.db.add(DoubtTurn(user_id=self.user.id, course_id=COURSE, chapter_id='ch-01', question=str(i), tier='default', status='failed'))
        self.db.commit()
        with patch.object(tutor, 'answer_question') as provider, self.assertRaises(HTTPException) as caught:
            self.call(tutor.ask, COURSE, 'ch-01', DoubtRequest(requestId=uuid4(), question='Another question'))
        self.assertEqual(caught.exception.status_code, 429)
        provider.assert_not_called()
        with patch.object(learning.settings, 'tutor_enabled', False), self.assertRaises(HTTPException) as caught:
            self.call(tutor.ask, COURSE, 'ch-01', DoubtRequest(requestId=uuid4(), question='Another question'))
        self.assertEqual(caught.exception.status_code, 503)
