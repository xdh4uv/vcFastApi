from datetime import datetime, timedelta, timezone
import json
import unittest
from unittest.mock import patch
from uuid import UUID
from pathlib import Path
from fastapi import HTTPException
import test_learning as baseline
from test_learning import COURSE
from test_content import LESSON
from test_adaptive import BANK
from app.models.aptitudeModel import AptitudeProfile, Enrollment
from app.models.contentModel import ContentGeneration
from app.models.engagementModel import LearningEvent, ReadingProgress, AttemptTiming
from app.models.learningCourseModel import LearningConcept, PracticeQuestion, LearningAttempt
from app.models.tutorModel import DoubtTurn, SavedNote
from app.routers import learning
from app.services.content import learning_depth, source_document
from app.services import automatic_lessons, aptitude
from app.services.content_generation import GenerationError


class ReleaseLearningTests(unittest.TestCase):
    call = baseline.LearningTests.call
    start = baseline.LearningTests.start
    submit = baseline.LearningTests.submit

    def setUp(self):
        baseline.LearningTests.setUp(self)
        for model in (Enrollment, AptitudeProfile, LearningEvent, ReadingProgress, AttemptTiming, DoubtTurn, SavedNote, ContentGeneration):
            model.__table__.create(self.engine)
        for c in BANK.concepts:
            self.db.add(LearningConcept(course_id=COURSE, chapter_id='ch-01', concept_id=c.id, material=c.model_dump()))
        for q in BANK.questions:
            self.db.add(PracticeQuestion(id=q.id, course_id=COURSE, chapter_id='ch-01', concept_id=q.conceptId,
                difficulty=q.difficulty, status='approved', content=q.model_dump()))
        self.db.commit()
        self.flags = patch.multiple(learning.settings, engagement_enabled=True, content_pipeline_enabled=True,
            automatic_lessons_enabled=True, tiered_tests_enabled=True, content_api_key='test-only',
            content_api_base_url='https://api.groq.com/openai/v1', content_model='openai/gpt-oss-120b',
            lesson_generations_per_day=12, lesson_requests_per_user_day=6)
        self.flags.start()
        self.chapter = learning.find_chapter(learning.load_course(self.db, COURSE), 'ch-01')
        self.source = source_document(self.db, COURSE, self.chapter)

    def tearDown(self):
        self.flags.stop()
        baseline.LearningTests.tearDown(self)

    def profile(self, tier):
        row = AptitudeProfile(user_id=self.user.id, course_id=COURSE, tier=tier, signals={'eligible': True})
        self.db.add(row); self.db.commit()
        return row

    def test_official_test_matches_tier_and_snapshot_survives_tier_change(self):
        row = self.profile('advanced')
        draft = self.start('ch-01')
        self.assertEqual(draft['selection']['tier'], 'advanced')
        self.assertEqual({q['difficulty'] for q in draft['questions']}, {'challenge'})
        self.assertEqual(len({q['conceptId'] for q in draft['questions']}), 5)
        row.tier = 'beginner'; self.db.commit()
        self.assertEqual(self.start('ch-01')['questions'], draft['questions'])
        self.assertEqual(self.submit(draft)['percent'], 100)
        row.tier, row.signals = 'beginner', {'eligible': True}
        self.db.commit()
        new = self.start('ch-01')
        self.assertEqual(new['selection']['tier'], 'beginner')

    def test_chapter_evidence_overrides_course_and_cold_start_stays_default(self):
        self.assertEqual(learning_depth(self.db, self.user.id, COURSE, 'ch-01', True, True)['tier'], 'default')
        self.profile('advanced')
        for _ in range(2):
            draft = self.start('ch-01')
            self.submit(draft, correct=False)
            # Restore eligible course signal to prove chapter precedence independently.
            row = self.db.get(AptitudeProfile, (self.user.id, COURSE))
            row.tier, row.signals = 'advanced', {'eligible': True}
            self.db.commit()
        depth = learning_depth(self.db, self.user.id, COURSE, 'ch-01', True, True)
        self.assertEqual((depth['tier'], depth['reason']), ('beginner', 'chapter-results'))

    def test_no_provider_call_for_default_or_duplicate_review_draft(self):
        with patch.object(automatic_lessons, 'request_lesson', return_value=(json.dumps(LESSON), {'total_tokens': 100}, 'end_turn')) as provider:
            result = automatic_lessons.request_variant(self.db, self.user.id, self.source, self.chapter, 'default')
            self.assertEqual(result['status'], 'available'); provider.assert_not_called()
            first = automatic_lessons.request_variant(self.db, self.user.id, self.source, self.chapter, 'beginner')
            second = automatic_lessons.request_variant(self.db, self.other.id, self.source, self.chapter, 'beginner')
            self.assertEqual(first['status'], 'awaiting-review')
            self.assertEqual(first['generationId'], second['generationId'])
            provider.assert_called_once()
            row = self.db.get(ContentGeneration, UUID(first['generationId']))
            self.assertFalse(row.verified)
            self.assertEqual(learning.cached_lesson(self.db, COURSE, self.chapter, 'beginner')['status'], 'unavailable')

    def test_failure_is_persisted_and_cooldown_prevents_repeat_calls(self):
        with patch.object(automatic_lessons, 'request_lesson', side_effect=GenerationError('provider_http_429')) as provider:
            result = automatic_lessons.request_variant(self.db, self.user.id, self.source, self.chapter, 'beginner')
            self.assertEqual(result['status'], 'failed')
            with self.assertRaises(HTTPException) as caught:
                automatic_lessons.request_variant(self.db, self.user.id, self.source, self.chapter, 'beginner')
            self.assertEqual(caught.exception.status_code, 429)
            self.assertEqual(provider.call_count, 1)
            self.assertIsNone(self.db.query(ContentGeneration).one().content)

    def test_global_budget_does_not_block_cache_reuse(self):
        with patch.object(learning.settings, 'lesson_generations_per_day', 1), patch.object(automatic_lessons, 'request_lesson', return_value=(json.dumps(LESSON), {}, 'end_turn')) as provider:
            first = automatic_lessons.request_variant(self.db, self.user.id, self.source, self.chapter, 'beginner')
            self.assertEqual(automatic_lessons.request_variant(self.db, self.other.id, self.source, self.chapter, 'beginner')['generationId'], first['generationId'])
            with self.assertRaises(HTTPException) as caught:
                automatic_lessons.request_variant(self.db, self.user.id, self.source, self.chapter, 'advanced')
            self.assertEqual(caught.exception.status_code, 429)
            self.assertEqual(provider.call_count, 1)

    def test_unrated_questions_are_not_counted_as_resolved(self):
        self.db.add_all([DoubtTurn(user_id=self.user.id, course_id=COURSE, chapter_id='ch-01', tier='default',
            question='Why?', answer='Answer', status='ready', helpful=True),
            DoubtTurn(user_id=self.user.id, course_id=COURSE, chapter_id='ch-01', tier='default', question='Explain?', status='failed')])
        self.db.flush()
        self.assertEqual(aptitude.calculate(self.db, self.user.id, COURSE).signals['questionResolution'], .5)

    def test_reading_activity_appears_in_course_state(self):
        self.db.add(ReadingProgress(user_id=self.user.id, course_id=COURSE, chapter_id='ch-01', source_key='a'*64, sections={'concepts': 3}))
        self.db.commit()
        course = self.call(learning.get_course, COURSE)
        self.assertEqual(course['chapters'][0]['readingState'], 'in-progress')
        self.call(learning.mark_read, COURSE, 'ch-01')
        self.assertEqual(self.call(learning.get_course, COURSE)['chapters'][0]['readingState'], 'completed')

    def test_generation_status_keeps_drafts_private_and_approval_enables_cache(self):
        self.profile('beginner')
        self.db.add(Enrollment(user_id=self.user.id, subject_id=self.subject.sub_module_id)); self.db.commit()
        with patch.object(automatic_lessons, 'request_lesson', return_value=(json.dumps(LESSON), {}, 'end_turn')):
            result = self.call(learning.request_explanation, COURSE, 'ch-01')
        status = self.call(learning.explanation_status, COURSE, 'ch-01')
        self.assertEqual(status, {'status': 'awaiting-review', 'generationId': result['generationId']})
        self.assertNotIn('content', status)
        with self.assertRaises(HTTPException):
            self.call(learning.get_content_generation, UUID(result['generationId']))
        row = self.db.get(ContentGeneration, UUID(result['generationId']))
        row.verified = True; self.db.commit()
        with patch.object(learning.settings, 'content_api_key', ''), patch.object(automatic_lessons, 'request_lesson') as provider:
            self.assertEqual(self.call(learning.request_explanation, COURSE, 'ch-01')['status'], 'available')
            provider.assert_not_called()
        self.assertEqual(self.call(learning.get_content_generation, row.id)['generated'], LESSON)

    def test_interrupted_request_recovers_durably_without_immediate_provider_retry(self):
        with patch.object(automatic_lessons, 'request_lesson', return_value=(json.dumps(LESSON), {}, 'end_turn')):
            automatic_lessons.request_variant(self.db, self.user.id, self.source, self.chapter, 'beginner')
        row = self.db.query(ContentGeneration).one()
        row.status, row.content = 'pending', None
        row.created_at = datetime.now(timezone.utc) - timedelta(hours=1)
        self.db.commit()
        with patch.object(automatic_lessons, 'request_lesson') as provider:
            with self.assertRaises(HTTPException) as caught:
                automatic_lessons.request_variant(self.db, self.user.id, self.source, self.chapter, 'beginner')
            self.assertEqual(caught.exception.status_code, 429)
            provider.assert_not_called()
        # The dependency's eventual session close must not undo stale recovery.
        self.db.rollback()
        self.assertEqual(self.db.get(ContentGeneration, row.id).status, 'failed')

    def test_advanced_mastery_progress_measures_remaining_distance(self):
        row = self.profile('advanced')
        row.score, row.confidence = .85, 1
        row.signals = {**{key: .5 for key in aptitude.WEIGHTS}, 'eligible': True}
        with patch.object(aptitude, 'thresholds', return_value=(.3, .7)):
            self.assertEqual(aptitude.profile_view(self.db, row)['progress'], 50)

    def test_every_chapter_has_a_complete_approved_test_at_each_tier(self):
        from app.schemas.adaptive import PracticeBank
        from app.services.adaptive import select_tier_questions
        data = Path(__file__).resolve().parents[1] / 'data'
        for path in sorted(data.glob('*practice-v1.json')):
            bank = PracticeBank.model_validate_json(path.read_text(encoding='utf-8'))
            if bank.chapterId == 'ch-01':
                continue
            for concept in bank.concepts:
                self.db.add(LearningConcept(course_id=COURSE, chapter_id=bank.chapterId, concept_id=concept.id, material=concept.model_dump()))
            for q in bank.questions:
                self.db.add(PracticeQuestion(id=q.id, course_id=COURSE, chapter_id=bank.chapterId,
                    concept_id=q.conceptId, difficulty=q.difficulty, status='approved', content=q.model_dump()))
        self.db.commit()
        course = learning.load_course(self.db, COURSE)
        self.assertEqual(len(course.chapters), 14)
        for chapter in course.chapters:
            for tier, difficulty in [('beginner','foundation'),('default','standard'),('advanced','challenge')]:
                questions, metadata = select_tier_questions(self.db, self.user.id, COURSE, chapter.id, tier)
                self.assertEqual(len(questions), 5, (chapter.id, tier))
                self.assertEqual(len({q['id'] for q in questions}), 5)
                self.assertEqual({q['difficulty'] for q in questions}, {difficulty})
                self.assertEqual(metadata['tier'], tier)
