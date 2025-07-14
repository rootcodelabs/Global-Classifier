SELECT 
    job_id,
    model_id,
    job_status,
    created_at
FROM model_training_jobs 
WHERE job_status = 'queued'
ORDER BY created_at ASC
LIMIT 1;