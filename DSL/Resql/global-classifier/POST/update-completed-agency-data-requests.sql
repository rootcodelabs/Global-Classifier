WITH incoming AS (
    SELECT
        a."agencyId"   AS agency_id,
        a."syncStatus" AS sync_status
    FROM jsonb_to_recordset(:agencies::jsonb) AS a("agencyId" TEXT, "syncStatus" TEXT)
),
outcome AS (
    SELECT
        r.id,
        CASE
            WHEN NOT ia.part_of_network THEN 'CANCELLED'
            WHEN :generationStatus <> 'Generation_Failed'
                 AND i.sync_status = 'Synced_with_CKB' THEN 'DONE'
            ELSE 'FAILED'
        END AS new_status
    FROM public.agency_data_requests r
    JOIN public.integrated_agencies ia ON ia.agency_id = r.agency_id
    LEFT JOIN incoming i ON i.agency_id = r.agency_id
    WHERE r.dataset_version_id = :datasetId::BIGINT
      AND r.status = 'IN_PROGRESS'
),
completed AS (
    UPDATE public.agency_data_requests r
    SET status        = o.new_status::agency_request_status,
        retry_count   = r.retry_count + CASE WHEN o.new_status = 'FAILED' THEN 1 ELSE 0 END,
        error_message = CASE
                            WHEN o.new_status = 'FAILED' THEN 'Generation failed'
                            WHEN o.new_status = 'CANCELLED' THEN 'Agency left the network'
                            ELSE NULL
                        END,
        updated_at    = CURRENT_TIMESTAMP
    FROM outcome o
    WHERE r.id = o.id
      AND r.status = 'IN_PROGRESS'
    RETURNING r.agency_id, r.data_hash, o.new_status
),
updated_agencies AS (
    UPDATE public.integrated_agencies ia
    SET agency_data_hash       = CASE WHEN c.new_status = 'DONE' THEN c.data_hash ELSE ia.agency_data_hash END,
        sync_status            = CASE
                                     WHEN c.new_status = 'DONE' THEN 'Synced_with_CKB'
                                     ELSE 'Sync_with_CKB_Failed'
                                 END::sync_status,
        is_enabled             = (c.new_status = 'DONE'),
        last_updated_timestamp = CURRENT_TIMESTAMP
    FROM completed c
    WHERE ia.agency_id = c.agency_id
      AND c.new_status IN ('DONE', 'FAILED')
    RETURNING ia.agency_id
)
SELECT
    COUNT(*) FILTER (WHERE new_status = 'DONE')      AS synced_count,
    COUNT(*) FILTER (WHERE new_status = 'FAILED')    AS failed_count,
    COUNT(*) FILTER (WHERE new_status = 'CANCELLED') AS cancelled_count
FROM completed;
