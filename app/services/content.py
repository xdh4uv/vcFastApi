"""Read published lessons without a provider call on the student request path."""
import hashlib
import json

from pydantic import ValidationError
from ..models.contentModel import ContentGeneration
from ..models.learningCourseModel import LearningConcept
from ..schemas.content import GeneratedLesson
from .adaptive import load_insights

PROMPT_VERSION = 'lesson-v1'


def explanation_depth(db, user_id, course_id, chapter_id, adaptive_available):
    evidence = {'tier': 'default', 'evidenceCount': 0, 'percent': None, 'reason': 'more-evidence-needed'}
    if not adaptive_available:
        return evidence
    insights, _ = load_insights(db, user_id, course_id, chapter_id)
    concepts = insights['concepts']
    count = sum(c['evidenceCount'] for c in concepts)
    correct = sum(c['correct'] for c in concepts)
    percent = round(100 * correct / count) if count else None
    evidence.update(evidenceCount=count, percent=percent)
    # Reuse fresh first-answer evidence (up to five answers per concept). Repeated retakes add none.
    if count >= 10 and all(c['evidenceCount'] >= 1 for c in concepts):
        ratio = correct / count
        evidence.update(tier='beginner' if ratio < .6 else 'advanced' if ratio >= .8 else 'default', reason='chapter-results')
    return evidence


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def source_document(db, course_id, chapter):
    cards = db.query(LearningConcept).filter_by(course_id=course_id, chapter_id=chapter.id).order_by(LearningConcept.concept_id).all()
    return {'courseId': course_id, 'chapter': chapter.model_dump(exclude={'questions', 'finalQuestion'}),
            'revisionCards': [{k: v for k, v in c.material.items() if k != 'legacyLabels'} for c in cards]}


def cached_lesson(db, course_id, chapter, tier):
    metadata = {'requestedTier': tier, 'servedTier': 'default', 'status': 'base', 'generationId': None,
                'verified': False, 'generated': None}
    if tier == 'default':
        return metadata
    source = source_document(db, course_id, chapter)
    row = db.query(ContentGeneration).filter_by(course_id=course_id, chapter_id=chapter.id, tier=tier,
        source_hash=digest(source), prompt_version=PROMPT_VERSION, status='ready').order_by(ContentGeneration.created_at.desc()).first()
    if row:
        try:
            content = GeneratedLesson.model_validate(row.content).model_dump()
        except ValidationError:
            metadata['status'] = 'unavailable'
            return metadata
        return {**metadata, 'servedTier': tier, 'status': 'ready', 'generationId': str(row.id),
                'verified': row.verified, 'generated': content}
    metadata['status'] = 'unavailable'
    return metadata
