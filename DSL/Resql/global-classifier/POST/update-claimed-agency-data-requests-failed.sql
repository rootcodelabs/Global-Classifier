WITH failed_requests AS (
    UPDATE public.agency_data_requests r
    SET status        = 'FAILED'::agency_request_status,
        retry_count   = r.retry_count + 1,
        error_message = 'Generation could not be started',
        updated_at    = CURRENT_TIMESTAMP
    WHERE r.id = ANY(
        SELECT jsonb_array_elements_text(:requestIds::jsonb)::BIGINT
    )
      AND r.status = 'IN_PROGRESS'
    RETURNING r.agency_id
),
failed_agencies AS (
    UPDATE public.integrated_agencies ia
    SET sync_status            = 'Sync_with_CKB_Failed'::sync_status,
        last_updated_timestamp = CURRENT_TIMESTAMP
    WHERE ia.agency_id IN (SELECT agency_id FROM failed_requests)
    RETURNING ia.agency_id
)
SELECT COUNT(*) AS failed_count
FROM failed_requests;
