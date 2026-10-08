WITH incoming AS (
    SELECT
        a."agencyId"      AS agency_id,
        a."agencyName"    AS agency_name,
        a."partOfNetwork" AS part_of_network
    FROM jsonb_to_recordset(:agencies::jsonb) AS a("agencyId" TEXT, "agencyName" TEXT, "partOfNetwork" BOOLEAN)
),
previous AS (
    SELECT ia.agency_id, ia.part_of_network
    FROM public.integrated_agencies ia
    JOIN incoming i ON i.agency_id = ia.agency_id
),
upserted AS (
    INSERT INTO public.integrated_agencies AS ia (
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
        created_at,
        part_of_network
    )
    SELECT
        i.agency_id,
        i.agency_name,
        '',
        TRUE,
        'undeployed'::deployment_status,
        FALSE,
        '',
        FALSE,
        '',
        CURRENT_TIMESTAMP,
        '1970-01-01T00:00:00Z'::timestamp with time zone,
        'Unavailable_in_CKB'::sync_status,
        CURRENT_TIMESTAMP,
        i.part_of_network
    FROM incoming i
    ON CONFLICT (agency_id) DO UPDATE
    SET agency_name     = EXCLUDED.agency_name,
        part_of_network = EXCLUDED.part_of_network,
        is_enabled      = CASE WHEN EXCLUDED.part_of_network THEN ia.is_enabled ELSE FALSE END
    RETURNING ia.agency_id, ia.part_of_network
),
cancelled AS (
    UPDATE public.agency_data_requests r
    SET status        = 'CANCELLED'::agency_request_status,
        error_message = 'Agency left the network',
        updated_at    = CURRENT_TIMESTAMP
    FROM incoming i
    WHERE r.agency_id = i.agency_id
      AND i.part_of_network = FALSE
      AND r.status IN ('PENDING', 'FAILED')
    RETURNING r.id
)
SELECT
    u.agency_id,
    (p.agency_id IS NULL) AS is_new_agency,
    COALESCE(p.part_of_network AND NOT u.part_of_network, FALSE) AS left_network
FROM upserted u
LEFT JOIN previous p ON p.agency_id = u.agency_id
WHERE p.agency_id IS NULL
   OR (p.part_of_network AND NOT u.part_of_network);