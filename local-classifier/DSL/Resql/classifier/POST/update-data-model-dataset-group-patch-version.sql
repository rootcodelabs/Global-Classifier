UPDATE models_metadata
SET
    connected_dg_patch_version = connected_dg_patch_version + 1
WHERE connected_dg_id = :dg_id;