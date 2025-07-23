SELECT
    id,
    dataset_id,
    major_version,
    minor_version,
    latest,
    process_complete,
    progress_percentage,
    validation_status,
    validation_message
FROM dataset_progress_sessions
ORDER BY created_time DESC;
