"""Reading and timing records, isolated from grading and answer snapshots."""
from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from ..core.database import Base
from .learningCourseModel import document


class ReadingProgress(Base):
    __tablename__ = 'learning_reading_progress'
    __table_args__ = {'schema': 'modules'}
    user_id = Column(Integer, ForeignKey('public.users.id', ondelete='CASCADE'), primary_key=True)
    course_id = Column(String(100), ForeignKey('modules.learning_courses.course_id'), primary_key=True)
    chapter_id = Column(String(40), primary_key=True)
    source_key = Column(String(64), nullable=False)
    sections = Column(document, nullable=False, default=dict)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class LearningEvent(Base):
    __tablename__ = 'learning_events'
    __table_args__ = (Index('ix_learning_events_owner_time', 'user_id', 'course_id', 'created_at'), {'schema': 'modules'})
    id = Column(UUID(as_uuid=True), primary_key=True)
    user_id = Column(Integer, ForeignKey('public.users.id', ondelete='CASCADE'), nullable=False)
    course_id = Column(String(100), ForeignKey('modules.learning_courses.course_id'), nullable=False)
    chapter_id = Column(String(40), nullable=True)
    event_type = Column(String(40), nullable=False)
    payload = Column(document, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class AttemptTiming(Base):
    __tablename__ = 'learning_attempt_timing'
    __table_args__ = {'schema': 'modules'}
    attempt_id = Column(UUID(as_uuid=True), ForeignKey('modules.learning_attempts.id', ondelete='CASCADE'), primary_key=True)
    seconds = Column(document, nullable=False, default=dict)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
