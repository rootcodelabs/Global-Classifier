WITH latest_successful_version AS (
    SELECT id
    FROM public.dataset_versions
    WHERE generation_status = 'Generation_Success'
    ORDER BY id DESC
    LIMIT 1
)
SELECT DISTINCT
    d.agency_id,
    v.id AS previous_dataset_id
FROM latest_successful_version v
JOIN public.datasets d ON d.dataset_version_id = v.id
JOIN public.integrated_agencies ia ON ia.agency_id = d.agency_id
WHERE ia.part_of_network = FALSE;
