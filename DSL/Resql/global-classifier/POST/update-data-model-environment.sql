UPDATE public.data_models
SET
    deployment_env = :deploymentEnv::deployment_environment,
    updated_timestamp = CURRENT_TIMESTAMP
WHERE
    model_id = :modelId
RETURNING
    model_id,
    deployment_env;
