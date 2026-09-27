-- Local/CI only: this folder is never passed to Flyway for the remote database.
-- Minimal catalogue so the learning seeds can find the Maths subject.
INSERT INTO modules.sub_modules_master (sub_module_id, sub_module_name, sub_module_description)
SELECT '00000000-0000-4000-8000-000000000001', 'Maths', 'Class 10 Mathematics (local development)'
WHERE NOT EXISTS (
    SELECT 1 FROM modules.sub_modules_master WHERE lower(sub_module_name) IN ('math', 'maths', 'mathematics')
);
