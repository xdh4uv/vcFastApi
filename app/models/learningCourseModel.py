from datetime import datetime, timezone
import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, JSON, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from ..core.database import Base
from .subModuleMasterModel import SubModuleMaster  # Register the FK target.

document = JSON().with_variant(JSONB, "postgresql")


class LearningCourse(Base):
    __tablename__ = "learning_courses"
    __table_args__ = (UniqueConstraint("subject_id", "level"), {"schema": "modules"})
    course_id = Column(String(100), primary_key=True)
    subject_id = Column(UUID(as_uuid=True), ForeignKey("modules.sub_modules_master.sub_module_id"), nullable=False)
    level = Column(String(40), nullable=False)
    content = Column(document, nullable=False)


class LearningPreference(Base):
    __tablename__ = "learning_preferences"
    __table_args__ = {"schema": "modules"}
    user_id = Column(Integer, ForeignKey("public.users.id", ondelete="CASCADE"), primary_key=True)
    subject_id = Column(UUID(as_uuid=True), ForeignKey("modules.sub_modules_master.sub_module_id"), primary_key=True)
    level = Column(String(40), nullable=False)


class LearningProgress(Base):
    __tablename__ = "learning_progress"
    __table_args__ = {"schema": "modules"}
    user_id = Column(Integer, ForeignKey("public.users.id", ondelete="CASCADE"), primary_key=True)
    course_id = Column(String(100), ForeignKey("modules.learning_courses.course_id"), primary_key=True)
    read = Column(document, nullable=False, default=list)


class LearningAttempt(Base):
    __tablename__ = "learning_attempts"
    __table_args__ = (
        Index("ix_learning_attempt_owner_course", "user_id", "course_id"),
        Index("uq_learning_active_draft", "user_id", "course_id", "test_id", unique=True,
              postgresql_where=text("submitted_at IS NULL"), sqlite_where=text("submitted_at IS NULL")),
        {"schema": "modules"},
    )
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(Integer, ForeignKey("public.users.id", ondelete="CASCADE"), nullable=False)
    course_id = Column(String(100), ForeignKey("modules.learning_courses.course_id"), nullable=False)
    test_id = Column(String(40), nullable=False)
    questions = Column(document, nullable=False)
    answers = Column(document, nullable=False, default=dict)
    revision = Column(Integer, nullable=False, default=0)
    correct = Column(Integer, nullable=True)
    total = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    submitted_at = Column(DateTime(timezone=True), nullable=True)
