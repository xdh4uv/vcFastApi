"""Transparent five-signal policy. No ML, provider calls or generated scores."""
from datetime import datetime, timedelta, timezone
from math import exp
from statistics import pvariance
from sqlalchemy import func
from ..models.aptitudeModel import AptitudeProfile, Enrollment
from ..models.engagementModel import ReadingProgress, LearningEvent
from ..models.learningCourseModel import LearningAttempt, LearningCourse
from ..models.tutorModel import DoubtTurn
from .engagement import utc


WEIGHTS = {'testPerformance': .35, 'consistency': .15, 'readingEngagement': .20,
           'questionResolution': .15, 'reviewAvoidance': .15}


def calculate(db, user_id, course_id):
    db.flush()
    now = datetime.now(timezone.utc)
    attempts = db.query(LearningAttempt).filter_by(user_id=user_id, course_id=course_id).filter(LearningAttempt.submitted_at.is_not(None)).order_by(LearningAttempt.submitted_at, LearningAttempt.id).all()
    # Only first answers to distinct questions count. Retakes cannot manufacture evidence.
    evidence = {}
    for attempt in attempts:
        for question in attempt.questions:
            evidence.setdefault(question['id'], (attempt.answers.get(question['id']) == question['answer'], utc(attempt.submitted_at)))
    weights = [exp(-(now - date).total_seconds() / (30 * 86400)) for _, date in evidence.values()]
    performance = sum(weight * correct for weight, (correct, _) in zip(weights, evidence.values())) / sum(weights) if weights else .5
    reading = db.query(ReadingProgress).filter_by(user_id=user_id, course_id=course_id).all()
    course = db.get(LearningCourse, course_id)
    chapters = course.content['chapters']
    # Count each chapter's active time only up to its base lesson reading estimate.
    reading_scores = []
    for row in reading:
        chapter = next((c for c in chapters if c['id'] == row.chapter_id), None)
        if chapter:
            words = len(str({k: chapter[k] for k in ('goal', 'concepts', 'example', 'watchFor')}).split())
            expected = max(60, words * 60 / 160)
            reading_scores.append(min(1, sum(row.sections.values()) / expected))
    since = now - timedelta(days=30)
    events = db.query(LearningEvent.created_at, LearningEvent.event_type, LearningEvent.payload).filter(
        LearningEvent.user_id == user_id, LearningEvent.course_id == course_id, LearningEvent.created_at >= since).all()
    # Meaningful activity requires a submitted test or accepted active reading, not a page open.
    days = {utc(e.created_at).date() for e in events if e.event_type == 'TEST_COMPLETED' or e.event_type == 'PAGE_READ' and e.payload.get('acceptedSeconds', 0) >= 3}
    days.update(utc(a.submitted_at).date() for a in attempts if utc(a.submitted_at) >= since)
    turns = db.query(DoubtTurn).filter_by(user_id=user_id, course_id=course_id).all()
    rated = [t for t in turns if t.helpful is not None and t.status == 'ready']
    resolution = sum(t.helpful and not t.flagged for t in rated) / len(turns) if turns else .5
    review = 1 - sum(t.flagged for t in turns) / len(turns) if turns else .5
    signals = {'testPerformance': performance, 'consistency': min(1, len(days) / 30),
               'readingEngagement': sum(reading_scores) / len(reading_scores) if reading_scores else 0,
               'questionResolution': resolution, 'reviewAvoidance': review}
    score = sum(signals[key] * weight for key, weight in WEIGHTS.items())
    count = len(evidence) + len(days) + sum(sum(value >= 3 for value in row.sections.values()) for row in reading) + len(rated)
    variance = pvariance(list(signals.values()))
    confidence = min(1, count / 20) * max(0, 1 - variance)
    eligible = count >= 10 and bool(evidence) and variance <= .15
    row = db.get(AptitudeProfile, (user_id, course_id))
    if row is None:
        row = AptitudeProfile(user_id=user_id, course_id=course_id)
        db.add(row)
    row.score, row.confidence, row.signals, row.evidence_count = score, confidence, signals, count
    row.updated_at = now
    # Store eligibility without exposing another student's evidence.
    row.signals = {**signals, 'eligible': eligible, 'variance': variance, 'testEvidence': len(evidence)}
    db.flush()
    return row


def thresholds(db, course_id):
    scores = sorted(row.score for row in db.query(AptitudeProfile).filter_by(course_id=course_id).all() if row.signals.get('eligible'))
    if not scores:
        return .3, .7
    def percentile(fraction):
        position = (len(scores) - 1) * fraction
        left = int(position)
        return scores[left] + (scores[min(left + 1, len(scores) - 1)] - scores[left]) * (position - left)
    return percentile(.3), percentile(.7)


def assign(db, row):
    lower, upper = thresholds(db, row.course_id)
    # Ties remain Default; an equal-score cohort does not manufacture extremes.
    row.tier = 'default' if not row.signals.get('eligible') else 'beginner' if row.score < lower else 'advanced' if row.score > upper else 'default'
    return row


def recompute(db, user_id, course_id):
    return assign(db, calculate(db, user_id, course_id))


def profile_view(db, row):
    if not row:
        return {'tier': 'default', 'score': None, 'confidence': 0, 'evidenceCount': 0, 'progress': 0, 'reason': 'more-evidence-needed', 'signals': {}}
    lower, upper = thresholds(db, row.course_id)
    target = lower if row.tier == 'beginner' else upper if row.tier == 'default' else 1
    if row.tier == 'advanced':
        progress = min(100, max(0, round(100 * (row.score - upper) / (1 - upper)))) if upper < 1 else 100
    else:
        progress = min(100, round(100 * row.score / target)) if target > 0 else 0
    return {'tier': row.tier, 'score': round(row.score, 4), 'confidence': round(row.confidence, 4), 'evidenceCount': row.evidence_count,
            'progress': progress, 'reason': 'five-signals' if row.signals.get('eligible') else 'more-evidence-needed',
            'signals': {key: round(row.signals[key], 4) for key in WEIGHTS}, 'updatedAt': row.updated_at}


def recompute_all(db):
    # Cohort thresholds use fresh scores for the whole batch before assigning tiers.
    pairs = db.query(Enrollment.user_id, LearningCourse.course_id).join(LearningCourse, LearningCourse.subject_id == Enrollment.subject_id).all()
    from ..routers.learning import lock_progress
    for user_id, course_id in sorted(pairs):
        lock_progress(db, user_id, course_id)
        calculate(db, user_id, course_id)
        db.commit()
    for user_id, course_id in sorted(pairs):
        lock_progress(db, user_id, course_id)
        assign(db, db.get(AptitudeProfile, (user_id, course_id)))
        db.commit()
    return len(pairs)
