WITH linked_requests AS (
    UPDATE public.agency_data_requests r
    SET dataset_version_id = :datasetVersionId::BIGINT,
        updated_at         = CURRENT_TIMESTAMP
    WHERE r.id = ANY(
        SELECT jsonb_array_elements_text(:requestIds::jsonb)::BIGINT
    )
      AND r.status = 'IN_PROGRESS'
    RETURNING r.agency_id
),
syncing_agencies AS (
    UPDATE public.integrated_agencies ia
    SET sync_status = CASE
            WHEN COALESCE(ia.agency_data_hash, '') = '' THEN 'Sync_in_progress_with_CKB'
            ELSE 'Resync_in_progress_with_CKB'
        END::sync_status,
        last_updated_timestamp = CURRENT_TIMESTAMP
    WHERE ia.agency_id IN (SELECT agency_id FROM linked_requests)
    RETURNING ia.agency_id
)
SELECT COUNT(*) AS linked_count
FROM linked_requests;
