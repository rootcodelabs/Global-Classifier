UPDATE dataset_group_metadata
SET
    processed_data_available = :processed_data_available,
    raw_data_available = :raw_data_available,
    preprocess_data_location = :preprocess_data_location,
    raw_data_location = :raw_data_location,
    enable_allowed = :enable_allowed,
    last_updated_timestamp = :last_updated_timestamp::timestamp with time zone,
    num_samples = :num_samples,
    num_pages = :num_pages,
    validation_status = :validation_status::Validation_Status
WHERE id = :id;
