WITH incoming AS (
    SELECT
        a."agencyId"      AS agency_id,
        a."dataHash"      AS data_hash,
        a."presignedUrl"  AS presigned_url,
        a."urlExpiresAt"::timestamp with time zone AS url_expires_at,
        a."partOfNetwork" AS part_of_network
    FROM jsonb_to_recordset(:agencies::jsonb) AS a(
        "agencyId" TEXT, "dataHash" TEXT, "presignedUrl" TEXT, "urlExpiresAt" TEXT, "partOfNetwork" BOOLEAN
    )
),
candidates AS (
    SELECT
        i.agency_id,
        i.data_hash,
        i.presigned_url,
        i.url_expires_at
    FROM incoming i
    JOIN public.integrated_agencies ia ON ia.agency_id = i.agency_id
    WHERE i.part_of_network IS TRUE
      AND i.data_hash IS DISTINCT FROM ia.agency_data_hash
),
latest AS (
    SELECT DISTINCT ON (r.agency_id) r.id, r.agency_id, r.data_hash, r.status
    FROM public.agency_data_requests r
    JOIN candidates c ON c.agency_id = r.agency_id
    ORDER BY r.agency_id, r.id DESC
),
decided AS (
    SELECT
        c.agency_id,
        c.data_hash,
        c.presigned_url,
        c.url_expires_at,
        l.id AS latest_id,
        CASE
            WHEN l.status IN ('PENDING', 'FAILED') AND l.data_hash = c.data_hash THEN 'REFRESH_LINK'
            WHEN EXISTS (
                SELECT 1
                FROM public.agency_data_requests r
                WHERE r.agency_id = c.agency_id
                  AND r.status = 'IN_PROGRESS'
                  AND r.data_hash = c.data_hash
            ) THEN 'SKIP'
            WHEN l.status IN ('PENDING', 'FAILED') THEN 'OVERWRITE'
            ELSE 'INSERT'
        END AS action
    FROM candidates c
    LEFT JOIN latest l ON l.agency_id = c.agency_id
),
refreshed AS (
    UPDATE public.agency_data_requests r
    SET presigned_url  = d.presigned_url,
        url_expires_at = d.url_expires_at,
        updated_at     = CURRENT_TIMESTAMP
    FROM decided d
    WHERE r.id = d.latest_id
      AND d.action = 'REFRESH_LINK'
      AND r.status IN ('PENDING', 'FAILED')
      AND r.presigned_url IS DISTINCT FROM d.presigned_url
    RETURNING r.id
),
overwritten AS (
    UPDATE public.agency_data_requests r
    SET data_hash      = d.data_hash,
        presigned_url  = d.presigned_url,
        url_expires_at = d.url_expires_at,
        status         = 'PENDING'::agency_request_status,
        retry_count    = 0,
        error_message  = NULL,
        updated_at     = CURRENT_TIMESTAMP
    FROM decided d
    WHERE r.id = d.latest_id
      AND d.action = 'OVERWRITE'
      AND r.status IN ('PENDING', 'FAILED')
    RETURNING r.agency_id
),
inserted AS (
    INSERT INTO public.agency_data_requests (agency_id, data_hash, presigned_url, url_expires_at, status)
    SELECT d.agency_id, d.data_hash, d.presigned_url, d.url_expires_at, 'PENDING'::agency_request_status
    FROM decided d
    WHERE d.action = 'INSERT'
    RETURNING agency_id
)
SELECT agency_id FROM overwritten
UNION ALL
SELECT agency_id FROM inserted;