UPDATE public.data_models
SET 
    latest = false,
    updated_timestamp = CURRENT_TIMESTAMP
WHERE 
    model_id = :modelId
RETURNING 
    model_id,
    model_group_key,
    model_name,
    major,
    minor,
    latest,
    deployment_env,
    training_status,
    updated_timestamp;