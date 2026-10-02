-- Correct the reviewed angle justification without rewriting existing attempt snapshots.
-- The three revised questions receive new IDs; old documents remain available for history.
UPDATE modules.learning_concepts
SET material = jsonb_set(material, '{example,steps,0}',
    to_jsonb('The parallel horizontals and shared line of sight give equal alternate interior angles: depression equals elevation.'::text))
WHERE course_id = 'ncert-maths-10-v1' AND chapter_id = 'ch-09' AND concept_id = 'angles'
  AND material #>> '{example,steps,0}' = 'The two horizontals are parallel, so the corresponding angles are equal.';

INSERT INTO modules.learning_practice_questions(id, course_id, chapter_id, concept_id, difficulty, status, source, content)
SELECT replace(id, '-v1-', '-v2-'), course_id, chapter_id, concept_id, difficulty, 'approved', source,
    jsonb_set(jsonb_set(content, '{id}', to_jsonb(replace(id, '-v1-', '-v2-'))), '{explanation}',
        to_jsonb('The parallel horizontals and shared line of sight give equal alternate interior angles: depression equals elevation.'::text))
FROM modules.learning_practice_questions
WHERE course_id = 'ncert-maths-10-v1' AND chapter_id = 'ch-09'
  AND id IN ('c09-v1-04', 'c09-v1-05', 'c09-v1-06')
ON CONFLICT (id) DO NOTHING;

UPDATE modules.learning_practice_questions SET status = 'draft'
WHERE course_id = 'ncert-maths-10-v1' AND chapter_id = 'ch-09'
  AND id IN ('c09-v1-04', 'c09-v1-05', 'c09-v1-06');
