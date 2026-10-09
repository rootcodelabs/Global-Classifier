WITH reset_requests AS (
    UPDATE public.agency_data_requests r
    SET status     = 'PENDING'::agency_request_status,
        updated_at = CURRENT_TIMESTAMP
    WHERE r.status = 'FAILED'
      AND r.retry_count < 3
      AND r.url_expires_at > CURRENT_TIMESTAMP + INTERVAL '10 minutes'
      AND r.id = (
          SELECT MAX(latest.id)
          FROM public.agency_data_requests latest
          WHERE latest.agency_id = r.agency_id
      )
    RETURNING r.id
)
SELECT COUNT(*) AS reset_count
FROM reset_requests;
