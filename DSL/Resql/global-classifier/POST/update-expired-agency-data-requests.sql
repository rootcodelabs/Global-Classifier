WITH expired_requests AS (
    UPDATE public.agency_data_requests
    SET status        = 'EXPIRED'::agency_request_status,
        error_message = 'Download link expired before generation started',
        updated_at    = CURRENT_TIMESTAMP
    WHERE status = 'PENDING'
      AND url_expires_at <= CURRENT_TIMESTAMP + INTERVAL '10 minutes'
    RETURNING id
)
SELECT COUNT(*) AS expired_count
FROM expired_requests;
