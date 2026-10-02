from datetime import datetime, timedelta, timezone
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from ..core.config import settings
from ..core.security import get_current_user
from ..models.usersModel import User
from ..models.tutorModel import DoubtTurn, SavedNote
from ..models.aptitudeModel import AptitudeProfile
from ..services.aptitude import recompute
from ..services.access import learning_access
from ..schemas.tutor import DoubtRequest, FeedbackRequest, NoteRequest
from ..services.content import source_document
from ..services.engagement import enabled, record_event, utc
from ..services.tutor import answer_question
from ..services.content_generation import GenerationError
from .learning import learning_db, no_cache, load_course, find_chapter, lock_progress

router = APIRouter(prefix='/learning', tags=['tutor', 'notes'], dependencies=[Depends(no_cache), Depends(enabled), Depends(learning_access)])


def turn_view(turn):
    return {'id': str(turn.id), 'question': turn.question, 'answer': turn.answer,
            'tier': turn.tier, 'status': turn.status, 'helpful': turn.helpful, 'flagged': turn.flagged, 'createdAt': turn.created_at}


def own_turn(db, user, turn_id):
    turn = db.query(DoubtTurn).filter_by(id=turn_id, user_id=user.id).first()
    if not turn:
        raise HTTPException(404, 'Question not found.')
    return turn


@router.get('/courses/{course_id}/chapters/{chapter_id}/doubts')
def history(course_id: str, chapter_id: str, db: Session = Depends(learning_db), user: User = Depends(get_current_user)):
    find_chapter(load_course(db, course_id), chapter_id)
    turns = db.query(DoubtTurn).filter_by(user_id=user.id, course_id=course_id, chapter_id=chapter_id).order_by(DoubtTurn.created_at.desc(), DoubtTurn.id.desc()).limit(20).all()
    return {'enabled': settings.tutor_enabled, 'turns': [turn_view(turn) for turn in reversed(turns)]}


@router.post('/courses/{course_id}/chapters/{chapter_id}/doubts')
def ask(course_id: str, chapter_id: str, body: DoubtRequest, db: Session = Depends(learning_db), user: User = Depends(get_current_user)):
    course = load_course(db, course_id)
    chapter = find_chapter(course, chapter_id)
    db.query(User).filter_by(id=user.id).with_for_update().one()
    lock_progress(db, user.id, course_id)
    existing = db.get(DoubtTurn, body.requestId)
    if existing:
        if existing.user_id != user.id or existing.course_id != course_id or existing.chapter_id != chapter_id or existing.question != body.question:
            raise HTTPException(409, 'Request ID already used.')
        if existing.status == 'pending' and utc(existing.created_at) < datetime.now(timezone.utc) - timedelta(minutes=2):
            existing.status, existing.error_code = 'failed', 'abandoned_request'
            existing.completed_at = datetime.now(timezone.utc)
            db.commit()
        return turn_view(existing)
    if not settings.tutor_enabled:
        raise HTTPException(503, 'Tutor generation is temporarily unavailable. Study material and tests remain available.')
    now = datetime.now(timezone.utc)
    recent = db.query(DoubtTurn).filter(DoubtTurn.user_id == user.id, DoubtTurn.created_at >= now - timedelta(days=1)).all()
    if len(recent) >= 40 or sum(utc(t.created_at) >= now - timedelta(hours=1) for t in recent) >= 10:
        raise HTTPException(429, 'Tutor request limit reached. Please try later.')
    if any(t.status == 'pending' and utc(t.created_at) > now - timedelta(minutes=2) for t in recent):
        raise HTTPException(409, 'A tutor answer is still being prepared. Please wait.')
    previous = db.query(DoubtTurn).filter_by(user_id=user.id, course_id=course_id, chapter_id=chapter_id, status='ready').order_by(DoubtTurn.created_at.desc()).limit(4).all()
    previous.reverse()
    source = source_document(db, course_id, chapter)
    profile = db.get(AptitudeProfile, (user.id, course_id)) if settings.engagement_enabled else None
    tier = profile.tier if profile else 'default'
    turn = DoubtTurn(id=body.requestId, user_id=user.id, course_id=course_id, chapter_id=chapter_id, question=body.question, tier=tier)
    db.add(turn)
    record_event(db, user.id, course_id, chapter_id, 'QUESTION_ASKED', {'turnId': str(turn.id)})
    # Persist before contacting the provider; release the progress lock during inference.
    db.commit()
    try:
        answer, usage = answer_question(source, tier, previous, body.question)
        turn.answer, turn.usage, turn.status = answer, usage, 'ready'
    except (GenerationError, ValueError) as exc:
        turn.status, turn.error_code = 'failed', str(exc) if isinstance(exc, GenerationError) else 'invalid_configuration'
    turn.completed_at = datetime.now(timezone.utc)
    record_event(db, user.id, course_id, chapter_id, 'TUTOR_RESPONSE', {'turnId': str(turn.id), 'status': turn.status, 'responseLength': len(turn.answer or '')})
    db.commit()
    return turn_view(turn)


@router.put('/doubts/{turn_id}/feedback')
def feedback(turn_id: UUID, body: FeedbackRequest, db: Session = Depends(learning_db), user: User = Depends(get_current_user)):
    turn = own_turn(db, user, turn_id)
    lock_progress(db, user.id, turn.course_id)
    db.refresh(turn)
    if turn.status != 'ready':
        raise HTTPException(409, 'Only completed answers accept feedback.')
    if turn.helpful != body.helpful:
        turn.helpful = body.helpful
        record_event(db, user.id, turn.course_id, turn.chapter_id, 'TUTOR_FEEDBACK', {'turnId': str(turn.id), 'helpful': body.helpful})
    if settings.engagement_enabled:
        recompute(db, user.id, turn.course_id)
    db.commit()
    return turn_view(turn)


@router.post('/doubts/{turn_id}/flag')
def flag(turn_id: UUID, db: Session = Depends(learning_db), user: User = Depends(get_current_user)):
    turn = own_turn(db, user, turn_id)
    lock_progress(db, user.id, turn.course_id)
    db.refresh(turn)
    if not turn.flagged:
        turn.flagged = True
        record_event(db, user.id, turn.course_id, turn.chapter_id, 'REVIEW_REQUESTED', {'turnId': str(turn.id)})
    if settings.engagement_enabled:
        recompute(db, user.id, turn.course_id)
    db.commit()
    return turn_view(turn)


def note_view(db, note, courses=None):
    courses = {} if courses is None else courses
    if note.course_id not in courses:
        courses[note.course_id] = load_course(db, note.course_id)
    course = courses[note.course_id]
    chapter = next((chapter for chapter in course.chapters if chapter.id == note.chapter_id), None)
    return {'id': str(note.id), 'courseId': note.course_id, 'courseTitle': course.title, 'chapterId': note.chapter_id,
            'chapterTitle': chapter.title if chapter else note.chapter_id, 'question': note.question, 'answer': note.answer, 'createdAt': note.created_at}


@router.post('/notes')
def save_note(body: NoteRequest, db: Session = Depends(learning_db), user: User = Depends(get_current_user)):
    turn = own_turn(db, user, body.turnId)
    lock_progress(db, user.id, turn.course_id)
    if turn.status != 'ready' or not turn.answer:
        raise HTTPException(409, 'This question has no completed answer to save.')
    note = db.query(SavedNote).filter_by(user_id=user.id, turn_id=turn.id).first()
    if not note:
        note = SavedNote(user_id=user.id, turn_id=turn.id, course_id=turn.course_id, chapter_id=turn.chapter_id,
                         question=turn.question, answer=turn.answer)
        db.add(note)
        db.flush()
    result = note_view(db, note)
    db.commit()
    return result


@router.get('/notes')
def notes(course_id: str | None = None, chapter_id: str | None = None, offset: int = Query(default=0, ge=0, le=100000),
          db: Session = Depends(learning_db), user: User = Depends(get_current_user)):
    query = db.query(SavedNote).filter_by(user_id=user.id)
    if course_id:
        query = query.filter_by(course_id=course_id)
    if chapter_id:
        query = query.filter_by(chapter_id=chapter_id)
    rows = query.order_by(SavedNote.created_at.desc(), SavedNote.id.desc()).offset(offset).limit(51).all()
    courses = {}
    return {'notes': [note_view(db, n, courses) for n in rows[:50]], 'hasMore': len(rows) > 50}


@router.delete('/notes/{note_id}')
def delete_note(note_id: UUID, db: Session = Depends(learning_db), user: User = Depends(get_current_user)):
    note = db.query(SavedNote).filter_by(id=note_id, user_id=user.id).first()
    if not note:
        raise HTTPException(404, 'Note not found.')
    db.delete(note)
    db.commit()
    return {'deleted': True}


@router.get('/notes/catalog')
def notes_catalog(db: Session = Depends(learning_db), user: User = Depends(get_current_user)):
    course_ids = [value[0] for value in db.query(SavedNote.course_id).filter_by(user_id=user.id).distinct().all()]
    return [{'courseId': course_id, 'title': course.title, 'chapters': [{'id': c.id, 'title': c.title} for c in course.chapters]}
            for course_id in course_ids for course in [load_course(db, course_id)]]
