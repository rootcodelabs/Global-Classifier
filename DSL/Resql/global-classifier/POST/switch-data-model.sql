UPDATE public.data_models
SET
    deployment_env = CASE
        WHEN model_id = :newModelId THEN :deploymentEnv::deployment_environment
        WHEN model_id = :oldModelId THEN 'undeployed'::deployment_environment
        ELSE deployment_env
    END,
    latest = CASE
        WHEN :makeLatest::boolean THEN (model_id = :newModelId)
        ELSE latest
    END,
    updated_timestamp = CURRENT_TIMESTAMP
WHERE
    EXISTS (
        SELECT 1
        FROM public.data_models
        WHERE model_id = :oldModelId
          AND deployment_env = :deploymentEnv::deployment_environment
    )
    AND (
        model_id IN (:newModelId, :oldModelId)
        OR (
            :makeLatest::boolean
            AND latest IS TRUE
            AND model_group_key = (
                SELECT model_group_key FROM public.data_models WHERE model_id = :newModelId
            )
        )
    )
RETURNING
    model_id,
    deployment_env,
    latest;
