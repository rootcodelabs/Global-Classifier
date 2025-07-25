SELECT *
FROM public.data_models
WHERE model_group_key = :modelGroupKey
  AND major = (
    SELECT MAX(major)
    FROM public.data_models
    WHERE model_group_key = :modelGroupKey
  )
LIMIT 1;