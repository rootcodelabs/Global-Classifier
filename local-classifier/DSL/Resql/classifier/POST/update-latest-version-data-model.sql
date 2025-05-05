UPDATE models_metadata
SET latest = false
WHERE model_group_key = :group_key