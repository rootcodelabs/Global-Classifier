INSERT INTO "dataset_progress_sessions" (
    dg_id,
    group_name,
    major_version,
    minor_version,
    patch_version,
    latest,
    progress_percentage,
    validation_status
) VALUES (
    :dg_id,
    :group_name,
    :major_version,
    :minor_version,
    :patch_version,
    :latest,
    :progressPercentage,
    :validation_status::Validation_Progress_Status
)RETURNING id;