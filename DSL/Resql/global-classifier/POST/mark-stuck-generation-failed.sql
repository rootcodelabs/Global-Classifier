WITH stuck_versions AS (
    UPDATE public.dataset_versions
    SET generation_status = 'Generation_Failed',
        updated_at        = CURRENT_TIMESTAMP
    WHERE generation_status = 'Generation_in_Progress'
      AND created_at < CURRENT_TIMESTAMP - INTERVAL '3 hours'
    RETURNING id
),
stuck_requests AS (
    UPDATE public.agency_data_requests r
    SET status        = 'FAILED'::agency_request_status,
        retry_count   = r.retry_count + 1,
        error_message = 'Generation timed out',
        updated_at    = CURRENT_TIMESTAMP
    WHERE r.status = 'IN_PROGRESS'
      AND (
          r.updated_at < CURRENT_TIMESTAMP - INTERVAL '3 hours'
          OR r.dataset_version_id IN (SELECT id FROM stuck_versions)
      )
    RETURNING r.agency_id
),
failed_agencies AS (
    UPDATE public.integrated_agencies ia
    SET sync_status            = 'Sync_with_CKB_Failed'::sync_status,
        last_updated_timestamp = CURRENT_TIMESTAMP
    WHERE ia.agency_id IN (SELECT agency_id FROM stuck_requests)
    RETURNING ia.agency_id
)
SELECT
    (SELECT COUNT(*) FROM stuck_versions) AS cleared_versions,
    (SELECT COUNT(*) FROM stuck_requests) AS cleared_requests;
