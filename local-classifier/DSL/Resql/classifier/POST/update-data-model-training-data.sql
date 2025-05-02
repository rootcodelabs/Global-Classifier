UPDATE models_metadata
SET
    training_status = :training_status::Training_Status,
    model_s3_location = :model_s3_location,
    last_trained_timestamp = :last_trained_timestamp::timestamp with time zone,
    training_results = :training_results::jsonb,
    inference_routes = :inference_routes::jsonb
WHERE id = :id;
