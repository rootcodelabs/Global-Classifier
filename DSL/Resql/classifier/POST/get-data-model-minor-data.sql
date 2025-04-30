SELECT model_group_key, major_version, deployment_env, base_models, maturity_label
FROM models_metadata  WHERE id =:id;