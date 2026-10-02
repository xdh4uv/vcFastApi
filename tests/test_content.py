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
from app.services.content_generation import generate, request_lesson, GenerationError, validation_issues
from app.schemas.learning import ResetRequest
from scripts.seed_adaptive import read_bank

LESSON = {'summary': 'Prime factors reveal the structure of whole numbers.', 'sections': [
    {'title': 'Prime factorisation', 'explanation': ['Split a composite number into prime factors.'],
     'example': {'problem': 'Find the HCF and LCM of 84 and 126.', 'steps': ['84 = 2² × 3 × 7 and 126 = 2 × 3² × 7.', 'HCF = 42 and LCM = 252.']},
     'checkYourself': 'Find the HCF and LCM of 84 and 126.'},
    {'title': 'Common factors', 'explanation': ['The HCF uses the lowest shared prime powers.'],
     'example': {'problem': 'Find the HCF and LCM of 84 and 126.', 'steps': ['HCF uses the smaller shared powers.', 'HCF = 2 × 3 × 7 = 42.']},
     'checkYourself': 'Find the HCF and LCM of 84 and 126.'}],
    'takeaways': ['Factorisation ends at prime factors.', 'Use common prime powers to find the HCF.']}
for section in LESSON['sections']:
    section['example'] = deepcopy(baseline.CONTENT['chapters'][0]['example'])
    section['checkYourself'] = section['example']['problem']


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
        self.assertEqual(cached_lesson(self.db, baseline.COURSE, self.chapter, 'beginner')['status'], 'unavailable')
        with self.assertRaises(HTTPException) as caught:
            self.call(learning.get_content_generation, row.id)
        self.assertEqual(caught.exception.status_code, 404)
        from scripts.review_content import approve
        approve(self.db, row, self.source)
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
        from scripts.review_content import approve
        approve(self.db, self.create(tier='beginner')[0], self.source)
        approve(self.db, self.create(tier='advanced')[0], self.source)
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

    @patch('app.services.content_generation.requests.post')
    def test_groq_structured_lesson_and_invalid_configuration(self, post):
        post.return_value = Mock(status_code=200)
        post.return_value.json.return_value = {'choices': [{'message': {'content': json.dumps(LESSON)}, 'finish_reason': 'stop'}], 'usage': {}}
        raw, _, reason = request_lesson(self.source, 'beginner', 'openai/gpt-oss-120b', 'test-key',
            provider='openai-compatible', base_url='https://api.groq.com/openai/v1', output_mode='json_schema',
            reasoning_effort='medium', max_tokens=4096)
        self.assertEqual(json.loads(raw), LESSON)
        self.assertEqual(reason, 'end_turn')
        payload = post.call_args.kwargs['json']
        self.assertEqual(payload['max_completion_tokens'], 4096)
        self.assertEqual(payload['reasoning_effort'], 'medium')
        self.assertFalse(payload['include_reasoning'])
        self.assertTrue(payload['response_format']['json_schema']['strict'])
        self.assertNotIn('chat_template_kwargs', payload)
        post.reset_mock()
        for options in [{'stream': True, 'output_mode': 'json_schema'}, {'reasoning_effort': 'invalid'}, {'enable_thinking': False}]:
            with self.assertRaises(ValueError):
                request_lesson(self.source, 'beginner', 'openai/gpt-oss-120b', 'test-key',
                    provider='openai-compatible', base_url='https://api.groq.com/openai/v1', **options)
        with self.assertRaises(ValueError):
            request_lesson(self.source, 'beginner', 'unsupported-model', 'test-key', provider='openai-compatible',
                base_url='https://api.groq.com/openai/v1', reasoning_effort='medium')
        post.assert_not_called()

    def test_changed_source_and_prompt_do_not_serve_stale_versions(self):
        row, _ = self.create()
        row.verified = True
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
        with patch('app.services.content.PROMPT_VERSION', 'future-lesson-version'):
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
        row.verified = True
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
        with self.assertRaisesRegex(GenerationError, '^provider_timeout$'):
            request_lesson(self.source, 'beginner', 'test-model', 'secret')

    @patch('app.services.content_generation.requests.post')
    def test_stream_collects_answer_not_reasoning_and_keeps_usage(self, post):
        raw = json.dumps(LESSON)
        events = [
            {'choices': [{'index': 0, 'delta': {'reasoning_content': 'private reasoning'}}]},
            {'choices': [{'index': 0, 'delta': {'content': raw[:25]}}]},
            {'choices': [{'index': 0, 'delta': {'content': raw[25:]}, 'finish_reason': 'stop'}]},
            {'choices': [], 'usage': {'completion_tokens': 99, 'cost': 0, 'secret': 'ignore'}},
        ]
        response = Mock(status_code=200)
        response.iter_lines.return_value = [b': heartbeat'] + [b'data: ' + json.dumps(e).encode() for e in events] + [b'data: [DONE]']
        post.return_value = response
        result = request_lesson(self.source, 'advanced', 'nvidia/nemotron-3-ultra-550b-a55b', 'key',
            provider='openai-compatible', base_url='https://integrate.api.nvidia.com/v1', output_mode='text',
            stream=True, max_tokens=16384, read_timeout=180, temperature=1, top_p=.95, enable_thinking=True)
        self.assertEqual(result, (raw, {'completion_tokens': 99, 'cost': 0}, 'end_turn'))
        payload = post.call_args.kwargs['json']
        self.assertTrue(payload['stream'])
        self.assertEqual(payload['chat_template_kwargs'], {'enable_thinking': True})
        self.assertNotIn('response_format', payload)
        self.assertEqual(post.call_args.kwargs['timeout'], (10, 180))
        response.close.assert_called_once()

    @patch('app.services.content_generation.requests.post')
    def test_stream_rejects_overload_even_after_http_200(self, post):
        post.return_value = Mock(status_code=200)
        post.return_value.iter_lines.return_value = [b'data: {"error":{"message":"sensitive details","code":503}}']
        with self.assertRaisesRegex(GenerationError, '^provider_http_503$'):
            request_lesson(self.source, 'advanced', 'model', 'key', provider='openai-compatible',
                           base_url='https://integrate.api.nvidia.com/v1', stream=True)
        post.return_value.close.assert_called_once()

    @patch('app.services.content_generation.requests.post')
    def test_missing_done_truncation_and_refusal_are_not_success(self, post):
        for finish, refusal, done in [('stop', None, False), ('length', None, True), ('stop', 'no', True)]:
            event = {'choices': [{'delta': {'content': json.dumps(LESSON), 'refusal': refusal}, 'finish_reason': finish}]}
            response = Mock(status_code=200)
            response.iter_lines.return_value = [b'data: ' + json.dumps(event).encode()] + ([b'data: [DONE]'] if done else [])
            post.return_value = response
            raw, usage, reason = request_lesson(self.source, 'advanced', 'model', 'key', provider='openai-compatible',
                                               base_url='https://integrate.api.nvidia.com/v1', stream=True)
            failed, _ = self.create(provider=Mock(return_value=(raw, usage, reason)))
            self.assertEqual(failed.status, 'failed')
            self.assertEqual(failed.error_code, 'incomplete_or_refused')

    @patch('app.services.content_generation.requests.post')
    def test_stream_rejects_malformed_events_and_times_out(self, post):
        response = Mock(status_code=200)
        post.return_value = response
        response.iter_lines.return_value = [b'data: broken JSON']
        with self.assertRaisesRegex(GenerationError, '^invalid_provider_response$'):
            request_lesson(self.source, 'advanced', 'model', 'key', provider='openai-compatible',
                           base_url='https://integrate.api.nvidia.com/v1', stream=True)
        response.iter_lines.side_effect = requests.Timeout('secret details')
        with self.assertRaisesRegex(GenerationError, '^provider_timeout$'):
            request_lesson(self.source, 'advanced', 'model', 'key', provider='openai-compatible',
                           base_url='https://integrate.api.nvidia.com/v1', stream=True)

    def test_validation_diagnostics_and_request_options_cache_identity(self):
        bad = deepcopy(LESSON)
        bad['sections'][0]['example']['steps'] = ['Only one step']
        issues = validation_issues(json.dumps(bad))
        self.assertEqual(issues[0]['path'], ['sections', 0, 'example', 'steps'])
        self.assertNotIn('Only one step', json.dumps(issues))
        first, _ = generate(self.db, self.source, 'advanced', 'model', self.provider, request_options={'stream': True})
        second, _ = generate(self.db, self.source, 'advanced', 'model', self.provider, request_options={'stream': False})
        self.assertNotEqual(first.cache_key, second.cache_key)
        self.assertEqual(first.usage['request_options'], {'stream': True})
        self.assertEqual(first.usage['input_tokens'], 100)

    def test_quality_rejects_new_exercises_scope_and_markup(self):
        for field, value in [('checkYourself', 'If the product of zeroes of 2x²+bx−6 is −3, find b.'),
                             ('explanation', ['Use complex roots to solve this Class 10 problem.']),
                             ('explanation', ['Use \\(x^2\\) here.'])]:
            bad = deepcopy(LESSON)
            bad['sections'][0][field] = value
            issues = validation_issues(json.dumps(bad), self.source)
            self.assertTrue(issues)
            row, _ = self.create(provider=Mock(return_value=(json.dumps(bad), {}, 'end_turn')))
            self.assertEqual(row.status, 'failed')
            self.assertEqual(row.error_code, 'invalid_lesson')
            self.assertIsNone(row.content)

    def test_approval_rejects_stale_or_invalid_content(self):
        from scripts.review_content import approve
        row, _ = self.create()
        row.prompt_version = 'lesson-v2'
        with self.assertRaises(ValueError):
            approve(self.db, row, self.source)
        self.assertFalse(row.verified)
        row.prompt_version = 'lesson-v4'
        row.content = deepcopy(LESSON)
        row.content['sections'][0]['checkYourself'] = 'Unreviewed invented exercise'
        with self.assertRaises(ValueError):
            approve(self.db, row, self.source)
        self.assertFalse(row.verified)

    def test_worked_solution_is_authored_and_tampering_prevents_approval(self):
        from scripts.review_content import approve
        bad = deepcopy(LESSON)
        bad['sections'][0]['example']['steps'] = ['84 and 126 have no common factor.', 'HCF = 1.']
        row, _ = self.create(provider=Mock(return_value=(json.dumps(bad), {}, 'end_turn')))
        self.assertEqual(row.status, 'ready')
        self.assertEqual(row.content['sections'][0]['example'], self.source['chapter']['example'])
        self.assertIn('HCF = 1.', row.raw_response)
        row.content = bad
        with self.assertRaises(ValueError):
            approve(self.db, row, self.source)
        self.assertFalse(row.verified)
        row.verified = True
        self.db.commit()
        self.assertEqual(cached_lesson(self.db, baseline.COURSE, self.chapter, 'beginner')['status'], 'unavailable')
        with self.assertRaises(HTTPException) as caught:
            self.call(learning.get_content_generation, row.id)
        self.assertEqual(caught.exception.status_code, 503)

    def test_review_can_correct_unpublished_prose_but_cannot_change_a_reviewed_version(self):
        from scripts.review_content import approve
        row, _ = self.create()
        original = row.raw_response
        corrected = deepcopy(row.content)
        corrected['summary'] = 'Euclid’s division algorithm finds the HCF of positive integers.'
        approve(self.db, row, self.source, corrected)
        self.assertTrue(row.verified)
        self.assertEqual(row.raw_response, original)
        self.assertEqual(row.content['summary'], corrected['summary'])
        with self.assertRaises(ValueError):
            approve(self.db, row, self.source, corrected)

    def test_invalid_prose_can_be_repaired_but_provider_failure_cannot_be_approved(self):
        from scripts.review_content import approve
        bad = deepcopy(LESSON)
        bad['sections'][0]['checkYourself'] = 'Invented ambiguous exercise'
        row, _ = self.create(provider=Mock(return_value=(json.dumps(bad), {}, 'end_turn')))
        self.assertEqual(row.status, 'failed')
        approve(self.db, row, self.source, deepcopy(LESSON))
        self.assertTrue(row.verified)
        row.verified, row.status, row.error_code = False, 'failed', 'provider_timeout'
        with self.assertRaises(ValueError):
            approve(self.db, row, self.source, deepcopy(LESSON))

    @patch('app.services.content_generation.requests.post')
    def test_nim_options_cannot_leak_into_other_providers(self, post):
        for provider, endpoint in [('openai-compatible', 'https://openrouter.ai/api/v1'), ('anthropic', 'https://api.anthropic.com/v1')]:
            with self.assertRaises(ValueError):
                request_lesson(self.source, 'advanced', 'model', 'key', provider=provider, base_url=endpoint, enable_thinking=True)
        post.assert_not_called()
