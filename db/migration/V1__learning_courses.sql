-- Additive migration. Existing module, subject and user tables are untouched.
CREATE SCHEMA IF NOT EXISTS modules;
CREATE TABLE IF NOT EXISTS modules.learning_courses (
    course_id VARCHAR(100) PRIMARY KEY,
    subject_id UUID NOT NULL REFERENCES modules.sub_modules_master(sub_module_id),
    level VARCHAR(40) NOT NULL,
    content JSONB NOT NULL,
    UNIQUE (subject_id, level),
    CONSTRAINT learning_course_document CHECK (
        jsonb_typeof(content) = 'object'
        AND content ? 'id'
        AND content->>'id' = course_id
        AND content ? 'chapters'
        AND jsonb_typeof(content->'chapters') = 'array'
        AND jsonb_array_length(content->'chapters') > 0
    )
);

CREATE TABLE IF NOT EXISTS modules.learning_preferences (
    user_id INTEGER NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    subject_id UUID NOT NULL REFERENCES modules.sub_modules_master(sub_module_id),
    level VARCHAR(40) NOT NULL,
    PRIMARY KEY (user_id, subject_id)
);
CREATE TABLE IF NOT EXISTS modules.learning_progress (
    user_id INTEGER NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    course_id VARCHAR(100) NOT NULL REFERENCES modules.learning_courses(course_id),
    read JSONB NOT NULL DEFAULT '[]',
    PRIMARY KEY (user_id, course_id)
);
CREATE TABLE IF NOT EXISTS modules.learning_attempts (
    id UUID PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    course_id VARCHAR(100) NOT NULL REFERENCES modules.learning_courses(course_id),
    test_id VARCHAR(40) NOT NULL,
    questions JSONB NOT NULL,
    answers JSONB NOT NULL DEFAULT '{}',
    revision INTEGER NOT NULL DEFAULT 0,
    correct INTEGER,
    total INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    submitted_at TIMESTAMPTZ,
    CHECK ((submitted_at IS NULL AND correct IS NULL AND total IS NULL)
        OR (submitted_at IS NOT NULL AND correct IS NOT NULL AND total IS NOT NULL AND total > 0 AND correct BETWEEN 0 AND total))
);
CREATE INDEX IF NOT EXISTS ix_learning_attempt_owner_course ON modules.learning_attempts(user_id, course_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_learning_active_draft ON modules.learning_attempts(user_id, course_id, test_id)
    WHERE submitted_at IS NULL;
