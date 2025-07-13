UPDATE public.data_models
SET 
    deployment_env = 'undeployed'::deployment_environment,
    updated_timestamp = CURRENT_TIMESTAMP
WHERE 
    deployment_env = 'production'::deployment_environment
RETURNING 
    model_id,
    model_group_key,
    model_name,
    major,
    minor,
    deployment_env,
    updated_timestamp;