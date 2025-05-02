SELECT  dt.id,
        dt.group_name,
       dt.major_version,
       dt.minor_version,
       dt.patch_version,
       dt.latest,
       dt.is_enabled,
       dt.enable_allowed,
       dt.created_timestamp,
       dt.last_updated_timestamp,
       dt.last_trained_timestamp,
       dt.last_model_trained,
       dt.validation_status,
       CEIL(COUNT(*) OVER() / :page_size::DECIMAL) AS total_pages
FROM "dataset_group_metadata" dt
WHERE
    (:major_version = -1 OR dt.major_version = :major_version)
    AND (:minor_version = -1 OR dt.minor_version = :minor_version)
    AND (:patch_version = -1 OR dt.patch_version = :patch_version)
    AND (:validation_status = 'all' OR dt.validation_status = :validation_status::Validation_Status)
    AND (:group_name = 'all' OR dt.group_name = :group_name)
ORDER BY
    CASE WHEN :sort_by = 'name' AND :sorting = 'asc' THEN dt.group_name END ASC,
    CASE WHEN :sort_by = 'name' AND :sorting = 'desc' THEN dt.group_name END DESC,
    CASE WHEN :sort_by = 'created_timestamp' AND :sorting = 'asc' THEN dt.created_timestamp END ASC,
    CASE WHEN :sort_by = 'created_timestamp' AND :sorting = 'desc' THEN dt.created_timestamp END DESC,
    CASE WHEN :sort_by = 'last_updated_timestamp' AND :sorting = 'asc' THEN dt.last_updated_timestamp END ASC,
    CASE WHEN :sort_by = 'last_updated_timestamp' AND :sorting = 'desc' THEN dt.last_updated_timestamp END DESC
OFFSET ((GREATEST(:page, 1) - 1) * :page_size) LIMIT :page_size;
