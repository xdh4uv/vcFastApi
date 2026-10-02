"""Inspect a generation; approve explicitly only after reviewing maths and curriculum scope."""
import argparse
import json
from uuid import UUID

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.contentModel import ContentGeneration
from app.models.learningCourseModel import LearningCourse
from app.schemas.learning import Course
from app.services.content import PROMPT_VERSION, digest, source_document
from app.services.content_generation import validation_issues
from app.services.content_quality import quality_issues


def approve(db, row, source):
    if row.status != 'ready' or row.prompt_version != PROMPT_VERSION or row.source_hash != digest(source):
        raise ValueError('Only a ready generation of the current source and prompt can be reviewed.')
    issues = validation_issues(json.dumps(row.content))
    if not issues:
        issues = quality_issues(row.content, source)
    if issues:
        raise ValueError('Quality checks failed: ' + json.dumps(issues))
    row.verified = True
    db.commit()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('generation_id', type=UUID)
    parser.add_argument('--approve', action='store_true', help='Confirm you have checked all worked solutions, exercises and curriculum scope.')
    args = parser.parse_args()
    url = make_url(settings.database_url_unpooled or settings.database_url)
    if args.approve and (not settings.database_url_unpooled or '-pooler' in (url.host or '')):
        parser.error('Approval requires DATABASE_URL_UNPOOLED with the direct owner connection.')
    engine = create_engine(url)
    try:
        with Session(engine) as db:
            row = db.get(ContentGeneration, args.generation_id)
            if not row:
                raise SystemExit('Generation not found.')
            print(json.dumps({'id': str(row.id), 'status': row.status, 'verified': row.verified,
                              'promptVersion': row.prompt_version, 'content': row.content}, ensure_ascii=False, indent=2))
            if args.approve:
                record = db.get(LearningCourse, row.course_id)
                if not record:
                    raise SystemExit('Course no longer available.')
                course = Course.model_validate(record.content)
                chapter = next((c for c in course.chapters if c.id == row.chapter_id), None)
                if not chapter:
                    raise SystemExit('Chapter no longer available.')
                try:
                    approve(db, row, source_document(db, course.id, chapter))
                except ValueError as exc:
                    raise SystemExit(str(exc)) from None
                print('Approved. Serving still requires CONTENT_PIPELINE_ENABLED=true.')
            else:
                print('Inspection only; no approval or database write.')
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
