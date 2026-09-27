-- Expand existing storage; preserve all saved answers and question snapshots.
ALTER TABLE modules.learning_attempts ADD COLUMN IF NOT EXISTS kind VARCHAR(20) NOT NULL DEFAULT 'chapter';
ALTER TABLE modules.learning_attempts ADD COLUMN IF NOT EXISTS selection_metadata JSONB NOT NULL DEFAULT '{}';
UPDATE modules.learning_attempts SET kind='final' WHERE test_id='final' AND kind='chapter';
DROP INDEX IF EXISTS modules.uq_learning_active_draft;
CREATE UNIQUE INDEX uq_learning_active_draft ON modules.learning_attempts(user_id, course_id, test_id, kind) WHERE submitted_at IS NULL;
CREATE TABLE IF NOT EXISTS modules.learning_concepts (
    course_id VARCHAR(100) REFERENCES modules.learning_courses(course_id),
    chapter_id VARCHAR(40), concept_id VARCHAR(60), material JSONB NOT NULL,
    PRIMARY KEY(course_id, chapter_id, concept_id)
);
CREATE TABLE IF NOT EXISTS modules.learning_practice_questions (
    id VARCHAR(100) PRIMARY KEY,
    course_id VARCHAR(100) NOT NULL, chapter_id VARCHAR(40) NOT NULL, concept_id VARCHAR(60) NOT NULL,
    difficulty VARCHAR(20) NOT NULL CHECK (difficulty IN ('foundation','standard','challenge')),
    status VARCHAR(20) NOT NULL CHECK (status IN ('draft','approved')),
    source VARCHAR(30) NOT NULL, content JSONB NOT NULL,
    FOREIGN KEY(course_id,chapter_id,concept_id) REFERENCES modules.learning_concepts(course_id,chapter_id,concept_id)
);
CREATE INDEX IF NOT EXISTS ix_practice_selection ON modules.learning_practice_questions(course_id,chapter_id,status,concept_id,difficulty);
GRANT SELECT ON modules.learning_concepts, modules.learning_practice_questions TO admin;
