"""Aggregate observational pilot signals; missing evidence is never success."""
from datetime import timedelta
from statistics import mean


def percent(numerator, denominator):
    return round(100 * numerator / denominator, 2) if denominator else None


def score_change(attempts, days=28):
    """Compare first and latest official attempt of the same student's chapter."""
    groups = {}
    for attempt in attempts:
        if attempt.kind != 'chapter' or not attempt.submitted_at or not attempt.total:
            continue
        groups.setdefault((attempt.user_id, attempt.test_id), []).append(attempt)
    gains, relative = {}, {}
    pair_count, relative_pairs = 0, 0
    for (user_id, _), rows in groups.items():
        rows.sort(key=lambda a: (a.submitted_at, str(a.id)))
        first, last = rows[0], rows[-1]
        if last.submitted_at - first.submitted_at < timedelta(days=days):
            continue
        baseline, followup = 100 * first.correct / first.total, 100 * last.correct / last.total
        gains.setdefault(user_id, []).append(followup - baseline)
        pair_count += 1
        if baseline:
            relative.setdefault(user_id, []).append(100 * (followup - baseline) / baseline)
            relative_pairs += 1
    return {'maturedChapterPairs': pair_count, 'relativeGainPairs': relative_pairs, 'studentsWithFollowup': len(gains),
            'meanGainPercentagePoints': round(mean(mean(v) for v in gains.values()), 2) if gains else None,
            'meanRelativeGainPercent': round(mean(mean(v) for v in relative.values()), 2) if relative else None,
            'method': 'First/latest official chapter attempts at least 28 days apart; average chapter gains within each learner, then learners equally. Observational, affected by retakes and question reuse.'}
