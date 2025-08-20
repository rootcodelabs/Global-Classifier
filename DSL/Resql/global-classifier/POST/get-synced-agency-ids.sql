SELECT agency_id, agency_data_hash
FROM public.integrated_agencies
WHERE sync_status = 'Synced_with_CKB';