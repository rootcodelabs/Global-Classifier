INSERT INTO "integrated_agencies"
(agency_id, agency_name, group_key, is_latest, deployment_status, is_enabled, agency_data_hash, enable_allowed, last_model_trained, last_updated_timestamp, last_trained_timestamp, sync_status, created_at)
VALUES
(:agencyId, :agencyName, :groupKey, :isLatest, :deploymentStatus::deployment_status, :isEnabled, :agencyDataHash, :enableAllowed, :lastModelTrained, 
CASE WHEN :lastUpdatedTimestamp IS NOT NULL THEN :lastUpdatedTimestamp::timestamp with time zone ELSE NULL END,
CASE WHEN :lastTrainedTimestamp IS NOT NULL THEN :lastTrainedTimestamp::timestamp with time zone ELSE NULL END, 
:syncStatus::sync_status, :createdAt::timestamp with time zone);
