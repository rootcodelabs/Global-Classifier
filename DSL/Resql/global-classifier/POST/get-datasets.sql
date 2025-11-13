SELECT 
    id,
    major,
    minor,
    created_at,
    generation_status,
    last_model_trained,
    last_trained,
    CEIL(COUNT(*) OVER() / :page_size::DECIMAL) AS total_pages
FROM 
    dataset_versions
WHERE
    (:generation_status = 'all' OR generation_status ILIKE '%' || :generation_status || '%')
    AND (:dataset_name = 'all' 
         OR POSITION(LOWER(:dataset_name) IN LOWER(CONCAT('v', major, '.', minor))) > 0
         OR POSITION(LOWER(:dataset_name) IN LOWER(CONCAT(major, '.', minor))) > 0
         OR POSITION(LOWER(:dataset_name) IN LOWER(major::text)) > 0
         OR POSITION(LOWER(:dataset_name) IN LOWER(minor::text)) > 0)
ORDER BY
    CASE WHEN :sort_by = 'created_at' AND :sort_type = 'asc' THEN created_at END ASC,
    CASE WHEN :sort_by = 'created_at' AND :sort_type = 'desc' THEN created_at END DESC,
    -- CASE WHEN :sort_by = 'major' AND :sort_type = 'asc' THEN major END ASC,
    -- CASE WHEN :sort_by = 'major' AND :sort_type = 'desc' THEN major END DESC,
    -- CASE WHEN :sort_by = 'minor' AND :sort_type = 'asc' THEN minor END ASC,
    -- CASE WHEN :sort_by = 'minor' AND :sort_type = 'desc' THEN minor END DESC,
    CASE WHEN :sort_by IS NULL OR :sort_by = '' THEN created_at END DESC
OFFSET ((GREATEST(:page, 1) - 1) * :page_size) LIMIT :page_size;