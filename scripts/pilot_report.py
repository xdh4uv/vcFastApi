"""Read-only aggregate pilot report. No student identifiers or conversations emitted."""
import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.learningCourseModel import LearningAttempt
from app.models.engagementModel import LearningEvent
from app.models.tutorModel import DoubtTurn, SavedNote
from app.services.pilot_metrics import percent, score_change


def build_report(db, course_id, since):
    attempts = db.query(LearningAttempt.id, LearningAttempt.user_id, LearningAttempt.test_id, LearningAttempt.kind,
                        LearningAttempt.correct, LearningAttempt.total, LearningAttempt.submitted_at).filter(
                            LearningAttempt.course_id == course_id, LearningAttempt.submitted_at >= since).all()
    doubts = db.query(DoubtTurn.user_id, DoubtTurn.status, DoubtTurn.helpful, DoubtTurn.flagged).filter(
        DoubtTurn.course_id == course_id, DoubtTurn.created_at >= since).all()
    notes = db.query(SavedNote.user_id).filter(SavedNote.course_id == course_id, SavedNote.created_at >= since).all()
    events = db.query(LearningEvent.user_id).filter(LearningEvent.course_id == course_id, LearningEvent.created_at >= since).distinct().all()
    active = {row.user_id for row in attempts + doubts + notes} | {row[0] for row in events}
    resolved = sum(row.status == 'ready' and row.helpful is True and not row.flagged for row in doubts)
    rated = sum(row.status == 'ready' and row.helpful is not None for row in doubts)
    return {'courseId': course_id, 'since': since.isoformat(), 'activeStudents': len(active),
            'notesAdoption': {'studentsSavingNotes': len({n.user_id for n in notes}), 'percent': percent(len({n.user_id for n in notes}), len(active))},
            'tutor': {'questions': len(doubts), 'confirmedHelpfulUnflagged': resolved, 'ratedAnswers': rated,
                      'failed': sum(d.status == 'failed' for d in doubts), 'pending': sum(d.status == 'pending' for d in doubts),
                      'confirmedResolutionPercent': percent(resolved, len(doubts)), 'feedbackCoveragePercent': percent(rated, len(doubts)),
                      'method': 'Helpful, ready, unflagged replies / all questions; feedback proxy, unrated replies remain unknown.'},
            'scoreChange': score_change(attempts), 'cachedLoadP95Seconds': None,
            'limitations': ['HTTP latency needs a separate benchmark.', 'Score change is observational, not proof the platform caused improvement.', 'No activity or insufficient follow-up yields unknown metrics.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--course', default='ncert-maths-10-v1')
    parser.add_argument('--days', type=int, default=35)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if not 28 <= args.days <= 365:
        parser.error('--days must be 28–365.')
    engine = create_engine(settings.database_url)
    try:
        with Session(engine) as db:
            db.execute(text('SET TRANSACTION READ ONLY'))
            result = build_report(db, args.course, datetime.now(timezone.utc) - timedelta(days=args.days))
        output = json.dumps(result, indent=2)
        if args.output:
            args.output.write_text(output, encoding='utf-8')
        print(output)
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
