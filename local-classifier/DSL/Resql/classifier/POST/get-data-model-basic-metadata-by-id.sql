SELECT
    id AS model_id,
    model_name,
    major_version,
    minor_version
FROM models_metadata
WHERE id = :id;
