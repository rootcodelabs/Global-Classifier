INSERT INTO dataset_group_metadata (
    group_name, group_key, major_version, minor_version, patch_version, latest,
    is_enabled, enable_allowed, last_model_trained, created_timestamp,
    last_updated_timestamp, last_trained_timestamp, validation_status,
    validation_errors, processed_data_available, raw_data_available,
    num_samples, num_pages, raw_data_location, preprocess_data_location,
    validation_criteria, class_hierarchy, connected_models
)
SELECT
    group_name, group_key, major_version,
    (
        SELECT COALESCE(MAX(minor_version), 0) + 1
        FROM dataset_group_metadata
        WHERE group_key = :group_key AND major_version = :major_version
    ) AS minor_version,
    0 AS patch_version, true AS latest,
    false AS is_enabled, false AS enable_allowed, last_model_trained, created_timestamp,
    CURRENT_TIMESTAMP AS last_updated_timestamp, last_trained_timestamp,
    'in-progress'::Validation_Status AS validation_status, NULL AS validation_errors, false AS processed_data_available,
    false AS raw_data_available, 0 AS num_samples,  0 AS num_pages, NULL AS raw_data_location, NULL AS preprocess_data_location,
    validation_criteria, class_hierarchy, connected_models
FROM dataset_group_metadata
WHERE id = :id
RETURNING id;
