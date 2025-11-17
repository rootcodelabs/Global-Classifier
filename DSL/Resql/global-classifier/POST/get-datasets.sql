SELECT 
    dv.id,
    dv.major,
    dv.minor,
    dv.created_at,
    dv.generation_status,
    COALESCE(dm.model_name, dv.last_model_trained) AS last_model_trained,
    dv.last_trained,
    CEIL(COUNT(*) OVER() / :page_size::DECIMAL) AS total_pages
FROM 
    dataset_versions dv
LEFT JOIN 
    data_models dm ON dv.last_model_trained = dm.model_id::text
WHERE
    (:generation_status = 'all' OR dv.generation_status ILIKE '%' || :generation_status || '%')
    AND (:dataset_name = 'all' 
         OR POSITION(LOWER(:dataset_name) IN LOWER(CONCAT('v', dv.major, '.', dv.minor))) > 0
         OR POSITION(LOWER(:dataset_name) IN LOWER(CONCAT(dv.major, '.', dv.minor))) > 0
         OR POSITION(LOWER(:dataset_name) IN LOWER(dv.major::text)) > 0
         OR POSITION(LOWER(:dataset_name) IN LOWER(dv.minor::text)) > 0)
ORDER BY
    CASE WHEN :sort_by = 'created_at' AND :sort_type = 'asc' THEN dv.created_at END ASC,
    CASE WHEN :sort_by = 'created_at' AND :sort_type = 'desc' THEN dv.created_at END DESC,
    -- CASE WHEN :sort_by = 'major' AND :sort_type = 'asc' THEN dv.major END ASC,
    -- CASE WHEN :sort_by = 'major' AND :sort_type = 'desc' THEN dv.major END DESC,
    -- CASE WHEN :sort_by = 'minor' AND :sort_type = 'asc' THEN dv.minor END ASC,
    -- CASE WHEN :sort_by = 'minor' AND :sort_type = 'desc' THEN dv.minor END DESC,
    CASE WHEN :sort_by IS NULL OR :sort_by = '' THEN dv.created_at END DESC
OFFSET ((GREATEST(:page, 1) - 1) * :page_size) LIMIT :page_size;