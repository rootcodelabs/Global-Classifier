INSERT INTO model_training_jobs (
    created_at,
    model_id,
    job_status,
    model_name,
    major_version,
    minor_version,
    latest,
    deployment_environment
) VALUES (
    EXTRACT(EPOCH FROM NOW())::INTEGER,
    :model_id,
    'queued'::training_job_status,
    :model_name,
    :major_version,
    :minor_version,
    :latest,
    :deployment_environment
)
RETURNING 
    job_id,
    model_id,
    job_status,
    created_at,
    model_name,
    major_version,
    minor_version,
    latest,
    deployment_environment,
    'Training job successfully queued' AS message;