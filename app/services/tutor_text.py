"""Normalize a small, lossless subset of presentation markup into plain maths."""
import re

from .content_quality import plain_text

SUPERSCRIPT = str.maketrans('0123456789+-', '⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻')
SYMBOLS = {
    'times': '×', 'cdot': '×', 'pm': '±', 'mp': '∓', 'neq': '≠', 'ne': '≠',
    'leq': '≤', 'le': '≤', 'geq': '≥', 'ge': '≥', 'approx': '≈',
    'alpha': 'α', 'beta': 'β', 'gamma': 'γ', 'theta': 'θ', 'pi': 'π',
    'Rightarrow': '⇒', 'rightarrow': '→', 'implies': '⇒', 'infty': '∞',
    'in': '∈', 'notin': '∉', 'forall': '∀', 'exists': '∃', 'varnothing': '∅',
}
NUMBER_SETS = {'N': 'ℕ', 'Z': 'ℤ', 'Q': 'ℚ', 'R': 'ℝ', 'C': 'ℂ'}


def normalize_answer(answer):
    """Preserve maths/conditions; unsupported commands and HTML still fail closed."""
    answer = re.sub(r'(?m)^\s{0,3}#{1,6}\s+', '', answer)
    answer = re.sub(r'```(?:text|plaintext|math|latex)?[ \t]*\n(.*?)\n```', r'\1', answer, flags=re.S)
    answer = re.sub(r'`([^`\n]+)`', r'\1', answer)
    for marker in ('**', '__', '*', '_'):
        escaped = re.escape(marker)
        answer = re.sub(r'(?<!\w)' + escaped + r'(?=\S)([^\n]+?\S|\S)' + escaped + r'(?!\w)', r'\1', answer)
    for opening, closing in ((r'\[', r'\]'), (r'\(', r'\)'), ('$$', '$$'), ('$', '$')):
        answer = re.sub(re.escape(opening) + r'(.*?)' + re.escape(closing), r'\1', answer, flags=re.S)
    answer = re.sub(r'\\(?:qquad|quad|enspace|thinspace)\b|\\[,;! ]', ' ', answer)
    answer = re.sub(r'\\mathbb\s*\{([NZQRC])\}', lambda m: NUMBER_SETS[m[1]], answer)
    answer = re.sub(r'\\(?:left|right)(?=[()\[\]])', '', answer)
    # TeX command names use ASCII letters; Unicode operands such as ℝ must not
    # prevent matching, while unknown longer commands must remain unsupported.
    answer = re.sub(r'\\(' + '|'.join(SYMBOLS) + r')(?![A-Za-z])', lambda m: SYMBOLS[m[1]], answer)
    answer = re.sub(r'\\(?:text|mathrm|mathbf)\{([^{}\\]*)\}', r'\1', answer)
    answer = re.sub(r'\^(?:\{([+-]?\d+)\}|([+-]?\d+))',
                    lambda m: (m[1] or m[2]).translate(SUPERSCRIPT), answer)
    # Only supported braced expressions are rewritten. Parentheses preserve precedence.
    for _ in range(16):
        previous = answer
        answer = re.sub(r'\\frac\{([^{}\\]+)\}\{([^{}\\]+)\}', r'(\1)/(\2)', answer)
        answer = re.sub(r'\\sqrt\{([^{}\\]+)\}', r'√(\1)', answer)
        answer = re.sub(r'\\boxed\{([^{}\\]+)\}', r'(\1)', answer)
        if answer == previous:
            break
    answer = answer.strip()
    if not answer or not plain_text(answer):
        raise ValueError('Unsupported tutor formatting')
    return answer
