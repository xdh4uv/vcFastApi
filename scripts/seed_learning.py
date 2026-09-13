"""Apply the additive migration and publish a versioned course, atomically.

Run from the repository root: python -m scripts.seed_learning
Use DATABASE_URL_UNPOOLED for Neon migrations. No existing version is overwritten.
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.schemas.learning import Course

ROOT = Path(__file__).resolve().parents[1]


def publish(connection, course: Course):
    connection.execute(text((ROOT / "migrations/001_learning_courses.sql").read_text(encoding="utf-8")))
    subject_id = connection.execute(text(
        "SELECT sub_module_id FROM modules.sub_modules_master WHERE lower(sub_module_name) IN ('math', 'maths', 'mathematics')"
    )).scalar_one()
    connection.execute(text("""
        INSERT INTO modules.learning_courses (course_id, subject_id, level, content)
        VALUES (:id, :subject_id, 'high-school', CAST(:content AS jsonb)) ON CONFLICT (course_id) DO NOTHING
    """), {"id": course.id, "subject_id": subject_id, "content": course.model_dump_json()})
    saved = connection.execute(text(
        "SELECT content FROM modules.learning_courses WHERE course_id = :id"
    ), {"id": course.id}).scalar_one()
    if saved != course.model_dump():
        raise ValueError("An existing course version differs. Publish a new version ID instead of overwriting saved answers.")


def main():
    load_dotenv(ROOT / ".env")
    url = make_url(os.environ.get("DATABASE_URL_UNPOOLED") or os.environ["DATABASE_URL"])
    if "-pooler" in (url.host or ""):
        raise SystemExit("Set DATABASE_URL_UNPOOLED to the direct Neon connection for this migration.")
    course = Course.model_validate_json((ROOT / "data/ncert-maths-10-v1.json").read_text(encoding="utf-8"))
    engine = create_engine(url, connect_args={"connect_timeout": 15})
    with engine.begin() as connection:
        publish(connection, course)
    print(f"Published {course.id}: {len(course.chapters)} chapters, {sum(len(c.questions) + 1 for c in course.chapters)} questions.")
    engine.dispose()


if __name__ == "__main__":
    main()
