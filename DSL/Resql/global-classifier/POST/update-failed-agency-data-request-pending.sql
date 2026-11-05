WITH reset_request AS (
    UPDATE public.agency_data_requests r
    SET status     = 'PENDING'::agency_request_status,
        updated_at = CURRENT_TIMESTAMP
    FROM public.integrated_agencies ia
    WHERE ia.agency_id = r.agency_id
      AND ia.part_of_network = TRUE
      AND r.agency_id = :agencyId
      AND r.status = 'FAILED'
      AND r.url_expires_at > CURRENT_TIMESTAMP + INTERVAL '10 minutes'
      AND r.id = (
          SELECT MAX(latest.id)
          FROM public.agency_data_requests latest
          WHERE latest.agency_id = r.agency_id
      )
    RETURNING r.agency_id
),
syncing_agency AS (
    UPDATE public.integrated_agencies ia
    SET sync_status            = 'Sync_in_progress_with_CKB'::sync_status,
        last_updated_timestamp = CURRENT_TIMESTAMP
    WHERE ia.agency_id IN (SELECT agency_id FROM reset_request)
    RETURNING ia.agency_id
)
SELECT COUNT(*) AS reset_count
FROM reset_request;
