from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from ..core.database import Base
from .learningCourseModel import document


class Enrollment(Base):
    __tablename__ = 'learning_enrollments'
    __table_args__ = {'schema': 'modules'}
    user_id = Column(Integer, ForeignKey('public.users.id', ondelete='CASCADE'), primary_key=True)
    subject_id = Column(UUID(as_uuid=True), ForeignKey('modules.sub_modules_master.sub_module_id'), primary_key=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class AptitudeProfile(Base):
    __tablename__ = 'learning_aptitude_profiles'
    __table_args__ = {'schema': 'modules'}
    user_id = Column(Integer, ForeignKey('public.users.id', ondelete='CASCADE'), primary_key=True)
    course_id = Column(String(100), ForeignKey('modules.learning_courses.course_id'), primary_key=True)
    score = Column(Float, nullable=False, default=0)
    confidence = Column(Float, nullable=False, default=0)
    tier = Column(String(20), nullable=False, default='default')
    signals = Column(document, nullable=False, default=dict)
    evidence_count = Column(Integer, nullable=False, default=0)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
