SELECT 
    model_id as id,
    model_name,
    major,
    minor
FROM public.data_models
WHERE training_status = 'trained'
ORDER BY model_id;