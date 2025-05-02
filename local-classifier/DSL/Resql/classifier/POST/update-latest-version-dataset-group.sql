UPDATE dataset_group_metadata
SET latest = false
WHERE group_key = :group_key