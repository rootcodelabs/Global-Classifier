SELECT 
    agency_id,
    agency_name,
    group_key,
    is_latest,
    deployment_status,
    is_enabled,
    agency_data_hash,
    enable_allowed,
    last_model_trained,
    last_updated_timestamp,
    last_trained_timestamp,
    sync_status,
    created_at,
    CEIL(COUNT(*) OVER() / :page_size::DECIMAL) AS total_pages
FROM 
    integrated_agencies
WHERE
    (:agency_name = 'all' OR agency_name ILIKE '%' || :agency_name || '%')
ORDER BY
    CASE WHEN :sort_by = 'agency_name' AND :sort_type = 'asc' THEN agency_name END ASC,
    CASE WHEN :sort_by = 'agency_name' AND :sort_type = 'desc' THEN agency_name END DESC,
    CASE WHEN :sort_by = 'created_at' AND :sort_type = 'asc' THEN created_at END ASC,
    CASE WHEN :sort_by = 'created_at' AND :sort_type = 'desc' THEN created_at END DESC,
    CASE WHEN :sort_by = 'last_updated_timestamp' AND :sort_type = 'asc' THEN last_updated_timestamp END ASC,
    CASE WHEN :sort_by = 'last_updated_timestamp' AND :sort_type = 'desc' THEN last_updated_timestamp END DESC,
    CASE WHEN :sort_by IS NULL OR :sort_by = '' THEN last_updated_timestamp END DESC
OFFSET ((GREATEST(:page, 1) - 1) * :page_size) LIMIT :page_size;