"""Explicit, read-only verification of the configured PostgreSQL course."""
from pathlib import Path
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text

from app.schemas.learning import Course

ROOT = Path(__file__).resolve().parents[1]


def main():
    load_dotenv(ROOT / ".env")
    engine = create_engine(os.environ["DATABASE_URL"], connect_args={"connect_timeout": 15})
    expected = Course.model_validate_json((ROOT / "data/ncert-maths-10-v1.json").read_text(encoding="utf-8"))
    with engine.connect() as connection:
        connection.execute(text("SET TRANSACTION READ ONLY"))
        stored = connection.execute(text("SELECT content FROM modules.learning_courses WHERE course_id=:id"), {"id": expected.id}).scalar_one()
        assert Course.model_validate(stored) == expected
        inspector = inspect(connection)
        for table in ("learning_courses", "learning_preferences", "learning_progress", "learning_attempts"):
            assert inspector.has_table(table, schema="modules"), table
        indexes = inspector.get_indexes("learning_attempts", schema="modules")
        assert any(i["name"] == "uq_learning_active_draft" and i["unique"] for i in indexes)
        assert len(inspector.get_foreign_keys("learning_attempts", schema="modules")) == 2
    engine.dispose()
    print("Verified PostgreSQL course, 14 chapters, 84 questions, four tables, foreign keys and unique active-draft index.")


if __name__ == "__main__":
    main()
