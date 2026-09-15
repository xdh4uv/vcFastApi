"""Deterministic practice policy v1. Evidence is derived from saved snapshots."""
from collections import Counter

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import load_only

from ..models.learningCourseModel import LearningAttempt, LearningConcept, PracticeQuestion
from ..schemas.adaptive import AdaptiveQuestion, Concept

DIFFICULTIES = ["foundation", "standard", "challenge"]
POLICY = "concept-practice-v1"


def concept_evidence(concepts, attempts):
    aliases = {label: c.id for c in concepts for label in c.legacyLabels}
    evidence = {c.id: [] for c in concepts}
    counted = set()
    submitted = sorted((a for a in attempts if a.submitted_at), key=lambda a: (a.submitted_at, str(a.id)))
    for attempt in submitted:
        repeats = set((attempt.selection_metadata or {}).get("repeatedQuestionIds", []))
        for q in attempt.questions:
            if q["id"] in counted:
                continue
            counted.add(q["id"])
            concept = q.get("conceptId") or aliases.get(q.get("concept"))
            if concept in evidence and q["id"] not in repeats:
                evidence[concept].append((attempt.answers.get(q["id"]) == q["answer"], q["difficulty"]))
    result = []
    for concept in concepts:
        records = evidence[concept.id]
        current, window = 1, []
        for index, (correct, difficulty) in enumerate(records):
            if index == 0 and not correct:
                current = 0
                continue
            if difficulty == DIFFICULTIES[current]:
                window.append(correct)
                if len(window) >= 3 and all(window[-3:]) and current < 2:
                    current += 1; window = []
                elif len(window) >= 2 and sum(not value for value in window[-3:]) >= 2 and current > 0:
                    current -= 1; window = []
        recent = records[-5:]
        correct = sum(item[0] for item in recent)
        percent = round(100 * correct / len(recent)) if recent else None
        status = "insufficient" if len(recent) < 3 else "revise" if percent < 60 else "practise" if percent < 80 else "positive"
        priority = 0 if (recent and not recent[-1][0]) or status == "revise" else 1 if not recent else 2 if status in ("insufficient", "practise") else 3
        result.append({**concept.model_dump(exclude={"legacyLabels"}), "evidenceCount": len(recent), "correct": correct,
                       "percent": percent, "status": status, "priority": priority, "nextDifficulty": DIFFICULTIES[current]})
    return sorted(result, key=lambda item: (item["priority"], item["id"]))


def load_insights(db, user_id, course_id, chapter_id):
    rows = db.query(LearningConcept).filter_by(course_id=course_id, chapter_id=chapter_id).order_by(LearningConcept.concept_id).all()
    if not rows:
        raise HTTPException(404, "Focused practice is not published for this chapter yet.")
    try:
        concepts = [Concept.model_validate(row.material) for row in rows]
    except ValidationError:
        raise HTTPException(503, "Revision material could not be loaded.") from None
    attempts = db.query(LearningAttempt).filter_by(user_id=user_id, course_id=course_id, test_id=chapter_id).all()
    return {"chapterId": chapter_id, "policyVersion": POLICY, "concepts": concept_evidence(concepts, attempts)}, attempts


def select_questions(db, course_id, chapter_id, insights, attempts):
    # Query metadata first; only selected question documents are loaded.
    bank = db.query(PracticeQuestion).options(load_only(PracticeQuestion.id, PracticeQuestion.concept_id, PracticeQuestion.difficulty)).filter_by(
        course_id=course_id, chapter_id=chapter_id, status="approved").order_by(PracticeQuestion.id).all()
    if not bank:
        raise HTTPException(409, "No approved practice questions are available yet.")
    seen = {q["id"] for a in attempts for q in a.questions}
    fresh = [q for q in bank if q.id not in seen]
    pool = fresh or bank
    selected = []
    concepts = insights["concepts"]
    weak = [c for c in concepts if c["priority"] == 0]
    targets = [weak[i % len(weak)] for i in range(3)] if weak else concepts[:3]
    targets += [c for c in concepts if c not in targets][:2]
    # Fill coverage slots if there is only one concept or a target bank is exhausted.
    targets += concepts * 5
    for target in targets:
        candidates = [q for q in pool if q.id not in {s.id for s in selected} and q.concept_id == target["id"]]
        if not candidates:
            continue
        desired = DIFFICULTIES.index(target["nextDifficulty"])
        chosen = min(candidates, key=lambda q: (abs(DIFFICULTIES.index(q.difficulty) - desired), DIFFICULTIES.index(q.difficulty), q.id))
        selected.append(chosen)
        if len(selected) == 5:
            break
    ids = [q.id for q in selected]
    documents = {q.id: q for q in db.query(PracticeQuestion).filter(PracticeQuestion.id.in_(ids)).all()}
    try:
        questions = []
        for item in selected:
            row = documents[item.id]
            q = AdaptiveQuestion.model_validate(row.content)
            if q.id != row.id or q.conceptId != row.concept_id or q.difficulty != row.difficulty:
                raise ValueError("Question metadata mismatch")
            questions.append(q.model_dump())
    except (ValidationError, ValueError):
        raise HTTPException(503, "Practice questions could not be loaded.") from None
    repeated = [id_ for id_ in ids if id_ in seen]
    metadata = {"policyVersion": POLICY, "focusConcepts": list(dict.fromkeys(q["concept"] for q in questions)),
                "difficultyMix": dict(Counter(q["difficulty"] for q in questions)),
                "repeatedQuestionIds": repeated, "freshCount": len(ids) - len(repeated),
                "mode": "revision" if repeated else "fresh"}
    return questions, metadata
