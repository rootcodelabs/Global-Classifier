SELECT
    dt.id,
    dt.model_group_key,
    dt.model_name,
    dt.major_version,
    dt.minor_version,
    dt.latest,
    dt.maturity_label,
    dt.deployment_env,
    dt.training_status,
    dt.base_models,
    dt.last_trained_timestamp,
    dt.created_timestamp,
    dt.connected_dg_id,
    dt.connected_dg_name,
    dt.connected_dg_major_version,
    dt.connected_dg_minor_version,
    dt.connected_dg_patch_version,
    jsonb_pretty(dt.training_results) AS training_results
FROM
    models_metadata dt
WHERE
    dt.deployment_env IN ('jira', 'outlook');