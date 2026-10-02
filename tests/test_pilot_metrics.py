from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import unittest

from app.services.pilot_metrics import percent, score_change


class PilotMetricsTests(unittest.TestCase):
    def test_each_learner_has_equal_weight_despite_different_chapter_counts(self):
        started = datetime.now(timezone.utc)
        rows = []
        for user, chapter, gain in [(1, 'ch-01', 4), (1, 'ch-02', 4), (2, 'ch-01', 0)]:
            for day, correct in [(0, 5), (28, 5 + gain)]:
                rows.append(SimpleNamespace(kind='chapter', submitted_at=started + timedelta(days=day),
                    total=10, correct=correct, user_id=user, test_id=chapter, id=len(rows)))
        result = score_change(rows)
        self.assertEqual(result['meanGainPercentagePoints'], 20)
        self.assertEqual(result['meanRelativeGainPercent'], 40)

    def test_missing_or_immature_evidence_is_unknown(self):
        self.assertIsNone(percent(0, 0))
        self.assertIsNone(score_change([])['meanRelativeGainPercent'])
        started = datetime.now(timezone.utc)
        a = SimpleNamespace(kind='chapter', submitted_at=started, total=10, correct=5, user_id=1, test_id='ch-01', id=1)
        b = SimpleNamespace(**{**vars(a), 'submitted_at': started + timedelta(days=27), 'correct': 9, 'id': 2})
        self.assertEqual(score_change([a, b])['maturedChapterPairs'], 0)

    def test_comparable_chapters_and_zero_baselines_are_handled_honestly(self):
        started = datetime.now(timezone.utc)
        def row(user, chapter, day, correct, kind='chapter'):
            return SimpleNamespace(kind=kind, submitted_at=started + timedelta(days=day), total=10, correct=correct, user_id=user, test_id=chapter, id=day)
        result = score_change([row(1,'ch-01',0,5),row(1,'ch-01',28,6),row(2,'ch-01',0,0),row(2,'ch-01',28,5),row(1,'ch-02',28,10),row(1,'ch-01',30,10,'adaptive')])
        self.assertEqual(result['maturedChapterPairs'], 2)
        self.assertEqual(result['relativeGainPairs'], 1)
        self.assertEqual(result['meanRelativeGainPercent'], 20)
        self.assertEqual(result['meanGainPercentagePoints'], 30)
