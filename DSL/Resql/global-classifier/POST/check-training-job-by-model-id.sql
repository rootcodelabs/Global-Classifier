SELECT 
    EXISTS(SELECT 1 FROM ModelTrainingJobs WHERE model_id = :modelId) AS job_exists,
    COALESCE(
        (SELECT job_status 
         FROM ModelTrainingJobs 
         WHERE model_id = :modelId 
         ORDER BY created_at DESC 
         LIMIT 1), 
        'no-job'
    ) AS current_status,
    COALESCE(
        (SELECT job_id 
         FROM ModelTrainingJobs 
         WHERE model_id = :modelId 
         ORDER BY created_at DESC 
         LIMIT 1), 
        NULL
    ) AS latest_job_id;