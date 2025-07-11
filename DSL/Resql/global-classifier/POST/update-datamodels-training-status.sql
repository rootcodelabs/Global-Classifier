UPDATE public.data_models
SET 
    training_status = 'trained'::training_status,
    training_results = :trainingResults::jsonb,
    model_s3_location = :modelS3Location::text,
    last_trained = CURRENT_TIMESTAMP,
    updated_timestamp = CURRENT_TIMESTAMP
WHERE 
    model_id = :modelId
RETURNING 
    model_id,
    model_group_key,
    model_name,
    major,
    minor,
    training_status,
    training_results,
    updated_timestamp;