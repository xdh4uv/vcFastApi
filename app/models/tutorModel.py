from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from ..core.database import Base
from .learningCourseModel import document


class DoubtTurn(Base):
    __tablename__ = 'learning_doubts'
    __table_args__ = (Index('ix_doubt_owner_chapter', 'user_id', 'course_id', 'chapter_id', 'created_at'), {'schema': 'modules'})
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(Integer, ForeignKey('public.users.id', ondelete='CASCADE'), nullable=False)
    course_id = Column(String(100), ForeignKey('modules.learning_courses.course_id'), nullable=False)
    chapter_id = Column(String(40), nullable=False)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=True)
    tier = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False, default='pending')
    helpful = Column(Boolean, nullable=True)
    flagged = Column(Boolean, nullable=False, default=False)
    usage = Column(document, nullable=False, default=dict)
    error_code = Column(String(80), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime(timezone=True), nullable=True)


class SavedNote(Base):
    __tablename__ = 'learning_saved_notes'
    __table_args__ = (UniqueConstraint('user_id', 'turn_id'), Index('ix_notes_owner_time', 'user_id', 'created_at'), {'schema': 'modules'})
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(Integer, ForeignKey('public.users.id', ondelete='CASCADE'), nullable=False)
    turn_id = Column(UUID(as_uuid=True), ForeignKey('modules.learning_doubts.id'), nullable=False)
    course_id = Column(String(100), ForeignKey('modules.learning_courses.course_id'), nullable=False)
    chapter_id = Column(String(40), nullable=False)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
