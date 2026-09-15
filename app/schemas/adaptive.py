from pydantic import BaseModel, ConfigDict, Field, model_validator
from .learning import Question, WorkedExample


class Concept(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=r"^[a-z][a-z-]+$")
    title: str = Field(min_length=1)
    legacyLabels: list[str]
    explanation: str = Field(min_length=1)
    example: WorkedExample
    commonMistake: str = Field(min_length=1)
    checklist: list[str] = Field(min_length=1)


class AdaptiveQuestion(Question):
    conceptId: str


class PracticeBank(BaseModel):
    model_config = ConfigDict(extra="forbid")
    courseId: str
    chapterId: str
    concepts: list[Concept] = Field(min_length=1)
    questions: list[AdaptiveQuestion] = Field(min_length=1)

    @model_validator(mode="after")
    def consistent_bank(self):
        ids = {c.id for c in self.concepts}
        if len(ids) != len(self.concepts) or len({q.id for q in self.questions}) != len(self.questions):
            raise ValueError("Concept and question IDs must be unique")
        labels = [label for c in self.concepts for label in c.legacyLabels]
        if len(set(labels)) != len(labels):
            raise ValueError("Legacy labels must map to one concept")
        titles = {c.id: c.title for c in self.concepts}
        if any(q.conceptId not in ids or q.concept != titles[q.conceptId] for q in self.questions):
            raise ValueError("Question concept must match its registered concept")
        return self
