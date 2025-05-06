UPDATE dataset_group_metadata
SET
    last_model_trained =:last_model_trained
WHERE id = :id;