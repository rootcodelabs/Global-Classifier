UPDATE integrated_agencies
SET 
    agency_name = COALESCE(:agencyName, agency_name),
    group_key = COALESCE(:groupKey, group_key),
    is_latest = COALESCE(:isLatest, is_latest),
    deployment_status = COALESCE(:deploymentStatus::deployment_status, deployment_status),
    is_enabled = COALESCE(:isEnabled, is_enabled),
    agency_data_hash = COALESCE(:agencyDataHash, agency_data_hash),
    enable_allowed = COALESCE(:enableAllowed, enable_allowed),
    last_model_trained = COALESCE(:lastModelTrained, last_model_trained),
    last_updated_timestamp = CURRENT_TIMESTAMP,
    last_trained_timestamp = COALESCE(:lastTrainedTimestamp::TIMESTAMP WITH TIME ZONE, last_trained_timestamp),
    sync_status = COALESCE(:syncStatus::sync_status, sync_status)
WHERE 
    agency_id = :agencyId
RETURNING 
    agency_id,
    agency_name,
    group_key,
    is_latest,
    deployment_status,
    is_enabled,
    agency_data_hash,
    enable_allowed,
    last_model_trained,
    last_updated_timestamp,
    last_trained_timestamp,
    sync_status,
    created_at;