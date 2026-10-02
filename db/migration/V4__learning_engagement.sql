CREATE TABLE modules.learning_reading_progress (
    user_id INTEGER NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    course_id VARCHAR(100) NOT NULL REFERENCES modules.learning_courses(course_id),
    chapter_id VARCHAR(40) NOT NULL,
    source_key VARCHAR(64) NOT NULL,
    sections JSONB NOT NULL DEFAULT '{}',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY(user_id, course_id, chapter_id)
);
CREATE TABLE modules.learning_events (
    id UUID PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    course_id VARCHAR(100) NOT NULL REFERENCES modules.learning_courses(course_id),
    chapter_id VARCHAR(40),
    event_type VARCHAR(40) NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_learning_events_owner_time ON modules.learning_events(user_id, course_id, created_at);
CREATE TABLE modules.learning_attempt_timing (
    attempt_id UUID PRIMARY KEY REFERENCES modules.learning_attempts(id) ON DELETE CASCADE,
    seconds JSONB NOT NULL DEFAULT '{}',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
GRANT SELECT, INSERT, UPDATE, DELETE ON modules.learning_reading_progress, modules.learning_events, modules.learning_attempt_timing TO admin;
