from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class ReadingUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    eventId: UUID
    sourceKey: str = Field(pattern=r'^[a-f0-9]{64}$')
    section: str = Field(min_length=1, max_length=80)
    seconds: int = Field(ge=0, le=30, strict=True)


class TimingUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    eventId: UUID
    questionId: str = Field(min_length=1, max_length=100)
    seconds: int = Field(ge=1, le=30, strict=True)
