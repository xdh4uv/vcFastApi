import json
import unittest
from unittest.mock import Mock, patch
from app.services import tutor
from app.services.content_generation import GenerationError

SOURCE = {'courseId': 'ncert-maths-10-v1', 'chapter': {'title': 'Polynomials'}, 'revisionCards': []}
ANSWER = 'The zeroes are 2 and 3. Substituting either value gives 0.'


class TutorAdapterTests(unittest.TestCase):
    def setUp(self):
        config = patch.multiple(tutor.settings, tutor_enabled=True, content_provider='openai-compatible',
                                content_api_base_url='https://integrate.api.nvidia.com/v1', content_model='test-model',
                                content_api_key='test-key', content_stream=False, content_enable_thinking=True,
                                content_temperature=1, tutor_enable_thinking=None, tutor_temperature=.2,
                                content_reasoning_effort=None, tutor_reasoning_effort=None,
                                tutor_read_timeout=45, tutor_max_tokens=1536)
        config.start()
        self.addCleanup(config.stop)
        self.post = patch.object(tutor.requests, 'post').start()
        self.addCleanup(patch.stopall)
        self.response = Mock(status_code=200)
        self.post.return_value = self.response
        self.respond(ANSWER)

    def respond(self, answer, reason='stop'):
        self.response.json.return_value = {'choices': [{'message': {'content': answer}, 'finish_reason': reason}], 'usage': {}}

    def ask(self):
        return tutor.answer_question(SOURCE, 'advanced', [], 'Find the zeroes of x² − 5x + 6.')

    def test_nim_tutor_has_separate_budget_and_disables_thinking(self):
        self.assertEqual(self.ask(), (ANSWER, {}))
        request = self.post.call_args.kwargs
        self.assertEqual(request['json']['chat_template_kwargs'], {'enable_thinking': False})
        self.assertEqual(request['json']['max_tokens'], 1536)
        self.assertEqual(request['json']['temperature'], .2)
        self.assertEqual(request['timeout'], (5, 45))
        self.assertTrue(tutor.settings.content_enable_thinking)
        self.response.close.assert_called_once()

    def test_unsupported_markup_or_incomplete_answer_is_not_served(self):
        for answer in ['<b>Answer</b>', r'\begin{matrix}1&2\end{matrix}', '[Answer](https://example.com)', '```python\nprint(2)\n```']:
            self.respond(answer)
            with self.assertRaisesRegex(GenerationError, '^invalid_tutor_format$'):
                self.ask()
        self.respond(ANSWER, 'length')
        with self.assertRaisesRegex(GenerationError, '^invalid_tutor_answer$'):
            self.ask()

    def test_harmless_formatting_is_normalized_without_another_provider_call(self):
        self.respond(r'**Not unique.** A monic quadratic with one zero 2 is \(p(x)=(x-2)(x-r)\). We need another condition.')
        answer, _ = self.ask()
        self.assertEqual(answer, 'Not unique. A monic quadratic with one zero 2 is p(x)=(x-2)(x-r). We need another condition.')
        self.post.assert_called_once()

    def test_non_nim_provider_does_not_inherit_nim_thinking(self):
        with patch.object(tutor.settings, 'content_api_base_url', 'https://openrouter.ai/api/v1'):
            self.ask()
        self.assertNotIn('chat_template_kwargs', self.post.call_args.kwargs['json'])
        with patch.multiple(tutor.settings, content_provider='anthropic', content_api_base_url='https://api.anthropic.com/v1', content_stream=True):
            self.response.json.return_value = {'content': [{'type': 'text', 'text': ANSWER}], 'stop_reason': 'end_turn', 'usage': {}}
            self.ask()
        self.assertEqual(self.post.call_args.args[0], 'https://api.anthropic.com/v1/messages')
        self.assertFalse(self.post.call_args.kwargs['stream'])

    def test_lesson_thinking_default_is_nim_only_and_explicit_override_is_preserved(self):
        with patch.object(tutor.settings, 'content_enable_thinking', None):
            self.assertFalse(tutor.settings.content_request_options['enable_thinking'])
            with patch.object(tutor.settings, 'content_api_base_url', 'https://openrouter.ai/api/v1'):
                self.assertIsNone(tutor.settings.content_request_options['enable_thinking'])
        self.assertTrue(tutor.settings.content_request_options['enable_thinking'])

    def test_stream_budget_includes_wait_for_response_headers(self):
        event = {'choices': [{'index': 0, 'delta': {'content': ANSWER}, 'finish_reason': 'stop'}]}
        self.response.iter_lines.return_value = [b'data: ' + json.dumps(event).encode(), b'data: [DONE]']
        with patch.object(tutor.settings, 'content_stream', True), patch.object(tutor.time, 'monotonic', side_effect=[0, 15, 15, 16, 17]):
            self.assertEqual(self.ask(), (ANSWER, {}))
        with patch.object(tutor.settings, 'content_stream', True), patch.object(tutor.time, 'monotonic', side_effect=[0, 46]):
            with self.assertRaisesRegex(GenerationError, '^provider_stream_timeout$'):
                self.ask()

    def test_provider_outage_remains_a_safe_failure(self):
        self.response.status_code = 503
        with self.assertRaisesRegex(GenerationError, '^provider_http_503$'):
            self.ask()
        self.post.assert_called_once()
        self.response.close.assert_called_once()

    def test_groq_gpt_oss_uses_explicit_reasoning_without_leaking_options(self):
        with patch.multiple(tutor.settings, content_api_base_url='https://api.groq.com/openai/v1',
                            content_model='openai/gpt-oss-120b', tutor_reasoning_effort='high'):
            self.assertEqual(self.ask(), (ANSWER, {}))
        payload = self.post.call_args.kwargs['json']
        self.assertEqual(payload['reasoning_effort'], 'high')
        self.assertFalse(payload['include_reasoning'])
        self.assertEqual(payload['max_completion_tokens'], 1536)
        self.assertNotIn('max_tokens', payload)
        self.assertNotIn('chat_template_kwargs', payload)
        self.ask()
        payload = self.post.call_args.kwargs['json']
        self.assertNotIn('reasoning_effort', payload)
        self.assertNotIn('include_reasoning', payload)

    def test_groq_math_wrappers_become_plain_text_in_one_request(self):
        self.respond(r'No unique polynomial: \(p_r(x)=(x-2)(x-r),\quad r\in\mathbb{R}\).')
        with patch.multiple(tutor.settings, content_api_base_url='https://api.groq.com/openai/v1',
                            content_model='openai/gpt-oss-120b'):
            answer, _ = self.ask()
        self.assertEqual(answer, 'No unique polynomial: p_r(x)=(x-2)(x-r),  r∈ℝ.')
        self.post.assert_called_once()
        self.response.close.assert_called_once()

    def test_groq_stream_ignores_reasoning_and_incomplete_answer_stays_rejected(self):
        events = [
            {'choices': [{'delta': {'reasoning': 'Internal analysis'}, 'finish_reason': None}]},
            {'choices': [{'delta': {'content': ANSWER}, 'finish_reason': 'stop'}]},
        ]
        self.response.iter_lines.return_value = [b'data: ' + json.dumps(event).encode() for event in events] + [b'data: [DONE]']
        with patch.multiple(tutor.settings, content_api_base_url='https://api.groq.com/openai/v1',
                            content_model='openai/gpt-oss-120b', content_stream=True):
            self.assertEqual(self.ask(), (ANSWER, {}))
            events[-1]['choices'][0]['finish_reason'] = 'length'
            self.response.iter_lines.return_value = [b'data: ' + json.dumps(event).encode() for event in events] + [b'data: [DONE]']
            with self.assertRaisesRegex(GenerationError, '^invalid_tutor_answer$'):
                self.ask()
        self.assertNotIn('reasoning_format', self.post.call_args.kwargs['json'])
