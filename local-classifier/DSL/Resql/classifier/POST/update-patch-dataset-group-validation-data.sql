UPDATE dataset_group_metadata
SET
    validation_errors = :validation_errors::jsonb,
    last_updated_timestamp = CURRENT_TIMESTAMP
WHERE id = :id;
