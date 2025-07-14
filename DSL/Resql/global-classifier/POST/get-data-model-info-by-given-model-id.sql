SELECT 
    connected_ds_id,
    base_models
FROM data_models 
WHERE model_id = :model_id;