SELECT
    id,
    dg_id,
    group_name,
    major_version,
    minor_version,
    patch_version,
    latest,
    process_complete,
    progress_percentage,
    validation_status,
    validation_message
FROM dataset_progress_sessions
ORDER BY created_time DESC;
