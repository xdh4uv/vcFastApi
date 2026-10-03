"""Bounded request-time generation. Drafts are durable; publication stays operator-only."""
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from sqlalchemy import text
from ..core.config import settings
from ..models.contentModel import ContentGeneration
from ..models.engagementModel import LearningEvent
from .content import cached_lesson, digest, PROMPT_VERSION
from .content_generation import generate, request_lesson, validate_provider, validate_request_options
from .engagement import record_event, utc


def request_variant(db, user_id, source, chapter, tier):
    if not settings.automatic_lessons_enabled or not settings.content_pipeline_enabled:
        raise HTTPException(503, 'Automatic explanations are not enabled.')
    current = cached_lesson(db, source['courseId'], chapter, tier)
    if tier == 'default' or current['status'] == 'ready':
        return {'status': 'available', 'generationId': current['generationId']}
    if db.bind.dialect.name == 'postgresql' and db.execute(text('SELECT current_user')).scalar() != 'vchitr_runtime':
        raise HTTPException(503, 'Explanation generation is temporarily unavailable.')
    if not settings.content_api_key or not settings.content_model or not settings.content_api_base_url:
        raise HTTPException(503, 'Explanation generation is temporarily unavailable.')
    options = settings.content_request_options
    validate_provider(settings.content_provider, settings.content_api_base_url, settings.content_output_mode)
    validate_request_options(settings.content_provider, settings.content_api_base_url, **options)
    key = digest([digest(source), tier, PROMPT_VERSION, settings.content_provider,
                  settings.content_api_base_url, settings.content_model, settings.content_output_mode, options])
    # Reserve global capacity in the same transaction as the generation identity.
    # Transaction-level locks work with Neon's pooled connection and release before inference.
    if db.bind.dialect.name == 'postgresql':
        db.execute(text('SELECT pg_advisory_xact_lock(71020801)'))
    now = datetime.now(timezone.utc)
    active = db.query(ContentGeneration).filter_by(cache_key=key).filter(ContentGeneration.status.in_(['pending', 'ready'])).first()
    if active and active.status == 'pending' and utc(active.created_at) < now - timedelta(seconds=max(300, settings.content_read_timeout * 2 + 60)):
        active.status, active.error_code, active.completed_at = 'failed', 'request_interrupted', now
        db.commit()
        raise HTTPException(429, 'Explanation generation will be available later.', headers={'Retry-After': '300'})
    if active:
        db.commit()
        return {'status': 'pending' if active.status == 'pending' else 'awaiting-review', 'generationId': str(active.id)}
    since = now - timedelta(days=1)
    failed = db.query(ContentGeneration).filter_by(cache_key=key, status='failed').filter(ContentGeneration.created_at >= since).order_by(ContentGeneration.created_at.desc()).all()
    if failed and (len(failed) >= 2 or utc(failed[0].completed_at or failed[0].created_at) > now - timedelta(minutes=5)):
        raise HTTPException(429, 'Explanation generation will be available later.', headers={'Retry-After': '300'})
    if db.query(ContentGeneration).filter(ContentGeneration.created_at >= since).count() >= settings.lesson_generations_per_day:
        raise HTTPException(429, 'Daily explanation budget reached. Existing lessons remain available.', headers={'Retry-After': '3600'})
    if db.query(LearningEvent).filter_by(user_id=user_id, event_type='LESSON_REQUESTED').filter(LearningEvent.created_at >= since).count() >= settings.lesson_requests_per_user_day:
        raise HTTPException(429, 'Daily explanation request limit reached.', headers={'Retry-After': '3600'})
    record_event(db, user_id, source['courseId'], chapter.id, 'LESSON_REQUESTED', {'tier': tier})
    row, called = generate(db, source, tier, settings.content_model,
                          lambda s, t, m: request_lesson(s, t, m, settings.content_api_key,
                              provider=settings.content_provider, base_url=settings.content_api_base_url,
                              output_mode=settings.content_output_mode, **options),
                          provider_name=settings.content_provider, endpoint=settings.content_api_base_url,
                          output_mode=settings.content_output_mode, request_options=options)
    db.commit()
    return {'status': 'awaiting-review' if row.status == 'ready' else row.status,
            'generationId': str(row.id), 'retryAfterSeconds': 300 if row.status == 'failed' else None}
