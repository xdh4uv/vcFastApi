-- NOLOGIN until an operator provisions credentials; passwords never live in migrations.
CREATE ROLE vchitr_runtime NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
GRANT USAGE ON SCHEMA public, modules TO vchitr_runtime;
GRANT SELECT, INSERT, UPDATE ON public.users TO vchitr_runtime;
GRANT USAGE, SELECT ON SEQUENCE public.users_id_seq TO vchitr_runtime;
GRANT SELECT ON modules.modules_master, modules.sub_modules_master,
    modules.sub_modules_details, modules.learning_courses, modules.learning_concepts,
    modules.learning_practice_questions, modules.learning_content_generations TO vchitr_runtime;
GRANT SELECT, INSERT, UPDATE, DELETE ON modules.learning_preferences,
    modules.learning_progress, modules.learning_attempts, modules.learning_reading_progress,
    modules.learning_events, modules.learning_attempt_timing, modules.learning_doubts,
    modules.learning_saved_notes, modules.learning_enrollments,
    modules.learning_aptitude_profiles TO vchitr_runtime;
GRANT INSERT (id,course_id,chapter_id,tier,source_hash,cache_key,prompt_version,model,
    provider,endpoint,output_mode,status,source,content,raw_response,usage,
    error_code,created_at,completed_at) ON modules.learning_content_generations TO vchitr_runtime;
GRANT UPDATE (status,content,raw_response,usage,error_code,completed_at)
    ON modules.learning_content_generations TO vchitr_runtime;
CREATE POLICY content_app_read ON modules.learning_content_generations
    FOR SELECT TO vchitr_runtime USING (true);
CREATE POLICY content_app_draft_insert ON modules.learning_content_generations
    FOR INSERT TO vchitr_runtime WITH CHECK (verified = false);
CREATE POLICY content_app_draft_update ON modules.learning_content_generations
    FOR UPDATE TO vchitr_runtime USING (verified = false) WITH CHECK (verified = false);
CREATE OR REPLACE FUNCTION modules.protect_reviewed_lesson() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF current_user IN ('admin','vchitr_runtime') AND
        (NEW.verified OR (TG_OP = 'UPDATE' AND OLD.verified)) THEN
        RAISE EXCEPTION 'Runtime cannot publish or change reviewed lessons' USING ERRCODE = '42501';
    END IF;
    RETURN NEW;
END;
$$;
