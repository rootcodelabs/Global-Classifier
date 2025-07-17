UPDATE public.model_training_jobs 
SET job_status = :jobStatus::training_job_status
WHERE job_id = :jobId;