UPDATE dataset_group_metadata
SET connected_models =
    CASE
        WHEN connected_models IS NULL THEN jsonb_build_array(:connected_model::jsonb)
        ELSE connected_models || :connected_model::jsonb
    END
WHERE id = :id;
