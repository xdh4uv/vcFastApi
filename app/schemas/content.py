"""Bounded, plain-text lesson output; no assessment answers or executable markup."""
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Tier = Literal['beginner', 'default', 'advanced']
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=6000)]


class Example(BaseModel):
    model_config = ConfigDict(extra='forbid')
    problem: Text
    steps: list[Text] = Field(min_length=2, max_length=12)


class LessonSection(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: Text
    explanation: list[Text] = Field(min_length=1, max_length=8)
    example: Example
    checkYourself: Text


class GeneratedLesson(BaseModel):
    model_config = ConfigDict(extra='forbid')
    summary: Text
    sections: list[LessonSection] = Field(min_length=2, max_length=8)
    takeaways: list[Text] = Field(min_length=2, max_length=8)
