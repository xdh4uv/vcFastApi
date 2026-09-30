"""Check real chapter generation without publishing or modifying the database."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from uuid import uuid4

from dotenv import load_dotenv


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--course', default='ncert-maths-10-v1')
    parser.add_argument('--chapter', default='ch-02')
    parser.add_argument('--tier', choices=['beginner', 'advanced', 'both'], default='both')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    load_dotenv(root / '.env')
    from sqlalchemy import text
    from app.core.config import settings
    from app.core.database import SessionLocal
    from app.models.learningCourseModel import LearningCourse
    from app.schemas.learning import Course
    from app.schemas.content import GeneratedLesson
    from app.services.content import digest, source_document, PROMPT_VERSION
    from app.services.content_generation import request_lesson, GenerationError, validation_issues, validate_provider, validate_request_options

    if not settings.content_model or not settings.content_api_key or not settings.content_api_base_url:
        parser.error('Configure CONTENT_MODEL, CONTENT_API_KEY and CONTENT_API_BASE_URL.')
    try:
        validate_provider(settings.content_provider, settings.content_api_base_url, settings.content_output_mode)
        validate_request_options(settings.content_provider, settings.content_api_base_url, **settings.content_request_options)
    except ValueError as exc:
        parser.error(str(exc))
    try:
        with SessionLocal() as db:
            db.execute(text('SET TRANSACTION READ ONLY'))
            record = db.get(LearningCourse, args.course)
            if not record:
                parser.error('Course not found.')
            course = Course.model_validate(record.content)
            chapter = next((c for c in course.chapters if c.id == args.chapter), None)
            if not chapter:
                parser.error('Chapter not found.')
            source = source_document(db, course.id, chapter)
    except Exception as exc:
        raise SystemExit(f'Course retrieval failed ({type(exc).__name__}); no provider request.') from None
    directory = root / '.content-checks'
    directory.mkdir(exist_ok=True)
    for tier in ['beginner', 'advanced'] if args.tier == 'both' else [args.tier]:
        identifier = str(uuid4())
        report_path = directory / f'{identifier}.json'
        report = {'id': identifier, 'status': 'pending', 'chapter': chapter.id, 'tier': tier,
                  'provider': settings.content_provider, 'model': settings.content_model,
                  'endpoint': settings.content_api_base_url, 'outputMode': settings.content_output_mode,
                  'requestOptions': settings.content_request_options, 'promptVersion': PROMPT_VERSION,
                  'sourceHash': digest(source), 'source': source, 'verified': False,
                  'createdAt': datetime.now(timezone.utc).isoformat()}
        report_path.write_text(json.dumps(report, ensure_ascii=True, indent=2), encoding='utf-8')
        print(f'{chapter.id} {tier}: checking id={identifier}', flush=True)
        started = time.monotonic()
        try:
            raw, usage, reason = request_lesson(source, tier, settings.content_model, settings.content_api_key,
                provider=settings.content_provider, base_url=settings.content_api_base_url,
                output_mode=settings.content_output_mode, **settings.content_request_options)
            report.update(rawResponse=raw, usage=usage, stopReason=reason)
            issues = validation_issues(raw)
            if reason != 'end_turn':
                report.update(status='failed', error='incomplete_or_refused')
            elif issues:
                report.update(status='failed', error='invalid_lesson', validationIssues=issues)
            else:
                report.update(status='valid', lesson=GeneratedLesson.model_validate_json(raw).model_dump())
        except GenerationError as exc:
            report.update(status='failed', error=str(exc))
        report['elapsedSeconds'] = round(time.monotonic() - started, 1)
        report['completedAt'] = datetime.now(timezone.utc).isoformat()
        report_path.write_text(json.dumps(report, ensure_ascii=True, indent=2), encoding='utf-8')
        print(json.dumps({k: report[k] for k in ['id', 'status', 'elapsedSeconds', 'error', 'validationIssues', 'usage'] if k in report}, ensure_ascii=True), flush=True)
        print(f'Report: {report_path}', flush=True)
        if report['status'] != 'valid':
            raise SystemExit('Check failed; stopped. Inspect the local report before retrying. No content published.')
    print('Checks passed. Review the lesson examples for mathematical correctness; no content published.')


if __name__ == '__main__':
    main()
