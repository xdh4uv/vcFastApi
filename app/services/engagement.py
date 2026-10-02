from datetime import datetime, timezone
from uuid import uuid4
from fastapi import HTTPException
from ..core.config import settings
from ..models.engagementModel import ReadingProgress, LearningEvent, AttemptTiming
from .content import digest


def enabled():
    if not settings.engagement_enabled:
        raise HTTPException(503, 'Reading progress is not enabled yet.')


def reading_source(lesson):
    generated = (lesson.get('contentVariant') or {}).get('generated')
    if generated:
        sections = [{'id': f'section-{i}', 'title': s['title']} for i, s in enumerate(generated['sections'])]
        sections.append({'id': 'takeaways', 'title': 'Key takeaways'})
        text = str(generated)
    else:
        sections = [{'id': 'concepts', 'title': 'Core concepts'}, {'id': 'example', 'title': 'Worked example'},
                    {'id': 'watch-for', 'title': 'Watch for this'}]
        text = str({key: lesson[key] for key in ('goal', 'concepts', 'example', 'watchFor')})
    return {'sourceKey': digest(generated or {key: lesson[key] for key in ('goal', 'concepts', 'example', 'watchFor')}), 'sections': sections, 'estimatedMinutes': max(1, round(len(text.split()) / 160))}


def reading_view(db, user_id, course_id, chapter_id, source):
    row = db.get(ReadingProgress, (user_id, course_id, chapter_id))
    seconds = row.sections if row and row.source_key == source['sourceKey'] else {}
    consumed = sum(seconds.get(section['id'], 0) >= 3 for section in source['sections'])
    percent = round(100 * consumed / len(source['sections']))
    return {**source, 'seconds': seconds, 'percent': percent, 'testReady': percent >= settings.reading_test_threshold,
            'threshold': settings.reading_test_threshold}


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def time_credit(updated_at, requested):
    # Client telemetry is advisory: cap accepted time by elapsed server time.
    return min(requested, max(0, int((datetime.now(timezone.utc) - utc(updated_at)).total_seconds())))


def record_event(db, user_id, course_id, chapter_id, event_type, payload, event_id=None):
    db.add(LearningEvent(id=event_id or uuid4(), user_id=user_id, course_id=course_id,
                         chapter_id=chapter_id, event_type=event_type, payload=payload))


def duplicate(db, event_id, user_id, course_id, event_type, payload):
    row = db.get(LearningEvent, event_id)
    if row and (row.user_id != user_id or row.course_id != course_id or row.event_type != event_type or row.payload.get('request') != payload):
        raise HTTPException(409, 'This event ID was already used for a different update.')
    return row is not None


def update_reading(db, user_id, course_id, chapter_id, source, body):
    if body.sourceKey != source['sourceKey']:
        raise HTTPException(409, 'Lesson content changed. Reload before recording progress.')
    if body.section not in {section['id'] for section in source['sections']}:
        raise HTTPException(422, 'Unknown lesson section.')
    request = {**body.model_dump(mode='json'), 'chapterId': chapter_id}
    if duplicate(db, body.eventId, user_id, course_id, 'PAGE_READ', request):
        return reading_view(db, user_id, course_id, chapter_id, source)
    row = db.get(ReadingProgress, (user_id, course_id, chapter_id))
    if not row:
        row = ReadingProgress(user_id=user_id, course_id=course_id, chapter_id=chapter_id,
                              source_key=source['sourceKey'], sections={})
        db.add(row)
        db.flush()
        record_event(db, user_id, course_id, chapter_id, 'CHAPTER_OPENED', {})
    if row.source_key != source['sourceKey']:
        row.sections, row.source_key = {}, source['sourceKey']
        row.updated_at = datetime.now(timezone.utc)
    before = reading_view(db, user_id, course_id, chapter_id, source)
    credit = time_credit(row.updated_at, body.seconds)
    row.sections = {**row.sections, body.section: min(86400, row.sections.get(body.section, 0) + credit)}
    row.updated_at = datetime.now(timezone.utc)
    record_event(db, user_id, course_id, chapter_id, 'PAGE_READ', {'request': request, 'acceptedSeconds': credit}, body.eventId)
    db.flush()
    after = reading_view(db, user_id, course_id, chapter_id, source)
    if before['percent'] < 100 and after['percent'] == 100:
        record_event(db, user_id, course_id, chapter_id, 'CHAPTER_COMPLETED', {'sourceKey': source['sourceKey']})
    return after


def update_timing(db, user_id, course_id, attempt, body):
    if body.questionId not in {q['id'] for q in attempt.questions}:
        raise HTTPException(422, 'Unknown attempt question.')
    request = body.model_dump(mode='json')
    if duplicate(db, body.eventId, user_id, course_id, 'QUESTION_TIME', {**request, 'attemptId': str(attempt.id)}):
        return
    if attempt.submitted_at:
        raise HTTPException(409, 'Timing is closed for submitted tests.')
    row = db.get(AttemptTiming, attempt.id)
    if not row:
        row = AttemptTiming(attempt_id=attempt.id, seconds={}, updated_at=attempt.created_at)
        db.add(row)
    credit = time_credit(row.updated_at, body.seconds)
    row.seconds = {**row.seconds, body.questionId: min(86400, row.seconds.get(body.questionId, 0) + credit)}
    row.updated_at = datetime.now(timezone.utc)
    record_event(db, user_id, course_id, attempt.test_id, 'QUESTION_TIME',
                 {'request': {**request, 'attemptId': str(attempt.id)}, 'acceptedSeconds': credit}, body.eventId)
