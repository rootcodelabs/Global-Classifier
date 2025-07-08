SELECT *
FROM public.data_models
WHERE model_group_key = :modelGroupKey
ORDER BY created_timestamp DESC
LIMIT 1;