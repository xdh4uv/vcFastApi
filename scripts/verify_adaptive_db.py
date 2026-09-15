"""Read-only checks of published adaptive content and runtime access."""
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text
from scripts.seed_adaptive import ROOT, read_bank


def verify(connection):
    bank = read_bank()
    concepts = dict(connection.execute(text('SELECT concept_id, material FROM modules.learning_concepts WHERE course_id=:course AND chapter_id=:chapter'), dict(course=bank.courseId, chapter=bank.chapterId)).all())
    questions = dict(connection.execute(text("SELECT id, content FROM modules.learning_practice_questions WHERE course_id=:course AND chapter_id=:chapter AND status='approved'"), dict(course=bank.courseId, chapter=bank.chapterId)).all())
    assert all(concepts.get(c.id) == c.model_dump() for c in bank.concepts)
    assert all(questions.get(q.id) == q.model_dump() for q in bank.questions)
    index = next(i for i in inspect(connection).get_indexes('learning_attempts', schema='modules') if i['name']=='uq_learning_active_draft')
    assert index['unique'] and index['column_names']==['user_id','course_id','test_id','kind']
    assert len(inspect(connection).get_foreign_keys('learning_practice_questions',schema='modules'))==1


def main():
    load_dotenv(ROOT / '.env')
    engine = create_engine(os.environ['DATABASE_URL'], connect_args={'connect_timeout':15})
    with engine.connect() as connection:
        connection.execute(text('SET TRANSACTION READ ONLY'))
        verify(connection)
    engine.dispose()
    print('Verified 5 revision cards, 45 approved questions, concept foreign key and separate draft uniqueness.')


if __name__ == '__main__':
    main()
