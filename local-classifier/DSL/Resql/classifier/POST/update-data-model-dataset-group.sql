UPDATE models_metadata
SET
    connected_dg_name = null,
    connected_dg_id = null,
    connected_dg_major_version = 0,
    connected_dg_minor_version = 0,
    connected_dg_patch_version = 0
WHERE connected_dg_id = :id;
