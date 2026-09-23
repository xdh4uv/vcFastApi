from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import ValidationError
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.security import get_current_user
from ..core.config import settings
from ..models.learningCourseModel import LearningAttempt, LearningCourse, LearningPreference, LearningProgress, LearningConcept
from ..services.adaptive import load_insights, select_questions
from ..services.content import cached_lesson, source_document, digest, PROMPT_VERSION, explanation_depth
from ..models.contentModel import ContentGeneration
from ..schemas.content import GeneratedLesson
from ..models.subModuleMasterModel import SubModuleMaster
from ..models.usersModel import User
from ..schemas.learning import AnswerSubmission, Course, LevelSelection, ResetRequest


def no_cache(response: Response):
    response.headers["Cache-Control"] = "no-store"


def learning_db(db: Session = Depends(get_db)):
    try:
        yield db
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(503, "Learning is temporarily unavailable. Please retry.") from None


router = APIRouter(prefix="/learning", tags=["learning"], dependencies=[Depends(no_cache)])
LEVELS = [
    ("elementary", "Elementary school", "Classes 1–5"),
    ("middle-school", "Middle school", "Classes 6–8"),
    ("high-school", "High school", "Class 10 · NCERT"),
    ("senior-secondary", "Senior secondary", "Classes 11–12"),
    ("undergraduate", "Undergraduate", "Bachelor’s level"),
    ("masters", "Postgraduate", "Master’s level"),
    ("phd", "PhD", "Research level"),
]


def load_course(db, course_id):
    row = db.get(LearningCourse, course_id)
    if row is None:
        raise HTTPException(404, "This course has not been published yet.")
    try:
        course = Course.model_validate(row.content)
        if course.id != course_id:
            raise ValueError("Course version mismatch")
    except (ValidationError, ValueError):
        raise HTTPException(503, "Learning material could not be loaded. Please retry later.") from None
    return course


def subject_view(db, user, subject):
    courses = db.query(LearningCourse.level, LearningCourse.course_id).filter_by(subject_id=subject.sub_module_id).all()
    available = {c.level: c.course_id for c in courses}
    preference = db.get(LearningPreference, (user.id, subject.sub_module_id))
    selected = preference.level if preference else None
    return {"subjectId": str(subject.sub_module_id), "subjectName": subject.sub_module_name,
            "selectedLevel": selected, "courseId": available.get(selected),
            "levels": [{"id": id_, "title": title, "description": description,
                        "available": id_ in available} for id_, title, description in LEVELS]}


@router.get("/subjects/{subject_name}")
def get_subject(subject_name: str, db: Session = Depends(learning_db), user: User = Depends(get_current_user), include_course: bool = False):
    name = subject_name.strip().lower()
    aliases = ["math", "maths", "mathematics"] if name in ("math", "maths", "mathematics") else [name]
    subject = db.query(SubModuleMaster).filter(func.lower(SubModuleMaster.sub_module_name).in_(aliases)).first()
    if not subject:
        raise HTTPException(404, "Subject not found.")
    result = subject_view(db, user, subject)
    if include_course:
        result["course"] = get_course(result["courseId"], db, user) if result["courseId"] else None
    return result


@router.get("/preferences")
def get_preferences(db: Session = Depends(learning_db), user: User = Depends(get_current_user)):
    return [subject_view(db, user, s) for s in db.query(SubModuleMaster).order_by(SubModuleMaster.sub_module_name).all()]


@router.put("/subjects/{subject_id}/level")
def set_level(subject_id: UUID, body: LevelSelection, db: Session = Depends(learning_db), user: User = Depends(get_current_user)):
    subject = db.get(SubModuleMaster, subject_id)
    if not subject:
        raise HTTPException(404, "Subject not found.")
    if not db.query(LearningCourse).filter_by(subject_id=subject_id, level=body.level).first():
        raise HTTPException(422, "Coursework is not available for this level yet.")
    # Serialise preference changes across devices without an insert race.
    db.query(User).filter_by(id=user.id).with_for_update().one()
    preference = db.get(LearningPreference, (user.id, subject_id))
    if preference:
        preference.level = body.level
    else:
        db.add(LearningPreference(user_id=user.id, subject_id=subject_id, level=body.level))
    db.commit()
    return subject_view(db, user, subject)


def lock_progress(db, user_id, course_id):
    """All attempt/reset writes lock this row first, preventing reset/submit races."""
    if not db.get(LearningProgress, (user_id, course_id)):
        try:
            with db.begin_nested():
                db.add(LearningProgress(user_id=user_id, course_id=course_id, read=[]))
                db.flush()
        except IntegrityError:
            pass  # Another request created the same row.
    return db.query(LearningProgress).filter_by(user_id=user_id, course_id=course_id).with_for_update().populate_existing().one()


def history_rows(db, user_id, course_id, test_id=None, kind=None):
    query = db.query(LearningAttempt).filter_by(user_id=user_id, course_id=course_id).filter(LearningAttempt.submitted_at.is_not(None))
    query = query.filter(LearningAttempt.kind == kind) if kind else query.filter(LearningAttempt.kind != "adaptive")
    if test_id is not None:
        query = query.filter_by(test_id=test_id)
    return query.order_by(LearningAttempt.submitted_at, LearningAttempt.id).all()


def summary(attempt):
    return {"id": str(attempt.id), "testId": attempt.test_id, "kind": attempt.kind, "selection": attempt.selection_metadata, "submittedAt": attempt.submitted_at,
            "correct": attempt.correct, "total": attempt.total,
            "percent": round(attempt.correct / attempt.total * 100)}


def progress_view(db, user, course):
    progress = db.get(LearningProgress, (user.id, course.id))
    history = history_rows(db, user.id, course.id)
    completed = {a.test_id for a in history}
    return {"read": progress.read if progress else [], "history": [summary(a) for a in history],
            "finalUnlocked": all(c.id in completed for c in course.chapters)}


@router.get("/courses/{course_id}")
def get_course(course_id: str, db: Session = Depends(learning_db), user: User = Depends(get_current_user)):
    course = load_course(db, course_id)
    return {"id": course.id, "title": course.title, "chapters": [{"id": c.id, "title": c.title} for c in course.chapters],
            "progress": progress_view(db, user, course)}


def find_chapter(course, chapter_id):
    chapter = next((c for c in course.chapters if c.id == chapter_id), None)
    if chapter is None:
        raise HTTPException(404, "Chapter not found.")
    return chapter


@router.get("/courses/{course_id}/chapters/{chapter_id}")
def get_chapter(course_id: str, chapter_id: str, db: Session = Depends(learning_db), user: User = Depends(get_current_user)):
    chapter = find_chapter(load_course(db, course_id), chapter_id)
    adaptive = db.query(LearningConcept.concept_id).filter_by(course_id=course_id, chapter_id=chapter_id).first() is not None
    variant = None
    if settings.content_pipeline_enabled:
        depth = explanation_depth(db, user.id, course_id, chapter_id, adaptive)
        variant = {**cached_lesson(db, course_id, chapter, depth['tier']), 'selection': depth}
    return {**chapter.model_dump(exclude={"questions", "finalQuestion"}), "questionCount": len(chapter.questions),
            "adaptiveAvailable": adaptive, "contentVariant": variant}


@router.put("/courses/{course_id}/chapters/{chapter_id}/read")
def mark_read(course_id: str, chapter_id: str, db: Session = Depends(learning_db), user: User = Depends(get_current_user)):
    course = load_course(db, course_id)
    find_chapter(course, chapter_id)
    progress = lock_progress(db, user.id, course_id)
    progress.read = sorted(set(progress.read) | {chapter_id})
    db.commit()
    return progress_view(db, user, course)


def test_questions(db, user, course, test_id):
    if test_id == "final":
        if not progress_view(db, user, course)["finalUnlocked"]:
            raise HTTPException(403, "Submit every chapter test to unlock the final test.")
        return [c.finalQuestion.model_dump() for c in course.chapters]
    return [q.model_dump() for q in find_chapter(course, test_id).questions]


def attempt_view(attempt):
    result = {"id": str(attempt.id), "testId": attempt.test_id, "kind": attempt.kind, "selection": attempt.selection_metadata, "revision": attempt.revision,
              "answers": attempt.answers, "submittedAt": attempt.submitted_at,
              "questions": [{k: v for k, v in q.items() if k not in ("answer", "explanation")} for q in attempt.questions]}
    if attempt.submitted_at:
        result.update(summary(attempt))
        result["questions"] = attempt.questions
    return result


@router.get("/courses/{course_id}/tests/{test_id}")
def get_test(course_id: str, test_id: str, db: Session = Depends(learning_db), user: User = Depends(get_current_user)):
    course = load_course(db, course_id)
    questions = test_questions(db, user, course, test_id)
    history = history_rows(db, user.id, course_id, test_id)
    draft = db.query(LearningAttempt).filter_by(user_id=user.id, course_id=course_id, test_id=test_id, submitted_at=None).filter(LearningAttempt.kind != "adaptive").first()
    adaptive = db.query(LearningConcept.concept_id).filter_by(course_id=course_id, chapter_id=test_id).first() is not None
    return {"testId": test_id, "title": "Final course test" if test_id == "final" else find_chapter(course, test_id).title + " · Practice",
            "questionCount": len(questions), "attempt": attempt_view(draft or history[-1]) if draft or history else None,
            "history": [summary(a) for a in history], "adaptiveAvailable": adaptive,
            "insights": load_insights(db, user.id, course_id, test_id)[0] if adaptive and history and not draft else None}


@router.post("/courses/{course_id}/tests/{test_id}/attempts")
def start_attempt(course_id: str, test_id: str, db: Session = Depends(learning_db), user: User = Depends(get_current_user)):
    course = load_course(db, course_id)
    lock_progress(db, user.id, course_id)
    questions = test_questions(db, user, course, test_id)
    attempt = db.query(LearningAttempt).filter_by(user_id=user.id, course_id=course_id, test_id=test_id, submitted_at=None).filter(LearningAttempt.kind != "adaptive").first()
    if not attempt:
        attempt = LearningAttempt(user_id=user.id, course_id=course_id, test_id=test_id, kind="final" if test_id == "final" else "chapter", questions=questions, answers={})
        db.add(attempt)
    db.flush()
    result = attempt_view(attempt)
    db.commit()
    return result


def owned_attempt(db, user, course_id, attempt_id):
    load_course(db, course_id)
    lock_progress(db, user.id, course_id)
    attempt = db.query(LearningAttempt).filter_by(id=attempt_id, user_id=user.id, course_id=course_id).first()
    if not attempt:
        raise HTTPException(404, "Attempt not found. It may have been reset; reload the course.")
    return attempt


def validate_answers(attempt, body, complete=False):
    questions = {q["id"]: q for q in attempt.questions}
    if any(id_ not in questions or answer < 0 or answer >= len(questions[id_]["options"]) for id_, answer in body.answers.items()):
        raise HTTPException(422, "Invalid question or answer choice.")
    if complete and set(body.answers) != set(questions):
        raise HTTPException(422, "Answer every question before submitting.")
    if body.revision != attempt.revision:
        raise HTTPException(409, "This draft changed on another device. Reload before continuing.")


@router.put("/courses/{course_id}/attempts/{attempt_id}/draft")
def save_draft(course_id: str, attempt_id: UUID, body: AnswerSubmission, db: Session = Depends(learning_db), user: User = Depends(get_current_user)):
    attempt = owned_attempt(db, user, course_id, attempt_id)
    if attempt.submitted_at:
        raise HTTPException(409, "This test has already been submitted.")
    validate_answers(attempt, body)
    attempt.answers = body.answers
    attempt.revision += 1
    result = attempt_view(attempt)
    db.commit()
    return result


@router.post("/courses/{course_id}/attempts/{attempt_id}/submit")
def submit_attempt(course_id: str, attempt_id: UUID, body: AnswerSubmission, db: Session = Depends(learning_db), user: User = Depends(get_current_user)):
    attempt = owned_attempt(db, user, course_id, attempt_id)
    if attempt.submitted_at:
        if body.answers != attempt.answers:
            raise HTTPException(409, "This attempt has already been submitted. Start a retake.")
        result = attempt_view(attempt)  # Idempotent retry after an uncertain response.
        if attempt.kind == "adaptive":
            result["insights"] = load_insights(db, user.id, course_id, attempt.test_id)[0]
        return result
    validate_answers(attempt, body, complete=True)
    if attempt.kind != "adaptive":
        test_questions(db, user, load_course(db, course_id), attempt.test_id)
    attempt.answers = body.answers
    attempt.correct = sum(body.answers[q["id"]] == q["answer"] for q in attempt.questions)
    attempt.total = len(attempt.questions)
    attempt.submitted_at = datetime.now(timezone.utc)
    attempt.revision += 1
    db.flush()
    db.refresh(attempt)
    result = attempt_view(attempt)
    if attempt.kind == "adaptive":
        result["insights"] = load_insights(db, user.id, course_id, attempt.test_id)[0]
    # Build the response while the progress lock still prevents a concurrent reset.
    db.commit()
    return result


@router.post("/courses/{course_id}/reset")
def reset_results(course_id: str, body: ResetRequest, db: Session = Depends(learning_db), user: User = Depends(get_current_user)):
    course = load_course(db, course_id)
    lock_progress(db, user.id, course_id)
    db.query(LearningAttempt).filter_by(user_id=user.id, course_id=course_id).delete(synchronize_session=False)
    db.commit()
    return progress_view(db, user, course)


@router.get("/courses/{course_id}/chapters/{chapter_id}/insights")
def get_insights(course_id: str, chapter_id: str, db: Session = Depends(learning_db), user: User = Depends(get_current_user)):
    find_chapter(load_course(db, course_id), chapter_id)
    return load_insights(db, user.id, course_id, chapter_id)[0]


@router.get("/courses/{course_id}/chapters/{chapter_id}/practice")
def get_practice(course_id: str, chapter_id: str, db: Session = Depends(learning_db), user: User = Depends(get_current_user)):
    chapter = find_chapter(load_course(db, course_id), chapter_id)
    insights, attempts = load_insights(db, user.id, course_id, chapter_id)
    history = sorted((a for a in attempts if a.kind == "adaptive" and a.submitted_at), key=lambda a: (a.submitted_at, str(a.id)))
    draft = next((a for a in attempts if a.kind == "adaptive" and not a.submitted_at), None)
    latest = draft or (history[-1] if history else None)
    return {"testId": chapter_id, "kind": "adaptive", "title": chapter.title + " · Focused practice",
            "questionCount": len(latest.questions) if latest else 5, "attempt": attempt_view(latest) if latest else None,
            "history": [summary(a) for a in history], "insights": insights}


@router.post("/courses/{course_id}/chapters/{chapter_id}/practice")
def start_practice(course_id: str, chapter_id: str, db: Session = Depends(learning_db), user: User = Depends(get_current_user)):
    find_chapter(load_course(db, course_id), chapter_id)
    lock_progress(db, user.id, course_id)
    insights, attempts = load_insights(db, user.id, course_id, chapter_id)
    draft = next((a for a in attempts if a.kind == "adaptive" and not a.submitted_at), None)
    if not draft:
        questions, metadata = select_questions(db, course_id, chapter_id, insights, attempts)
        if not questions:
            raise HTTPException(409, "No suitable practice questions are available.")
        draft = LearningAttempt(user_id=user.id, course_id=course_id, test_id=chapter_id, kind="adaptive",
                                questions=questions, answers={}, selection_metadata=metadata)
        db.add(draft)
    db.flush()
    result = attempt_view(draft)
    db.commit()
    return result

@router.get('/content/{generation_id}')
def get_content_generation(generation_id: UUID, db: Session = Depends(learning_db), user: User = Depends(get_current_user)):
    if not settings.content_pipeline_enabled:
        raise HTTPException(404, 'Lesson versions are not enabled.')
    row = db.get(ContentGeneration, generation_id)
    if not row or row.status != 'ready':
        raise HTTPException(404, 'Lesson version not available.')
    chapter = find_chapter(load_course(db, row.course_id), row.chapter_id)
    if row.prompt_version != PROMPT_VERSION or row.source_hash != digest(source_document(db, row.course_id, chapter)):
        raise HTTPException(410, 'Lesson source changed. Reopen the chapter for current material.')
    try:
        content = GeneratedLesson.model_validate(row.content).model_dump()
    except ValidationError:
        raise HTTPException(503, 'Lesson version is unavailable.') from None
    return {'id': str(row.id), 'courseId': row.course_id, 'chapterId': row.chapter_id, 'tier': row.tier,
            'verified': row.verified, 'generated': content}
