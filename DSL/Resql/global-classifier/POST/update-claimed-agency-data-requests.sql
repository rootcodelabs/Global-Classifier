UPDATE public.agency_data_requests r
SET status     = 'IN_PROGRESS'::agency_request_status,
    updated_at = CURRENT_TIMESTAMP
FROM public.integrated_agencies ia
WHERE ia.agency_id = r.agency_id
  AND r.status = 'PENDING'
  AND ia.part_of_network = TRUE
RETURNING
    r.id AS request_id,
    r.agency_id,
    ia.agency_name,
    r.presigned_url AS data_url,
    (COALESCE(ia.agency_data_hash, '') = '') AS is_new_agency;
