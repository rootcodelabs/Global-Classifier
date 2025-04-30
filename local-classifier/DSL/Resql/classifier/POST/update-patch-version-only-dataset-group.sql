UPDATE dataset_group_metadata
    SET
        patch_version = patch_version + 1,
        last_updated_timestamp = CURRENT_TIMESTAMP
WHERE id = :id