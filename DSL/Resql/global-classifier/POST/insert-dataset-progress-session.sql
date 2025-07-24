INSERT INTO "dataset_progress_sessions" (
    dataset_id,
    major_version,
    minor_version,
    latest,
    progress_percentage,
    validation_status
) VALUES (
    :dataset_id,
    :major_version,
    :minor_version,
    :latest,
    :progressPercentage,
    :validation_status::Validation_Progress_Status
)RETURNING id;