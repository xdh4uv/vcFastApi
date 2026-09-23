import json
from copy import deepcopy
from unittest.mock import Mock, patch
import unittest

from fastapi import HTTPException
import requests
import test_learning as baseline
from app.models.contentModel import ContentGeneration
from app.models.learningCourseModel import LearningCourse, LearningConcept, PracticeQuestion
from app.routers import learning
from app.services.content import cached_lesson, digest, source_document, explanation_depth
from app.services.content_generation import generate, request_lesson, GenerationError
from app.schemas.learning import ResetRequest
from scripts.seed_adaptive import read_bank

LESSON = {'summary': 'Prime factors reveal the structure of whole numbers.', 'sections': [
    {'title': 'Prime factorisation', 'explanation': ['Split a composite number into prime factors.'],
     'example': {'problem': 'Factorise 12.', 'steps': ['12 = 2 × 6.', '6 = 2 × 3, so 12 = 2² × 3.']},
     'checkYourself': 'Factorise 18.'},
    {'title': 'Common factors', 'explanation': ['The HCF uses the lowest shared prime powers.'],
     'example': {'problem': 'Find HCF(12, 18).', 'steps': ['12 = 2² × 3 and 18 = 2 × 3².', 'HCF = 2 × 3 = 6.']},
     'checkYourself': 'Find HCF(8, 12).'}],
    'takeaways': ['Factorisation ends at prime factors.', 'Use common prime powers to find the HCF.']}


class ContentTests(unittest.TestCase):
    call = baseline.LearningTests.call
    tearDown = baseline.LearningTests.tearDown
    start = baseline.LearningTests.start
    submit = baseline.LearningTests.submit

    def setUp(self):
        baseline.LearningTests.setUp(self)
        flag = patch('app.routers.learning.settings.content_pipeline_enabled', True)
        flag.start()
        self.addCleanup(flag.stop)
        ContentGeneration.__table__.create(self.engine)
        self.chapter = learning.find_chapter(learning.load_course(self.db, baseline.COURSE), 'ch-01')
        self.source = source_document(self.db, baseline.COURSE, self.chapter)
        self.provider = Mock(return_value=(json.dumps(LESSON), {'input_tokens': 100, 'output_tokens': 200}, 'end_turn'))

    def test_disabled_rollout_reads_base_without_cache_table(self):
        self.db.commit()
        ContentGeneration.__table__.drop(self.engine)
        with patch('app.routers.learning.settings.content_pipeline_enabled', False):
            self.assertIsNone(self.call(learning.get_chapter, baseline.COURSE, 'ch-01')['contentVariant'])

    def create(self, tier='beginner', model='test-model', provider=None):
        return generate(self.db, self.source, tier, model, provider or self.provider)

    def test_identity_persisted_before_call_and_cache_reused_across_students(self):
        def provider(*args):
            pending = self.db.query(ContentGeneration).one()
            self.assertEqual(pending.status, 'pending')
            self.assertIsNotNone(pending.id)
            return self.provider(*args)
        row, called = self.create(provider=provider)
        self.assertTrue(called)
        self.assertEqual(row.status, 'ready')
        self.assertFalse(row.verified)
        self.assertEqual(row.usage['output_tokens'], 200)
        self.assertEqual(self.create()[0].id, row.id)
        self.provider.assert_called_once()
        for user in [self.user, self.other]:
            data = self.call(learning.get_content_generation, row.id, user=user)
            self.assertEqual(data['id'], str(row.id))
            self.assertNotIn('raw_response', json.dumps(data))
            self.assertNotIn('questions', json.dumps(data))
        detail = self.call(learning.get_content_generation, row.id)
        self.assertEqual(detail['generated'], LESSON)
        self.assertNotIn('source', detail)

    def test_automatic_depth_uses_distinct_evidence_per_student_and_reset(self):
        bank = read_bank()
        for c in bank.concepts:
            self.db.add(LearningConcept(course_id=baseline.COURSE, chapter_id='ch-01', concept_id=c.id, material=c.model_dump()))
        for q in bank.questions:
            self.db.add(PracticeQuestion(id=q.id, course_id=baseline.COURSE, chapter_id='ch-01', concept_id=q.conceptId,
                                        difficulty=q.difficulty, status='approved', content=q.model_dump()))
        self.db.commit()
        self.source = source_document(self.db, baseline.COURSE, self.chapter)
        self.create(tier='beginner')
        self.create(tier='advanced')
        self.submit(self.start('ch-01'), correct=False)
        self.submit(self.start('ch-01'), correct=False)
        self.assertEqual(self.call(learning.get_chapter, baseline.COURSE, 'ch-01')['contentVariant']['selection']['evidenceCount'], 5)
        self.submit(self.call(learning.start_practice, baseline.COURSE, 'ch-01'), correct=False)
        # Practice targets weak concepts; add fresh sets until all concepts have evidence and total >= 10.
        variant = self.call(learning.get_chapter, baseline.COURSE, 'ch-01')['contentVariant']
        self.assertEqual(variant['requestedTier'], 'beginner')
        self.assertEqual(variant['servedTier'], 'beginner')
        self.assertEqual(self.call(learning.get_chapter, baseline.COURSE, 'ch-01', user=self.other)['contentVariant']['requestedTier'], 'default')
        self.submit(self.start('ch-01', user=self.other), user=self.other)
        self.submit(self.call(learning.start_practice, baseline.COURSE, 'ch-01', user=self.other), user=self.other)
        self.assertEqual(self.call(learning.get_chapter, baseline.COURSE, 'ch-01', user=self.other)['contentVariant']['servedTier'], 'advanced')
        self.call(learning.reset_results, baseline.COURSE, ResetRequest(confirm=True))
        self.assertEqual(self.call(learning.get_chapter, baseline.COURSE, 'ch-01')['contentVariant']['requestedTier'], 'default')

    @patch('app.services.content.load_insights')
    def test_depth_thresholds_require_coverage(self, insights):
        for correct, expected in [(5, 'beginner'), (6, 'default'), (7, 'default'), (8, 'advanced')]:
            insights.return_value = ({'concepts': [{'evidenceCount': 5, 'correct': min(correct, 5)},
                                                 {'evidenceCount': 5, 'correct': max(0, correct - 5)}]}, [])
            self.assertEqual(explanation_depth(self.db, self.user.id, baseline.COURSE, 'ch-01', True)['tier'], expected)
        insights.return_value = ({'concepts': [{'evidenceCount': 10, 'correct': 10}, {'evidenceCount': 0, 'correct': 0}]}, [])
        self.assertEqual(explanation_depth(self.db, self.user.id, baseline.COURSE, 'ch-01', True)['tier'], 'default')

    @patch('app.services.content_generation.requests.post')
    def test_openai_compatible_nim_and_openrouter_adapters(self, post):
        post.return_value = Mock(status_code=200)
        post.return_value.json.return_value = {'choices': [{'message': {'content': json.dumps(LESSON)}, 'finish_reason': 'stop'}],
                                             'usage': {'prompt_tokens': 50, 'completion_tokens': 100, 'cost': 0.0}}
        for endpoint in ['https://openrouter.ai/api/v1', 'https://integrate.api.nvidia.com/v1']:
            for mode in ['json_object', 'json_schema', 'text']:
                raw, usage, reason = request_lesson(self.source, 'advanced', 'chosen-model', 'private-key',
                    provider='openai-compatible', base_url=endpoint, output_mode=mode)
                self.assertEqual(json.loads(raw), LESSON)
                self.assertEqual(reason, 'end_turn')
                self.assertEqual(post.call_args.args[0], endpoint + '/chat/completions')
                args = post.call_args.kwargs
                self.assertEqual(args['headers']['Authorization'], 'Bearer private-key')
                self.assertEqual('response_format' in args['json'], mode != 'text')
                self.assertEqual(usage['completion_tokens'], 100)
        before = post.call_count
        with self.assertRaises(ValueError):
            request_lesson(self.source, 'advanced', 'model', 'secret', provider='openai-compatible', base_url='http://example.com/v1')
        self.assertEqual(before, post.call_count)
        request_lesson(self.source, 'advanced', 'chosen-openai-model', 'key', provider='openai', base_url='https://api.openai.com/v1')
        self.assertIn('max_completion_tokens', post.call_args.kwargs['json'])
        self.assertNotIn('max_tokens', post.call_args.kwargs['json'])

    def test_default_and_missing_variants_use_base_without_generation(self):
        for tier, status in [('default', 'base'), ('advanced', 'unavailable')]:
            view = cached_lesson(self.db, baseline.COURSE, self.chapter, tier)
            self.assertEqual(view['status'], status)
            self.assertEqual(view['servedTier'], 'default')
        self.assertEqual(self.db.query(ContentGeneration).count(), 0)
        self.provider.assert_not_called()

    def test_changed_source_and_prompt_do_not_serve_stale_versions(self):
        row, _ = self.create()
        source = self.db.get(LearningCourse, baseline.COURSE)
        edited = deepcopy(source.content)
        edited['chapters'][0]['goal'] = 'Revised chapter goal'
        source.content = edited
        self.db.commit()
        chapter = learning.find_chapter(learning.load_course(self.db, baseline.COURSE), 'ch-01')
        self.assertEqual(cached_lesson(self.db, baseline.COURSE, chapter, 'beginner')['status'], 'unavailable')
        with self.assertRaises(HTTPException) as caught:
            self.call(learning.get_content_generation, row.id)
        self.assertEqual(caught.exception.status_code, 410)
        with patch('app.services.content.PROMPT_VERSION', 'lesson-v2'):
            self.assertEqual(cached_lesson(self.db, baseline.COURSE, self.chapter, 'beginner')['status'], 'unavailable')

    def test_tier_model_and_source_are_distinct_cache_keys(self):
        one, _ = self.create()
        two, _ = self.create(tier='advanced')
        three, _ = self.create(model='second-model')
        self.assertEqual(len({one.cache_key, two.cache_key, three.cache_key}), 3)
        self.assertEqual(digest(self.source), one.source_hash)
        self.assertNotIn('questions', json.dumps(self.source))
        self.assertNotIn('finalQuestion', json.dumps(self.source))
        self.assertNotIn(self.user.email, json.dumps(self.source))

    def test_invalid_truncated_refused_outputs_stay_unpublished_with_usage(self):
        for raw, reason, code in [('not json', 'end_turn', 'invalid_lesson'),
                                  (json.dumps(LESSON), 'max_tokens', 'incomplete_or_refused'),
                                  ('', 'refusal', 'incomplete_or_refused'),
                                  ('{}', 'end_turn', 'invalid_lesson')]:
            row, _ = self.create(provider=Mock(return_value=(raw, {'output_tokens': 2}, reason)))
            self.assertEqual(row.status, 'failed')
            self.assertEqual(row.error_code, code)
            self.assertEqual(row.raw_response, raw)
            self.assertEqual(row.usage['output_tokens'], 2)
            self.assertEqual(cached_lesson(self.db, baseline.COURSE, self.chapter, 'beginner')['status'], 'unavailable')
        self.assertEqual(self.db.query(ContentGeneration).count(), 4)

    def test_provider_failure_preserved_and_explicit_retry_gets_new_id(self):
        failed, _ = self.create(provider=Mock(side_effect=GenerationError('provider_http_429')))
        success, _ = self.create()
        self.assertNotEqual(failed.id, success.id)
        self.assertEqual(failed.error_code, 'provider_http_429')
        self.assertEqual(success.status, 'ready')

    def test_pending_job_blocks_duplicate_paid_call(self):
        row, _ = self.create()
        row.status = 'pending'
        self.db.commit()
        self.provider.reset_mock()
        reused, called = self.create()
        self.assertFalse(called)
        self.assertEqual(reused.id, row.id)
        self.provider.assert_not_called()

    def test_corrupt_ready_document_falls_back(self):
        row, _ = self.create()
        row.content = {'summary': 'broken'}
        self.db.commit()
        self.assertEqual(cached_lesson(self.db, baseline.COURSE, self.chapter, 'beginner')['status'], 'unavailable')

    @patch('app.services.content_generation.requests.post')
    def test_provider_contract_timeout_and_redaction(self, post):
        post.return_value = Mock(status_code=200)
        post.return_value.json.return_value = {'content': [{'type': 'text', 'text': json.dumps(LESSON)}],
            'usage': {'input_tokens': 5, 'output_tokens': 8}, 'stop_reason': 'end_turn'}
        raw, usage, reason = request_lesson(self.source, 'beginner', 'test-model', 'secret')
        self.assertEqual(json.loads(raw), LESSON)
        self.assertEqual(reason, 'end_turn')
        args = post.call_args.kwargs
        self.assertEqual(args['timeout'], (10, 90))
        self.assertFalse(args['allow_redirects'])
        self.assertEqual(args['json']['output_config']['format']['type'], 'json_schema')
        self.assertNotIn('finalQuestion', json.dumps(args['json']))
        post.return_value.status_code = 429
        with self.assertRaisesRegex(GenerationError, 'provider_http_429'):
            request_lesson(self.source, 'beginner', 'test-model', 'secret')
        post.side_effect = requests.Timeout('sensitive request details')
        with self.assertRaisesRegex(GenerationError, '^provider_connection_failed$'):
            request_lesson(self.source, 'beginner', 'test-model', 'secret')
