INSERT INTO ModelTrainingJobs (
    model_id,
    job_status,
    created_at
) VALUES (
    :modelId,
    'training-in-progress',
    EXTRACT(EPOCH FROM NOW())::INT
)
RETURNING 
    job_id,
    model_id,
    job_status,
    created_at,
    'Training job created' AS message;