"""Original Class 10 Polynomials starter bank; regenerate the checked JSON artifact."""
import json
from fractions import Fraction
from pathlib import Path

concepts = [
    dict(id='zeroes', title='Finding and checking zeroes', legacyLabels=['zeroes'],
         explanation='A number r is a zero of p(x) when substitution gives p(r) = 0. A factor x − r therefore gives zero r. Solve each factor separately and check by substitution.',
         example=dict(problem='Find and verify the zeroes of x² − x − 6.', steps=['Factorise: x² − x − 6 = (x − 3)(x + 2).', 'Set each factor to zero: x = 3 or x = −2.', 'Check: 9 − 3 − 6 = 0 and 4 + 2 − 6 = 0.']),
         commonMistake='The factor x + 2 gives zero −2, not 2.', checklist=['Set p(x) equal to zero.', 'Keep signs when solving each factor.', 'Substitute every proposed zero.']),
    dict(id='degree-and-graphs', title='Degree and graphical zeroes', legacyLabels=['degree'],
         explanation='After collecting like terms, degree is the highest power with a nonzero coefficient. A nonzero polynomial of degree n has at most n distinct real zeroes. On y = p(x), zeroes are x-coordinates of x-axis contacts; touching also counts.',
         example=dict(problem='How many distinct real zeroes does y = (x − 4)² have?', steps=['The polynomial has degree 2.', 'It equals zero only at x = 4; the graph touches the x-axis there.', 'There is one distinct real zero, even though the factor occurs twice.']),
         commonMistake='Degree gives an upper bound, not a guarantee of that many distinct real zeroes. The zero polynomial has no defined degree.', checklist=['Simplify before finding degree.', 'Count distinct x-axis contacts.', 'Do not count the y-intercept as a zero unless it is the origin.']),
    dict(id='sum-of-zeroes', title='Sum of zeroes', legacyLabels=['sum of zeroes'],
         explanation='For ax² + bx + c, a ≠ 0, the sum of the two zeroes (counting a repeated zero twice) is −b/a. Read signed coefficients carefully; use the sum to recover a missing zero or coefficient.',
         example=dict(problem='One zero of 2x² − 10x + 12 is 2. Find the other.', steps=['a = 2 and b = −10, so the sum is −(−10)/2 = 5.', 'The other zero is 5 − 2 = 3.', 'Check: 2(3²) − 10(3) + 12 = 0.']),
         commonMistake='Using b/a loses the leading minus sign; using −b alone ignores a.', checklist=['Identify a and signed b.', 'Compute −b/a.', 'Subtract the known zero if needed.']),
    dict(id='product-and-relations', title='Product and coefficient relations', legacyLabels=['coefficient relations'],
         explanation='For ax² + bx + c, the product of its two zeroes is c/a. Combine product and sum checks to determine coefficients. If a known zero is nonzero, divide the product by it to find the other.',
         example=dict(problem='One zero of x² − 9x + k is 4. Find k.', steps=['The sum is 9, so the other zero is 5.', 'The product is 4 × 5 = 20; since a = 1, k = 20.', 'Substitution gives 16 − 36 + 20 = 0.']),
         commonMistake='The product is c/a, not −c/a. Dividing by a known zero of 0 is invalid.', checklist=['Identify a and c including signs.', 'Check both sum and product.', 'Use substitution to verify a recovered coefficient.']),
    dict(id='forming-polynomials', title='Forming quadratic polynomials', legacyLabels=['forming polynomials'],
         explanation='A monic quadratic with zeroes r and s is x² − (r + s)x + rs. Monic means leading coefficient 1. Multiplying the whole expression by any nonzero constant preserves its zeroes.',
         example=dict(problem='Form a monic quadratic with zeroes −3 and 4.', steps=['Sum = 1 and product = −12.', 'Use x² − (sum)x + product: x² − x − 12.', 'Expand (x + 3)(x − 4) to verify the same expression.']),
         commonMistake='The coefficient of x is the negative of the sum. A pair of zeroes determines a unique monic quadratic, but many non-monic multiples.', checklist=['Compute the sum and product.', 'Use x² − Sx + P.', 'Apply any requested leading coefficient to every term.']),
]


def polynomial(a, b, c):
    terms = []
    for coefficient, variable in [(a, 'x²'), (b, 'x'), (c, '')]:
        if not coefficient:
            continue
        magnitude = '' if variable and abs(coefficient) == 1 else str(abs(coefficient))
        term = magnitude + variable
        terms.append(('-' if coefficient < 0 else '') + term if not terms else (' - ' if coefficient < 0 else ' + ') + term)
    return ''.join(terms) or '0'


def build():
    questions = []
    titles = {c['id']: c['title'] for c in concepts}
    def add(concept, difficulty, prompt, correct, wrong, explanation):
        values = list(map(str, [correct, *wrong]))
        assert len(values) == len(set(values)) == 4, prompt
        shift = len(questions) % 4
        options = values[shift:] + values[:shift]
        questions.append(dict(id=f'poly-v1-{len(questions)+1:02d}', conceptId=concept, concept=titles[concept], difficulty=difficulty,
                              prompt=prompt, options=options, answer=options.index(str(correct)), explanation=explanation))
    def number(concept, difficulty, prompt, answer, explanation):
        answer = Fraction(answer)
        wrong = list(dict.fromkeys([-answer, answer-1, answer+1, answer+2]))
        add(concept, difficulty, prompt, answer, [n for n in wrong if n != answer][:3], explanation)

    for a, r in [(3, 4), (5, -2), (2, 7)]:
        expression = f'{a}x' + (f' - {a*r}' if r > 0 else f' + {-a*r}')
        number('zeroes', 'foundation', f'Find the zero of {expression}.', r, f'Set {expression} = 0 and divide by {a}: x = {r}.')
    for r, s in [(2, 5), (-3, 2), (-4, -1)]:
        expression = polynomial(1, -r-s, r*s)
        add('zeroes', 'standard', f'Which pair gives both zeroes of {expression}?', f'{r} and {s}',
            [f'{-r} and {-s}', f'{r} and {-s}', f'{-r} and {s}'], f'Sum {r+s}, product {r*s}; substitution of {r} and {s} gives zero.')
    for r, a, b in [(2, 3, -5), (-2, 2, 3), (3, 2, -7)]:
        k = -a*r*r-b*r
        expression = polynomial(a, b, 0) + ' + k'
        number('zeroes', 'challenge', f'If {r} is a zero of {expression}, find k.', k, f'Substitute x = {r}: k = -({a} × ({r})²) - ({b} × ({r})) = {k}.')

    for expression, degree in [('6x³ - 2x + 9', 3), ('4x² + 7x - 5', 2), ('8 - 3x', 1)]:
        add('degree-and-graphs', 'foundation', f'What is the degree of {expression}?', degree,
            [n for n in [0, 1, 2, 3] if n != degree], f'The highest power of x with a nonzero coefficient is {degree}.')
    for description, count in [('meets the x-axis only at (-3, 0) and (2, 0)', 2), ('touches the x-axis only at (5, 0)', 1), ('lies entirely above the x-axis', 0)]:
        add('degree-and-graphs', 'standard', f'The graph of a nonzero polynomial {description}. How many distinct real zeroes does it have?', count,
            [n for n in range(4) if n != count], f'Count distinct x-axis contacts, including a touch: {count}.')
    for expression, degree in [('5x³ + 2x² - 5x³ + x', 2), ('4x² + 3x - 4x² + 8', 1), ('7x² - 7x² + 6', 0)]:
        add('degree-and-graphs', 'challenge', f'After simplifying {expression}, what is the maximum possible number of distinct real zeroes allowed by its degree?', degree,
            [n for n in range(4) if n != degree], f'The leading terms cancel. The remaining nonzero polynomial has degree {degree}, hence at most {degree} distinct real zeroes.')

    for a, b, c in [(1, -6, 8), (1, 5, 6), (2, -9, 4)]:
        number('sum-of-zeroes', 'foundation', f'Find the sum of the zeroes of {polynomial(a,b,c)}.', Fraction(-b,a), f'Sum = -b/a = -({b})/{a} = {Fraction(-b,a)}.')
    for a, r, s in [(1, 2, 6), (2, -1, 4), (1, -3, -5)]:
        expression = polynomial(a, -a*(r+s), a*r*s)
        number('sum-of-zeroes', 'standard', f'One zero of {expression} is {r}. Find the other using their sum.', s, f'Sum = {r+s}; other zero = {r+s} - ({r}) = {s}.')
    for a, total, c in [(2, 5, 8), (3, -4, 9), (4, 3, 8)]:
        number('sum-of-zeroes', 'challenge', f'The zeroes of {a}x² + kx + {c} have sum {total}. Find k.', -a*total, f'-k/{a} = {total}, so k = {-a*total}.')

    for a, b, c in [(1, -7, 12), (2, 1, -6), (3, -8, 4)]:
        number('product-and-relations', 'foundation', f'Find the product of the zeroes of {polynomial(a,b,c)}.', Fraction(c,a), f'Product = c/a = {c}/{a} = {Fraction(c,a)}.')
    for a, r, s in [(2, 3, 5), (3, -2, 4), (2, -3, -1)]:
        expression = polynomial(a, -a*(r+s), a*r*s)
        number('product-and-relations', 'standard', f'One zero of {expression} is {r}. Find the other using their product.', s, f'Product = {a*r*s}/{a} = {r*s}; other zero = {r*s}/({r}) = {s}.')
    for a, r, s in [(2, 2, 5), (3, -1, 4), (2, -2, -5)]:
        expression = polynomial(a, -a*(r+s), 0) + ' + k'
        number('product-and-relations', 'challenge', f'One zero of {expression} is {r}. Use coefficient relations to find k.', a*r*s,
               f'Sum = {r+s}, so the other zero is {s}. Product k/{a} = {r*s}; hence k = {a*r*s}.')

    for difficulty, pairs in [('foundation', [(1,4), (2,3), (-2,5)]), ('standard', [(-3,-2), (-4,2), (0,5)])]:
        for r, s in pairs:
            b, c = -r-s, r*s
            prompt = f'Which monic quadratic has zeroes {r} and {s}?' if difficulty == 'foundation' else f'A monic quadratic has zeroes with sum {r+s} and product {c}. Which is it?'
            add('forming-polynomials', difficulty, prompt, polynomial(1,b,c), [polynomial(1,-b,c), polynomial(1,b,c+1), polynomial(1,b+1,c)],
                f'Use x² - (sum)x + product: {polynomial(1,b,c)}. Monic means the coefficient of x² is 1.')
    for a, r, s in [(2,1,3), (3,-2,4), (2,-3,-1)]:
        b, c = -a*(r+s), a*r*s
        add('forming-polynomials', 'challenge', f'Which quadratic has leading coefficient {a} and zeroes {r} and {s}?', polynomial(a,b,c),
            [polynomial(a,-b,c), polynomial(a,b,-c), polynomial(a,-r-s,r*s)],
            f'Multiply the entire monic quadratic by {a}: {polynomial(a,b,c)}. Both its sum and product relations agree.')
    return dict(courseId='ncert-maths-10-v1', chapterId='ch-02', concepts=concepts, questions=questions)


if __name__ == '__main__':
    path = Path(__file__).resolve().parents[1] / 'data/polynomials-practice-v1.json'
    path.write_text(json.dumps(build(), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('Wrote 5 Polynomials revision cards and 45 questions.')
