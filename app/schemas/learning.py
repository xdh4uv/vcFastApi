from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Question(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    concept: str = Field(min_length=1)
    difficulty: Literal["foundation", "standard", "challenge"]
    prompt: str = Field(min_length=1)
    options: list[str] = Field(min_length=4, max_length=4)
    answer: int = Field(ge=0, le=3, strict=True)
    explanation: str = Field(min_length=1)

    @model_validator(mode="after")
    def distinct_options(self):
        if len(set(self.options)) != 4 or any(not option.strip() for option in self.options):
            raise ValueError("Questions require four distinct, non-empty options.")
        return self


class LevelSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    level: str = Field(min_length=1, max_length=40)


class AnswerSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answers: dict[str, int] = Field(max_length=200)
    revision: int = Field(ge=0, strict=True)

    @model_validator(mode="before")
    @classmethod
    def strict_answers(cls, value):
        if isinstance(value, dict) and isinstance(value.get("answers"), dict):
            if any(type(answer) is not int for answer in value["answers"].values()):
                raise ValueError("Answer choices must be integer option indexes.")
        return value


class ResetRequest(BaseModel):
    confirm: Literal[True]


class WorkedExample(BaseModel):
    problem: str = Field(min_length=1)
    steps: list[str] = Field(min_length=1)


class Chapter(BaseModel):
    id: str = Field(pattern=r"^ch-[0-9]{2}$")
    title: str = Field(min_length=1)
    goal: str = Field(min_length=1)
    concepts: list[str] = Field(min_length=1)
    example: WorkedExample
    watchFor: str = Field(min_length=1)
    questions: list[Question] = Field(min_length=1)
    finalQuestion: Question


class Course(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1)
    chapters: list[Chapter] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_ids(self):
        chapter_ids = [chapter.id for chapter in self.chapters]
        questions = [q for c in self.chapters for q in [*c.questions, c.finalQuestion]]
        question_ids = [q.id for q in questions]
        if len(set(chapter_ids)) != len(chapter_ids) or len(set(question_ids)) != len(question_ids):
            raise ValueError("Chapter and question IDs must be unique within a course.")
        return self
