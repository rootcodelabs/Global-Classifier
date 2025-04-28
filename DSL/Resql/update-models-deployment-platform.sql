UPDATE models_metadata
SET
    deployment_env = :updating_platform::Deployment_Env
WHERE deployment_env = :existing_platform::Deployment_Env