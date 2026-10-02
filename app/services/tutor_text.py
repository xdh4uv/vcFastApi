"""Normalize a small, lossless subset of presentation markup into plain maths."""
import re

from .content_quality import plain_text

SUPERSCRIPT = str.maketrans('0123456789+-', '⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻')
SYMBOLS = {
    'times': '×', 'cdot': '×', 'pm': '±', 'mp': '∓', 'neq': '≠', 'ne': '≠',
    'leq': '≤', 'le': '≤', 'geq': '≥', 'ge': '≥', 'approx': '≈',
    'alpha': 'α', 'beta': 'β', 'gamma': 'γ', 'theta': 'θ', 'pi': 'π',
    'Rightarrow': '⇒', 'rightarrow': '→', 'implies': '⇒', 'infty': '∞',
}


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
    answer = re.sub(r'\\(?:left|right)(?=[()\[\]])', '', answer)
    answer = re.sub(r'\\(' + '|'.join(SYMBOLS) + r')\b', lambda m: SYMBOLS[m[1]], answer)
    answer = re.sub(r'\\(?:text|mathrm|mathbf)\{([^{}\\]*)\}', r'\1', answer)
    # Only supported braced expressions are rewritten. Parentheses preserve precedence.
    for _ in range(16):
        previous = answer
        answer = re.sub(r'\\frac\{([^{}\\]+)\}\{([^{}\\]+)\}', r'(\1)/(\2)', answer)
        answer = re.sub(r'\\sqrt\{([^{}\\]+)\}', r'√(\1)', answer)
        if answer == previous:
            break
    answer = re.sub(r'\^(?:\{([+-]?\d+)\}|([+-]?\d+))',
                    lambda m: (m[1] or m[2]).translate(SUPERSCRIPT), answer)
    answer = answer.strip()
    if not answer or not plain_text(answer):
        raise ValueError('Unsupported tutor formatting')
    return answer
