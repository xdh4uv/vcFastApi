from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session
from ..core.config import settings
from ..core.database import get_db
from ..core.security import get_current_user
from ..models.aptitudeModel import Enrollment
from ..models.learningCourseModel import LearningCourse
from ..models.usersModel import User


def require_course_access(db, user_id, course_id):
    if not settings.engagement_enabled:
        return
    subject_id = db.query(LearningCourse.subject_id).filter_by(course_id=course_id).scalar()
    if subject_id and not db.get(Enrollment, (user_id, subject_id)):
        raise HTTPException(403, 'Enroll in this subject before opening its course.')


def learning_access(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    course_id = request.path_params.get('course_id')
    if course_id:
        require_course_access(db, user.id, course_id)
