SELECT id, group_name, major_version, minor_version, patch_version, latest, is_enabled, num_samples, enable_allowed,
 validation_status, validation_errors, connected_models, validation_criteria, class_hierarchy
FROM dataset_group_metadata WHERE id = :id;
