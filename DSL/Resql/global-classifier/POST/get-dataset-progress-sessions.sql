SELECT
    id,
    dataset_id,
    major_version,
    minor_version,
    latest,
    process_complete,
    progress_percentage,
    generation_status,
    generation_message
FROM dataset_progress_sessions
ORDER BY created_time DESC;
