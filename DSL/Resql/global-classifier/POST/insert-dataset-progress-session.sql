INSERT INTO "dataset_progress_sessions" (
    dataset_id,
    major_version,
    minor_version,
    latest,
    progress_percentage,
    generation_status
) VALUES (
    :dataset_id,
    :major_version,
    :minor_version,
    :latest,
    :progressPercentage,
    :generation_status::Generation_Progress_Status
)RETURNING id;