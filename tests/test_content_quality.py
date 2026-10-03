import unittest
from copy import deepcopy

from app.services.content_quality import quality_issues, scope_rules

SOURCE = {'courseId': 'ncert-maths-10-v1', 'chapter': {'id': 'ch-02', 'example': {'problem': 'Find the zeroes of x² − 1.', 'steps': ['Factorise.', 'Zeroes are −1 and 1.']}}, 'revisionCards': []}
LESSON = {'summary': 'Polynomials', 'sections': [{'title': 'Zeroes', 'explanation': ['Use factorisation.'], 'example': SOURCE['chapter']['example'], 'checkYourself': SOURCE['chapter']['example']['problem']}], 'takeaways': ['A quadratic has at most two distinct real zeroes.']}


class ContentQualityTests(unittest.TestCase):
    def test_generated_self_checks_use_authored_problems_without_weakening_scope_checks(self):
        from app.services.content_quality import use_authored_examples
        from test_content import LESSON as complete_lesson
        from test_learning import CONTENT
        complete_source = {'courseId': CONTENT['id'], 'chapter': CONTENT['chapters'][0], 'revisionCards': []}
        lesson = deepcopy(complete_lesson)
        lesson['sections'][0]['checkYourself'] = 'Invented exercise with different numbers.'
        normalized = use_authored_examples(lesson, complete_source)
        self.assertEqual(normalized['sections'][0]['checkYourself'], normalized['sections'][0]['example']['problem'])
        self.assertEqual(quality_issues(normalized, complete_source), [])
        normalized['sections'][0]['explanation'] = ['Use complex numbers.']
        self.assertIn('out_of_scope', {issue['type'] for issue in quality_issues(normalized, complete_source)})

    def test_known_scaling_error_and_unqualified_graph_claim_cannot_be_approved(self):
        for text, kind in [('Multiplying by any nonzero constant a yields a non-monic quadratic.', 'invalid_scaling_claim'),
                           ('A repeated zero means the graph touches and does not cross.', 'unqualified_repeated_zero')]:
            lesson = deepcopy(LESSON)
            lesson['takeaways'] = [text]
            self.assertIn(kind, {issue['type'] for issue in quality_issues(lesson, SOURCE)})

    def test_correctly_qualified_claims_pass(self):
        lesson = deepcopy(LESSON)
        lesson['takeaways'] = ['Multiplying by any nonzero constant other than 1 produces a non-monic quadratic.',
                               'A repeated quadratic zero touches the axis rather than crossing it.']
        self.assertEqual(quality_issues(lesson, SOURCE), [])
        self.assertIn('not 1', scope_rules(SOURCE))

    def test_polynomials_does_not_pull_methods_from_quadratic_equations(self):
        lesson = deepcopy(LESSON)
        lesson['sections'][0]['explanation'] = ['Apply the quadratic formula and discriminant.']
        self.assertIn('out_of_scope', {issue['type'] for issue in quality_issues(lesson, SOURCE)})
