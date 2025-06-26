SELECT
    model_id,
    model_name,
    major,
    minor,
    dataset_id,
    dataset_version,
    base_models,
    deployment_environment,
    created_at,
    last_trained,
    model_status,
    training_status,
    CEIL(COUNT(*) OVER() / :page_size::DECIMAL) AS total_pages
FROM
    data_models
WHERE
    (:training_status = 'all' OR training_status = :training_status)
    AND (:model_status = 'all' OR model_status = :model_status)
    AND (:deployment_environment = 'all' OR deployment_environment = :deployment_environment)
ORDER BY
    CASE WHEN :sort_by = 'createdAt' AND :sort_type = 'asc' THEN created_at END ASC,
    CASE WHEN :sort_by = 'createdAt' AND :sort_type = 'desc' THEN created_at END DESC,
    CASE WHEN :sort_by = 'lastTrained' AND :sort_type = 'asc' THEN last_trained END ASC,
    CASE WHEN :sort_by = 'lastTrained' AND :sort_type = 'desc' THEN last_trained END DESC,
    CASE WHEN :sort_by = 'modelName' AND :sort_type = 'asc' THEN model_name END ASC,
    CASE WHEN :sort_by = 'modelName' AND :sort_type = 'desc' THEN model_name END DESC,
    CASE WHEN :sort_by IS NULL OR :sort_by = '' THEN created_at END DESC
OFFSET ((GREATEST(:page, 1) - 1) * :page_size) LIMIT :page_size;