WITH update_latest AS (
    UPDATE dataset_group_metadata
    SET latest = false
    WHERE group_key = :group_key
),
update_specific AS (
    UPDATE dataset_group_metadata
    SET
        major_version = (
            SELECT COALESCE(MAX(major_version), 0) + 1
            FROM dataset_group_metadata
            WHERE group_key = :group_key
        ),
        connected_models = NULL::JSONB,
        preprocess_data_location = NULL,
        raw_data_location = NULL,
        num_samples = 0,
        num_pages = 0,
        last_trained_timestamp = NULL,
        validation_errors = NULL::JSONB,
        last_model_trained = NULL,
        enable_allowed = false,
        validation_status = 'unvalidated'::Validation_Status,
        is_enabled = false,
        minor_version = 0,
        patch_version = 0,
        latest = true,
        last_updated_timestamp = :last_updated_timestamp::timestamp with time zone,
        validation_criteria = :validation_criteria::JSONB,
        class_hierarchy = :class_hierarchy::JSONB
    WHERE id = :id
)
SELECT 1;