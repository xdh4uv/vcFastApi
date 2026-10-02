from uuid import UUID
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..core.security import get_current_user
from ..models.usersModel import User
from ..schemas.engagement import ReadingUpdate, TimingUpdate
from ..services.engagement import enabled, reading_source, reading_view, update_reading, update_timing
from ..services.access import learning_access
from .learning import learning_db, no_cache, get_chapter, lock_progress, owned_attempt

router = APIRouter(prefix='/learning', tags=['engagement'], dependencies=[Depends(no_cache), Depends(enabled), Depends(learning_access)])


@router.get('/courses/{course_id}/chapters/{chapter_id}/progress')
def get_progress(course_id: str, chapter_id: str, db: Session = Depends(learning_db), user: User = Depends(get_current_user)):
    source = reading_source(get_chapter(course_id, chapter_id, db, user))
    return reading_view(db, user.id, course_id, chapter_id, source)


@router.post('/courses/{course_id}/chapters/{chapter_id}/progress')
def save_progress(course_id: str, chapter_id: str, body: ReadingUpdate, db: Session = Depends(learning_db), user: User = Depends(get_current_user)):
    lock_progress(db, user.id, course_id)
    source = reading_source(get_chapter(course_id, chapter_id, db, user))
    result = update_reading(db, user.id, course_id, chapter_id, source, body)
    db.commit()
    return result


@router.post('/courses/{course_id}/attempts/{attempt_id}/timing')
def save_timing(course_id: str, attempt_id: UUID, body: TimingUpdate, db: Session = Depends(learning_db), user: User = Depends(get_current_user)):
    attempt = owned_attempt(db, user, course_id, attempt_id)
    update_timing(db, user.id, course_id, attempt, body)
    db.commit()
    return {'saved': True}
