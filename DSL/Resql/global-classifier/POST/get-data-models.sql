SELECT
    model_id,
    model_group_key,
    model_name,
    major,
    minor,
    latest,
    connected_ds_id,
    connected_ds_major_version,
    connected_ds_minor_version,
    base_models,
    deployment_env,
    created_timestamp,
    updated_timestamp,
    last_trained,
    model_status,
    training_status,
    training_results,
    CEIL(COUNT(*) OVER() / :page_size::DECIMAL) AS total_pages
FROM
    data_models
WHERE
    (:training_status = 'all' OR training_status = :training_status::training_status)
    AND (:model_status = 'all' OR model_status = :model_status::model_status)
    AND (:deployment_env = 'all' OR deployment_env = :deployment_env::deployment_environment)
    AND deployment_env != 'production'::deployment_environment
ORDER BY
    CASE WHEN :sort_by = 'createdAt' AND :sort_type = 'asc' THEN created_timestamp END ASC,
    CASE WHEN :sort_by = 'createdAt' AND :sort_type = 'desc' THEN created_timestamp END DESC,
    CASE WHEN :sort_by = 'lastTrained' AND :sort_type = 'asc' THEN last_trained END ASC,
    CASE WHEN :sort_by = 'lastTrained' AND :sort_type = 'desc' THEN last_trained END DESC,
    CASE WHEN :sort_by = 'modelName' AND :sort_type = 'asc' THEN model_name END ASC,
    CASE WHEN :sort_by = 'modelName' AND :sort_type = 'desc' THEN model_name END DESC,
    CASE WHEN :sort_by IS NULL OR :sort_by = '' THEN created_timestamp END DESC
OFFSET ((GREATEST(:page, 1) - 1) * :page_size) LIMIT :page_size;