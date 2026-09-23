"""Pre-generate shared lesson variants from DB content. No student data is sent."""
import argparse
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--course', default='ncert-maths-10-v1')
    parser.add_argument('--chapter', default='ch-01', help='Chapter id or all')
    parser.add_argument('--tier', choices=['beginner', 'advanced', 'both'], default='beginner')
    parser.add_argument('--max-generations', type=int, default=1, help='Maximum paid calls in this run (1–28)')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--migrate', action='store_true', help='Apply additive migration 003 before generation')
    parser.add_argument('--migrate-only', action='store_true', help='Apply schema 003 without a provider key or call')
    parser.add_argument('--recover-pending', action='store_true', help='Mark interrupted jobs failed under the exclusive publisher lock')
    args = parser.parse_args()
    if args.dry_run and (args.migrate or args.migrate_only or args.recover_pending):
        parser.error('--dry-run cannot be combined with migration or recovery writes.')
    if args.migrate_only and args.recover_pending:
        parser.error('Run recovery separately from --migrate-only.')
    if not 1 <= args.max_generations <= 28:
        parser.error('--max-generations must be between 1 and 28')
    load_dotenv(Path(__file__).resolve().parents[1] / '.env')
    # Imports after env loading: settings and ORM need the configured database.
    from app.models.contentModel import ContentGeneration
    from app.models.learningCourseModel import LearningCourse
    from app.schemas.learning import Course
    from app.services.content import source_document
    from app.services.content_generation import generate, request_lesson, validate_provider
    if not os.environ.get('DATABASE_URL_UNPOOLED'):
        parser.error('Set DATABASE_URL_UNPOOLED to the schema owner direct connection.')
    url = make_url(os.environ['DATABASE_URL_UNPOOLED'])
    if '-pooler' in (url.host or ''):
        parser.error('Use a direct schema-owner connection, not the pooler.')
    model = os.environ.get('CONTENT_MODEL', '').strip()
    key = os.environ.get('CONTENT_API_KEY', '').strip()
    provider = os.environ.get('CONTENT_PROVIDER', 'openai-compatible').strip()
    base_url = os.environ.get('CONTENT_API_BASE_URL', '').strip().rstrip('/')
    output_mode = os.environ.get('CONTENT_OUTPUT_MODE', 'json_object').strip()
    if not args.dry_run and not args.migrate_only:
        if not model or not key or not base_url:
            parser.error('Configure CONTENT_MODEL, CONTENT_API_KEY and CONTENT_API_BASE_URL before generation.')
        validate_provider(provider, base_url, output_mode)
    engine = create_engine(url, connect_args={'connect_timeout': 15})
    count = 0
    with engine.connect() as connection:
        # Direct connection stays checked out across commits: session advisory lock remains held.
        if not connection.execute(text('SELECT pg_try_advisory_lock(71020403)')).scalar():
            raise SystemExit('Another content publisher is active. Retry after it finishes.')
        connection.commit()
        try:
            if args.migrate or args.migrate_only:
                connection.execute(text((Path(__file__).resolve().parents[1] / 'migrations/003_content_pipeline.sql').read_text()))
                connection.commit()
                if args.migrate_only:
                    print('Applied content schema 003; no provider call.')
                    return
            with Session(bind=connection) as db:
                if args.recover_pending:
                    if args.dry_run:
                        parser.error('Recovery is a write; omit --dry-run.')
                    from datetime import datetime, timezone
                    db.query(ContentGeneration).filter_by(status='pending').update(
                        {'status': 'failed', 'error_code': 'publisher_interrupted', 'completed_at': datetime.now(timezone.utc)})
                    db.commit()
                record = db.get(LearningCourse, args.course)
                if not record:
                    raise SystemExit('Course not found.')
                course = Course.model_validate(record.content)
                chapters = [c for c in course.chapters if args.chapter == 'all' or c.id == args.chapter]
                if not chapters:
                    raise SystemExit('Chapter not found.')
                for chapter in chapters:
                    source = source_document(db, course.id, chapter)
                    for tier in ['beginner', 'advanced'] if args.tier == 'both' else [args.tier]:
                        if args.dry_run:
                            print(f'{chapter.id} {tier}: source ready; no provider call')
                            continue
                        if count >= args.max_generations:
                            print('Paid-call limit reached. Rerun to continue; completed variants are reused.')
                            break
                        row, called = generate(db, source, tier, model,
                            lambda s, t, m: request_lesson(s, t, m, key, provider=provider, base_url=base_url, output_mode=output_mode),
                            provider_name=provider, endpoint=base_url, output_mode=output_mode)
                        count += int(called)
                        print(f'{chapter.id} {tier}: {row.status} id={row.id} calls={count} error={row.error_code or "none"}')
                        if row.status == 'failed':
                            raise SystemExit('Generation failed; stopped to avoid further spend. Inspect stored error and usage.')
        finally:
            connection.rollback()
            connection.execute(text('SELECT pg_advisory_unlock(71020403)'))
            connection.commit()
    engine.dispose()


if __name__ == '__main__':
    main()
