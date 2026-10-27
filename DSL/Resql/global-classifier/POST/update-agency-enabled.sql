UPDATE public.integrated_agencies
SET 
    is_enabled = :isEnabled
WHERE 
    agency_id = :agencyId
    AND sync_status IN ('Synced_with_CKB', 'Resync_needed_with_CKB')
    AND part_of_network = TRUE
RETURNING agency_id;