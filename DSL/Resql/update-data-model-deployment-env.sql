UPDATE models_metadata
SET
    deployment_env = :deployment_env::Deployment_Env
WHERE id = :id;
