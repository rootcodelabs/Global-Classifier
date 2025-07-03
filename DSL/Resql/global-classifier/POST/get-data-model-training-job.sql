SELECT 
    EXISTS(
        SELECT 1 
        FROM ModelTrainingJobs 
        WHERE job_status = 'training-in-progress'
    ) AS has_training_in_progress;