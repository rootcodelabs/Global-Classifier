UPDATE models_metadata
SET
    deployment_env = 'undeployed'
WHERE id = :id