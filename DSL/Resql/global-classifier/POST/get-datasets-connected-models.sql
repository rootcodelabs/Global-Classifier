SELECT 
    dm.model_name,
    dm.major,
    dm.minor
FROM public.data_models dm
WHERE dm.model_id = ANY(
    SELECT jsonb_array_elements_text(connected_models)::BIGINT
    FROM public.datasets
    WHERE id = :datasetId
);