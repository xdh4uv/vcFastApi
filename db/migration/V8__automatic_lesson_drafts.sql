-- Allow the runtime to generate unreviewed drafts without approval privileges.
GRANT INSERT (id,course_id,chapter_id,tier,source_hash,cache_key,prompt_version,model,
              provider,endpoint,output_mode,status,source,content,raw_response,usage,
              error_code,created_at,completed_at)
ON modules.learning_content_generations TO admin;
GRANT UPDATE (status,content,raw_response,usage,error_code,completed_at)
ON modules.learning_content_generations TO admin;
ALTER TABLE modules.learning_content_generations ENABLE ROW LEVEL SECURITY;
CREATE POLICY content_runtime_read ON modules.learning_content_generations
    FOR SELECT TO admin USING (true);
CREATE POLICY content_runtime_draft_insert ON modules.learning_content_generations
    FOR INSERT TO admin WITH CHECK (verified = false);
CREATE POLICY content_runtime_draft_update ON modules.learning_content_generations
    FOR UPDATE TO admin USING (verified = false) WITH CHECK (verified = false);
-- Neon admin currently has BYPASSRLS. Column grants and this trigger enforce
-- the publication boundary independently of row security.
CREATE FUNCTION modules.protect_reviewed_lesson() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF current_user = 'admin' AND (NEW.verified OR (TG_OP = 'UPDATE' AND OLD.verified)) THEN
        RAISE EXCEPTION 'Runtime cannot publish or change reviewed lessons' USING ERRCODE = '42501';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER protect_reviewed_lesson
BEFORE INSERT OR UPDATE ON modules.learning_content_generations
FOR EACH ROW EXECUTE FUNCTION modules.protect_reviewed_lesson();
