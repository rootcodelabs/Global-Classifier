SELECT
    id AS dg_id,
    group_name,
    major_version,
    minor_version,
    patch_version
FROM dataset_group_metadata
WHERE id = :id;
