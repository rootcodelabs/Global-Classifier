INSERT INTO public.model_training_jobs (
    created_at,
    model_id,
    job_status,
    model_name,
    major_version,
    minor_version,
    latest,
    deployment_environment
)
SELECT
    EXTRACT(EPOCH FROM NOW())::INTEGER,
    :modelId,
    'training-in-progress'::training_job_status,
    :modelName,
    :majorVersion,
    0,
    false,
    :deploymentEnvironment
WHERE NOT EXISTS (
    SELECT 1
    FROM public.model_training_jobs
    WHERE job_status = 'training-in-progress'
)
RETURNING
    job_id,
    model_id,
    job_status;
