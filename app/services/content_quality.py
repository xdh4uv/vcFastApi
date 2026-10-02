"""Small deterministic release checks; mathematical review remains an operator task."""
import json
import re
from ..schemas.content import GeneratedLesson

MARKUP = re.compile(r'\\(?:[()\[\]]|[A-Za-z]+)|`|\*\*|__|\$[^$\n]+\$|(?m:^\s*#{1,6}\s)|\[[^\]\n]+\]\([^\n]+\)|</?[A-Za-z][^>]*>')
CLASS10_EXTRAS = re.compile(
    r'\b(?:complex|imaginary|non[- ]real)\s+(?:numbers?|roots?|zeroes?|zeros?|plane)\b'
    r'|\b(?:calculus|differentiation|integration|eigenvalues?|complex conjugates?)\b', re.I)


def plain_text(text):
    return MARKUP.search(text) is None


def approved_problems(source):
    """Reuse author-supplied worked problems; never assessment prompts or answer keys."""
    material = [source['chapter'], *source.get('revisionCards', [])]
    return list(dict.fromkeys(item['example']['problem'].strip() for item in material if item.get('example')))


def authored_examples(source):
    material = [source['chapter'], *source.get('revisionCards', [])]
    return {re.sub(r'\s+', ' ', item['example']['problem'].strip()): item['example']
            for item in material if item.get('example')}


def use_authored_examples(lesson, source):
    """Only explanation prose is generated; worked solutions remain the checked source."""
    examples = authored_examples(source)
    for section in lesson['sections']:
        example = examples.get(re.sub(r'\s+', ' ', section['example']['problem'].strip()))
        if example:
            section['example'] = {'problem': example['problem'], 'steps': list(example['steps'])}
    return GeneratedLesson.model_validate(lesson).model_dump()


def scope_rules(source):
    rules = ('Class 10 mathematics only: real-number reasoning, no complex/imaginary roots or numbers, '
            'calculus, or university topics. Advanced means deeper reasoning inside the same chapter, '
            'not a higher education level.' if source['courseId'].startswith('ncert-maths-10-') else
            'Stay within the supplied chapter and education level. Advanced changes depth, not curriculum.')
    if source['courseId'].startswith('ncert-maths-10-') and source['chapter'].get('id') == 'ch-02':
        rules += (' For a quadratic with zeroes r,s, ax²+bx+c = a(x−r)(x−s): never omit a. '
                  'A repeated quadratic zero has multiplicity two and touches the axis; do not claim '
                  'that every repeated zero of an arbitrary polynomial never crosses it. '
                  'Do not introduce general multiplicity theorems beyond the supplied quadratic examples.')
    return rules


def quality_issues(lesson, source):
    issues = []
    allowed = {re.sub(r'\s+', ' ', problem) for problem in approved_problems(source)}
    examples = authored_examples(source)
    class10 = source['courseId'].startswith('ncert-maths-10-')
    reference = json.dumps(source, ensure_ascii=False)
    def check_text(value, path):
        if not plain_text(value):
            issues.append({'path': path, 'type': 'invalid_plain_text', 'message': 'Use plain text and Unicode maths; no Markdown, HTML or LaTeX.'})
        if class10:
            for match in CLASS10_EXTRAS.finditer(value):
                if not re.search(re.escape(match.group()), reference, re.I):
                    issues.append({'path': path, 'type': 'out_of_scope', 'message': 'Topic is outside the supplied Class 10 reference.'})
                    break
    check_text(lesson['summary'], ['summary'])
    for index, section in enumerate(lesson['sections']):
        base = ['sections', index]
        for field, value in [('example', section['example']['problem']), ('checkYourself', section['checkYourself'])]:
            path = base + (['example', 'problem'] if field == 'example' else [field])
            if re.sub(r'\s+', ' ', value.strip()) not in allowed:
                issues.append({'path': path, 'type': 'unapproved_problem', 'message': 'Choose a problem verbatim from the supplied worked examples.'})
        authored = examples.get(re.sub(r'\s+', ' ', section['example']['problem'].strip()))
        if authored and section['example']['steps'] != authored['steps']:
            issues.append({'path': base + ['example', 'steps'], 'type': 'changed_worked_solution',
                           'message': 'Worked solutions must retain the authored steps.'})
        for field in ('title', 'checkYourself'):
            check_text(section[field], base + [field])
        check_text(section['example']['problem'], base + ['example', 'problem'])
        for field, values in [('explanation', section['explanation']), ('steps', section['example']['steps'])]:
            for i, value in enumerate(values):
                check_text(value, base + (['example', 'steps', i] if field == 'steps' else [field, i]))
    for index, value in enumerate(lesson['takeaways']):
        check_text(value, ['takeaways', index])
    return issues[:8]
