from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class DoubtRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    requestId: UUID
    question: str = Field(min_length=1, max_length=2000)


class FeedbackRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    helpful: bool | None = Field(strict=True)


class NoteRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    turnId: UUID
