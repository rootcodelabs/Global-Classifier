SELECT 
    job_id,
    model_id,
    job_status,
    model_name,
    major_version,
    minor_version,
    latest, 
    created_at
FROM model_training_jobs 
WHERE job_status = 'queued'
ORDER BY created_at ASC
LIMIT 1;