SELECT model_id, model_group_key, model_name, major, minor, latest, training_status, deployment_env, last_trained, model_status, training_results, created_timestamp, updated_timestamp 
FROM public.data_models
WHERE deployment_env = 'production'::deployment_environment
ORDER BY updated_timestamp DESC
LIMIT 1;