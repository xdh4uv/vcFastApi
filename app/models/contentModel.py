from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from ..core.database import Base
from .learningCourseModel import document


class ContentGeneration(Base):
    __tablename__ = 'learning_content_generations'
    __table_args__ = (
        Index('uq_content_active_key', 'cache_key', unique=True,
              postgresql_where=text("status IN ('pending','ready')"), sqlite_where=text("status IN ('pending','ready')")),
        Index('ix_content_lookup', 'course_id', 'chapter_id', 'tier', 'source_hash', 'prompt_version', 'status'),
        {'schema': 'modules'},
    )
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    course_id = Column(String(100), ForeignKey('modules.learning_courses.course_id'), nullable=False)
    chapter_id = Column(String(40), nullable=False)
    tier = Column(String(20), nullable=False)
    source_hash = Column(String(64), nullable=False)
    cache_key = Column(String(64), nullable=False)
    prompt_version = Column(String(40), nullable=False)
    model = Column(String(100), nullable=False)
    provider = Column(String(40), nullable=False, default='openai-compatible')
    endpoint = Column(String(300), nullable=False, default='')
    output_mode = Column(String(30), nullable=False, default='json_object')
    status = Column(String(20), nullable=False)
    source = Column(document, nullable=False)
    content = Column(document)
    raw_response = Column(Text)
    usage = Column(document, nullable=False, default=dict)
    error_code = Column(String(80))
    verified = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime(timezone=True))
