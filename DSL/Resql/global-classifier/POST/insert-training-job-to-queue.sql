INSERT INTO model_training_jobs (
    model_id,
    job_status,
    created_at
) VALUES (
    :model_id,
    'queued'::training_job_status,
    EXTRACT(EPOCH FROM NOW())::INTEGER
)
RETURNING 
    job_id,
    model_id,
    job_status,
    created_at,
    'Training job successfully queued' AS message;