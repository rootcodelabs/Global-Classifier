SELECT
    mps.id,
    mps.model_id,
    mps.model_name,
    mps.major_version,
    mps.minor_version,
    mps.latest,
    mps.process_complete,
    mps.progress_percentage,
    mps.training_progress_status as training_status,
    mps.training_message,
    mm.maturity_label,
    mm.deployment_env
FROM model_progress_sessions mps
JOIN
    models_metadata mm
ON
    mps.model_id = mm.id
ORDER BY mps.created_time DESC;