UPDATE public.dataset_versions 
SET 
    connected_models = CASE 
        WHEN connected_models IS NULL THEN 
            jsonb_build_array(:modelId)
        WHEN NOT (connected_models @> jsonb_build_array(:modelId)) THEN 
            connected_models || jsonb_build_array(:modelId)
        ELSE 
            connected_models
    END,
    last_trained = CURRENT_TIMESTAMP,
    last_model_trained = :modelId
WHERE 
    id = :datasetId
RETURNING 
    id,
    connected_models;