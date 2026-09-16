"""Publish a checked chapter bank atomically; optionally apply migration 002."""
import argparse
import os
import json
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from app.schemas.adaptive import PracticeBank

ROOT = Path(__file__).resolve().parents[1]


BANKS = {'real-numbers': 'real-numbers-practice-v1.json', 'polynomials': 'polynomials-practice-v1.json'}
BANKS.update({name: f'{name}-practice-v1.json' for name in (
    'linear-equations','quadratic-equations','arithmetic-progressions','triangles','coordinate-geometry',
    'trigonometry','trigonometry-applications','circles','circle-areas','surface-areas-volumes','statistics','probability')})


def read_bank(name='real-numbers'):
    return PracticeBank.model_validate_json((ROOT / 'data' / BANKS[name]).read_text(encoding="utf-8"))


def publish(connection, bank, apply_schema=True):
    connection.execute(text("SELECT pg_advisory_xact_lock(71020402)"))
    if apply_schema:
        connection.execute(text((ROOT / "migrations/002_adaptive_practice.sql").read_text(encoding="utf-8")))
    course = connection.execute(text("SELECT content FROM modules.learning_courses WHERE course_id=:id"), {"id": bank.courseId}).scalar_one()
    assert any(c["id"] == bank.chapterId for c in course["chapters"]), "Chapter must exist"
    values = dict(course=bank.courseId, chapter=bank.chapterId,
                  concepts=json.dumps([c.model_dump() for c in bank.concepts]), questions=json.dumps([q.model_dump() for q in bank.questions]))
    connection.execute(text("""INSERT INTO modules.learning_concepts(course_id,chapter_id,concept_id,material)
        SELECT :course,:chapter,c->>'id',c FROM jsonb_array_elements(CAST(:concepts AS jsonb)) c ON CONFLICT DO NOTHING"""), values)
    saved_concepts = dict(connection.execute(text("SELECT concept_id,material FROM modules.learning_concepts WHERE course_id=:course AND chapter_id=:chapter"), values).all())
    if any(saved_concepts.get(c.id) != c.model_dump() for c in bank.concepts):
        raise ValueError("Published concept differs; use an explicit reviewed revision migration")
    connection.execute(text("""INSERT INTO modules.learning_practice_questions(id,course_id,chapter_id,concept_id,difficulty,status,source,content)
        SELECT q->>'id',:course,:chapter,q->>'conceptId',q->>'difficulty','approved','authored',q
        FROM jsonb_array_elements(CAST(:questions AS jsonb)) q ON CONFLICT DO NOTHING"""), values)
    saved = {r.id: r for r in connection.execute(text("SELECT id,concept_id,difficulty,content FROM modules.learning_practice_questions WHERE course_id=:course AND chapter_id=:chapter"), values)}
    if any(q.id not in saved or saved[q.id].content != q.model_dump() or saved[q.id].concept_id != q.conceptId or saved[q.id].difficulty != q.difficulty for q in bank.questions):
        raise ValueError("Published question differs; publish a new question ID")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bank', choices=[*BANKS, 'all'], default='real-numbers')
    parser.add_argument('--content-only', action='store_true', help='Schema 002 must already exist; publish without DDL')
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    url = make_url(os.environ["DATABASE_URL_UNPOOLED"])
    if "-pooler" in (url.host or ""):
        raise SystemExit("Use the schema owner's direct connection for migrations")
    banks = [read_bank(name) for name in BANKS] if args.bank == 'all' else [read_bank(args.bank)]
    engine = create_engine(url, connect_args={"connect_timeout": 15})
    with engine.begin() as connection:
        for index, bank in enumerate(banks):
            publish(connection, bank, apply_schema=not args.content_only and index == 0)
    engine.dispose()
    print(f"Published {len(banks)} banks, {sum(len(b.concepts) for b in banks)} concepts and {sum(len(b.questions) for b in banks)} adaptive questions.")


if __name__ == "__main__":
    main()
