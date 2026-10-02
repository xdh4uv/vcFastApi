import unittest

from app.services.tutor_text import normalize_answer


class TutorTextTests(unittest.TestCase):
    def test_math_notation_keeps_precedence_signs_and_conditions(self):
        self.assertEqual(normalize_answer(r'\[x^2+\frac{-b+\sqrt{b^2-4ac}}{2a}\]'), 'x²+(-b+√(b²-4ac))/(2a)')
        self.assertEqual(normalize_answer(r'$a\neq 0$, $r\times s=\frac{c}{a}$'), 'a≠ 0, r× s=(c)/(a)')
        self.assertEqual(normalize_answer(r'\frac{1}{\frac{2}{3}}'), '(1)/((2)/(3))')

    def test_markdown_decoration_becomes_plain_text(self):
        self.assertEqual(normalize_answer('# Answer\n**Zeroes:** `2` and *3*.'), 'Answer\nZeroes: 2 and 3.')
        self.assertEqual(normalize_answer('```text\nx² − 5x + 6\n```'), 'x² − 5x + 6')

    def test_plain_multiplication_inequality_and_subscripts_are_preserved(self):
        for text in ['x * y * z', '> 0', 'a_1 + a_2', 'x² − 5x + 6']:
            self.assertEqual(normalize_answer(text), text)

    def test_unsupported_maths_and_html_are_rejected(self):
        for text in [r'\frac12', r'\sqrt[3]{8}', r'\begin{cases}x=1\end{cases}', '<script>alert(1)</script>', '**', '']:
            with self.assertRaises(ValueError):
                normalize_answer(text)

    def test_real_number_set_membership_keeps_conditions_and_negation(self):
        self.assertEqual(normalize_answer(r'\(p_r(x)=(x-2)(x-r),\quad r\in\mathbb{R}\)'),
                         'p_r(x)=(x-2)(x-r),  r∈ℝ')
        self.assertEqual(normalize_answer(r'\(\sqrt{2}\notin\mathbb{Q}\)'), '√(2)∉ℚ')
        self.assertEqual(normalize_answer(r'\(\forall r\in\mathbb{R},\;p_r(2)=0\)'), '∀ r∈ℝ, p_r(2)=0')

    def test_boxed_results_keep_fraction_and_addition_precedence(self):
        self.assertEqual(normalize_answer(r'\[2\boxed{x^{2}+1}\]'), '2(x²+1)')
        self.assertEqual(normalize_answer(r'\boxed{\frac{1}{\frac{2}{3}}}'), '((1)/((2)/(3)))')
        self.assertEqual(normalize_answer(r'\boxed{\sqrt{x^{2}+1}}'), '(√(x²+1))')

    def test_new_notation_does_not_allow_unknown_commands_or_executable_markup(self):
        for text in [r'\mathbb{X}', r'\boxed{\input{secret}}', r'\boxed{<script>alert(1)</script>}',
                     r'\boxed{x^{r}}', r'\href{https://example.com}{answer}', r'\inside', r'\notinside']:
            with self.assertRaises(ValueError):
                normalize_answer(text)
