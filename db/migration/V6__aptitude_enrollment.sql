CREATE TABLE modules.learning_enrollments (
    user_id INTEGER NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    subject_id UUID NOT NULL REFERENCES modules.sub_modules_master(sub_module_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), PRIMARY KEY(user_id, subject_id)
);
-- Preserve access for students already using the current published subjects.
INSERT INTO modules.learning_enrollments(user_id, subject_id)
SELECT DISTINCT u.id, c.subject_id FROM public.users u CROSS JOIN modules.learning_courses c;
CREATE TABLE modules.learning_aptitude_profiles (
    user_id INTEGER NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    course_id VARCHAR(100) NOT NULL REFERENCES modules.learning_courses(course_id),
    score DOUBLE PRECISION NOT NULL DEFAULT 0 CHECK(score >= 0 AND score <= 1),
    confidence DOUBLE PRECISION NOT NULL DEFAULT 0 CHECK(confidence >= 0 AND confidence <= 1),
    tier VARCHAR(20) NOT NULL DEFAULT 'default' CHECK(tier IN ('beginner','default','advanced')),
    signals JSONB NOT NULL DEFAULT '{}', evidence_count INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(), PRIMARY KEY(user_id, course_id)
);
GRANT SELECT, INSERT, UPDATE, DELETE ON modules.learning_enrollments, modules.learning_aptitude_profiles TO admin;
