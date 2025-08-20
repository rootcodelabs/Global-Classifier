UPDATE public.integrated_agencies
    SET 
        sync_status =  :syncStatus::sync_status,
        is_enabled = :isEnabled,
        last_updated_timestamp = CURRENT_TIMESTAMP
    WHERE 
        agency_id = :agencyId;