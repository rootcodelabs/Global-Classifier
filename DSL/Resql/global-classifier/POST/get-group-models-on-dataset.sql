SELECT
    model_id,
    major,
    minor,
    training_status,
    deployment_env
FROM public.data_models
WHERE model_group_key = :modelGroupKey
  AND connected_ds_id = :datasetId
ORDER BY model_id;
