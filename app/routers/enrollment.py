from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..core.security import get_current_user
from ..models.aptitudeModel import Enrollment
from ..models.learningCourseModel import LearningCourse
from ..models.subModuleMasterModel import SubModuleMaster
from ..models.usersModel import User
from ..services.engagement import enabled
from .learning import learning_db, no_cache

router = APIRouter(prefix='/learning', tags=['enrollment'], dependencies=[Depends(no_cache), Depends(enabled)])


@router.get('/subjects')
def subjects(db: Session = Depends(learning_db), user: User = Depends(get_current_user)):
    rows = db.query(SubModuleMaster).join(LearningCourse, LearningCourse.subject_id == SubModuleMaster.sub_module_id).distinct().order_by(SubModuleMaster.sub_module_name).all()
    return [{'id': str(row.sub_module_id), 'name': row.sub_module_name, 'description': row.sub_module_description,
             'enrolled': db.get(Enrollment, (user.id, row.sub_module_id)) is not None} for row in rows]


@router.post('/subjects/{subject_id}/enroll')
def enroll(subject_id: UUID, db: Session = Depends(learning_db), user: User = Depends(get_current_user)):
    if not db.query(LearningCourse).filter_by(subject_id=subject_id).first():
        raise HTTPException(404, 'This subject has no published course.')
    db.query(User).filter_by(id=user.id).with_for_update().one()
    if not db.get(Enrollment, (user.id, subject_id)):
        db.add(Enrollment(user_id=user.id, subject_id=subject_id))
    db.commit()
    return {'enrolled': True}
