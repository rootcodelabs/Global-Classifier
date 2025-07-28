SELECT *
FROM public.data_models
WHERE deployment_env = 'production'::deployment_environment
ORDER BY updated_timestamp DESC
LIMIT 1;