UPDATE public.data_models 
SET 
    training_status = 'training_failed',
    updated_timestamp = NOW()
WHERE model_id = :model_id;