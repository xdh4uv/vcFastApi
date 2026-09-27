-- Additive: no changes to lessons, assessments, preferences or student history.
CREATE TABLE IF NOT EXISTS modules.learning_content_generations (
    id UUID PRIMARY KEY,
    course_id VARCHAR(100) NOT NULL REFERENCES modules.learning_courses(course_id),
    chapter_id VARCHAR(40) NOT NULL,
    tier VARCHAR(20) NOT NULL CHECK (tier IN ('beginner','advanced')),
    source_hash VARCHAR(64) NOT NULL,
    cache_key VARCHAR(64) NOT NULL,
    prompt_version VARCHAR(40) NOT NULL,
    model VARCHAR(100) NOT NULL,
    provider VARCHAR(40) NOT NULL,
    endpoint VARCHAR(300) NOT NULL,
    output_mode VARCHAR(30) NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('pending','ready','failed')),
    source JSONB NOT NULL,
    content JSONB,
    raw_response TEXT,
    usage JSONB NOT NULL DEFAULT '{}',
    error_code VARCHAR(80),
    verified BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    CHECK (status <> 'ready' OR content IS NOT NULL)
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_content_active_key ON modules.learning_content_generations(cache_key)
    WHERE status IN ('pending','ready');
CREATE INDEX IF NOT EXISTS ix_content_lookup ON modules.learning_content_generations
    (course_id,chapter_id,tier,source_hash,prompt_version,status);
-- Student-facing backend can read. Generation is an operator command using the owner role.
GRANT SELECT ON modules.learning_content_generations TO admin;
