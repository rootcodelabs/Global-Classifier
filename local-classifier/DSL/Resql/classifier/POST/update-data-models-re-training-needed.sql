UPDATE models_metadata
SET
    training_status = 'retraining needed'
WHERE id = ANY (ARRAY[:ids]);