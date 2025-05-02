INSERT INTO "model_progress_sessions" (
    model_id,
    model_name,
    major_version,
    minor_version,
    latest,
    progress_percentage,
    training_progress_status
) VALUES (
    :model_id,
    :model_name,
    :major_version,
    :minor_version,
    :latest,
    :progress_percentage,
    :training_progress_status::Training_Progress_Status
)RETURNING id;