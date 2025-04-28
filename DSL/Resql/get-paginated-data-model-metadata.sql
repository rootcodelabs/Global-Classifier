SELECT
    dt.id,
    dt.model_group_key,
    dt.model_name,
    dt.major_version,
    dt.minor_version,
    dt.latest,
    dt.maturity_label,
    dt.deployment_env,
    dt.training_status,
    dt.base_models,
    dt.last_trained_timestamp,
    dt.created_timestamp,
    dt.connected_dg_id,
    dt.connected_dg_name,
    dt.connected_dg_major_version,
    dt.connected_dg_minor_version,
    dt.connected_dg_patch_version,
    jsonb_pretty(dt.training_results) AS training_results,
    CEIL(COUNT(*) OVER() / :page_size::DECIMAL) AS total_pages
FROM
    models_metadata dt
WHERE
    (:major_version = -1 OR dt.major_version = :major_version)
    AND (:minor_version = -1 OR dt.minor_version = :minor_version)
    AND (:model_name = 'all' OR dt.model_name = :model_name)
    AND (:deployment_maturity = 'all' OR dt.maturity_label = :deployment_maturity::Maturity_Label)
    AND (:training_status = 'all' OR dt.training_status = :training_status::Training_Status)
    AND (:platform = 'all' OR dt.deployment_env = :platform::Deployment_Env)
    AND (:dataset_group = -1 OR dt.connected_dg_id = :dataset_group)
ORDER BY
    CASE WHEN :sort_by = 'name' AND :sort_type = 'asc' THEN dt.model_name END ASC,
    CASE WHEN :sort_by = 'name' AND :sort_type = 'desc' THEN dt.model_name END DESC,
    CASE WHEN :sort_by = 'created_timestamp' AND :sort_type = 'asc' THEN dt.created_timestamp END ASC,
    CASE WHEN :sort_by = 'created_timestamp' AND :sort_type = 'desc' THEN dt.created_timestamp END DESC
OFFSET ((GREATEST(:page, 1) - 1) * :page_size) LIMIT :page_size;

