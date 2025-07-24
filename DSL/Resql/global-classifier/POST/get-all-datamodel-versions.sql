SELECT 
    model_id as id,
    model_name,
    major,
    minor
FROM public.data_models
ORDER BY model_id;