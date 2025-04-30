UPDATE dataset_group_metadata
SET connected_models = (
    SELECT jsonb_agg(elem)
    FROM jsonb_array_elements(connected_models) elem
    WHERE (elem->>'modelId')::int <> :model_id
)
WHERE id = :id;