-- Fresh local/CI schemas need this pre-Flyway table for runtime catalogue grants.
-- Reconstructed from the existing Neon schema. This directory is never used remotely.
CREATE TABLE modules.sub_modules_details (
    sub_module_details_id UUID PRIMARY KEY,
    sub_module_id UUID,
    module_id UUID,
    chapter_name VARCHAR(255),
    chapter_description TEXT,
    created_at TIMESTAMP
);
