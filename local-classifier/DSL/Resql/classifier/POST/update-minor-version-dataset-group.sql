WITH update_latest AS (
    UPDATE dataset_group_metadata
    SET latest = false
    WHERE group_key = :group_key
    RETURNING 1
),
update_specific AS (
    UPDATE dataset_group_metadata
    SET
        minor_version = (
            SELECT COALESCE(MAX(minor_version), 0) + 1
            FROM dataset_group_metadata
            WHERE group_key = :group_key
        ),
        enable_allowed = false,
        validation_status = 'in-progress'::Validation_Status,
        is_enabled = false,
        patch_version = 0,
        latest = true,
        last_updated_timestamp = :last_updated_timestamp::timestamp with time zone
    WHERE id = :id
    RETURNING 1
)
SELECT 1;
