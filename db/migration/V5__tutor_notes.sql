CREATE TABLE modules.learning_doubts (
    id UUID PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    course_id VARCHAR(100) NOT NULL REFERENCES modules.learning_courses(course_id),
    chapter_id VARCHAR(40) NOT NULL,
    question TEXT NOT NULL, answer TEXT,
    tier VARCHAR(20) NOT NULL CHECK(tier IN ('beginner','default','advanced')),
    status VARCHAR(20) NOT NULL CHECK(status IN ('pending','ready','failed')),
    helpful BOOLEAN, flagged BOOLEAN NOT NULL DEFAULT false,
    usage JSONB NOT NULL DEFAULT '{}', error_code VARCHAR(80),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), completed_at TIMESTAMPTZ
);
CREATE INDEX ix_doubt_owner_chapter ON modules.learning_doubts(user_id, course_id, chapter_id, created_at);
CREATE TABLE modules.learning_saved_notes (
    id UUID PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    turn_id UUID NOT NULL REFERENCES modules.learning_doubts(id),
    course_id VARCHAR(100) NOT NULL REFERENCES modules.learning_courses(course_id),
    chapter_id VARCHAR(40) NOT NULL,
    question TEXT NOT NULL, answer TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), UNIQUE(user_id, turn_id)
);
CREATE INDEX ix_notes_owner_time ON modules.learning_saved_notes(user_id, created_at);
GRANT SELECT, INSERT, UPDATE, DELETE ON modules.learning_doubts, modules.learning_saved_notes TO admin;
